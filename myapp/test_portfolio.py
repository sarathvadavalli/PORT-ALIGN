from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from .models import AssetClass, Holding, Instrument, InvestorProfile, InvestorSequence, Portfolio, TargetAllocation, TradePrice
from .portfolio_services import portfolio_valuation, save_target_allocation

User = get_user_model()
TODAY = date(2026, 11, 9)


def fixture():
    user = User.objects.create_user(username='owner', email='owner@example.com')
    other = User.objects.create_user(username='otherowner', email='otherowner@example.com')
    profile = InvestorProfile.objects.create(user=user)
    other_profile = InvestorProfile.objects.create(user=other)
    portfolio = Portfolio.objects.create(pk='PORT-1', investor=profile, portfolio_name='My Investments', cash_balance='500.0000')
    other_portfolio = Portfolio.objects.create(pk='PORT-2', investor=other_profile, portfolio_name='Private Investments')
    assets = [AssetClass.objects.create(pk=f'AC-{index}', name=name) for index, name in enumerate(['Equity', 'Bonds', 'Gold'])]
    return user, other, portfolio, other_portfolio, assets


def rows(assets, values=('60', '30', '10')):
    return [{'asset_class': asset.pk, 'target_percentage': Decimal(value)} for asset, value in zip(assets, values)]


def payload(assets, values=('60', '30', '10')):
    result = {'allocations-TOTAL_FORMS': str(len(assets)), 'allocations-INITIAL_FORMS': str(len(assets))}
    for index, (asset, value) in enumerate(zip(assets, values)):
        result[f'allocations-{index}-asset_class'] = asset.pk
        result[f'allocations-{index}-target_percentage'] = value
    return result


class PortfolioViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.other, cls.portfolio, cls.other_portfolio, cls.assets = fixture()
        cls.instruments = [Instrument.objects.create(pk=f'I-{i}', name=f'Instrument {i}', symbol=f'SYM{i}',
                            asset_class=cls.assets[0], exchange='TEST', currency='INR') for i in range(3)]
        for i, instrument in enumerate(cls.instruments):
            Holding.objects.create(pk=f'H-{i}', portfolio=cls.portfolio, instrument=instrument,
                                   quantity='1.23456789' if i == 0 else '2', average_cost='5.25' if i == 0 else None)
        Holding.objects.create(pk='OTHER-H', portfolio=cls.other_portfolio, instrument=cls.instruments[0], quantity='999')
        TradePrice.objects.create(instrument=cls.instruments[0], price_date=TODAY - timedelta(days=3), closing_price='9')
        TradePrice.objects.create(instrument=cls.instruments[0], price_date=TODAY - timedelta(days=2), closing_price='12.345678')
        TradePrice.objects.create(instrument=cls.instruments[0], price_date=TODAY, closing_price=None)
        TradePrice.objects.create(instrument=cls.instruments[0], price_date=TODAY + timedelta(days=1), closing_price='1000')
        TradePrice.objects.create(instrument=cls.instruments[1], price_date=TODAY - timedelta(days=60), closing_price='25')
        TradePrice.objects.create(instrument=cls.instruments[2], price_date=TODAY, closing_price=None)
        TradePrice.objects.create(instrument=cls.instruments[2], price_date=TODAY + timedelta(days=1), closing_price='99')

    def setUp(self):
        self.client.force_login(self.user)

    def test_prices_values_and_constant_query_count(self):
        with self.assertNumQueries(1):
            result = portfolio_valuation(self.portfolio, as_of=TODAY)
        self.assertEqual(len(result['holdings']), 3)
        first, old, missing = result['holdings']
        self.assertEqual(first.latest_price, Decimal('12.345678'))
        self.assertEqual(first.latest_price_date, TODAY - timedelta(days=2))
        self.assertEqual(first.market_value, Decimal('1.23456789') * Decimal('12.345678'))
        self.assertEqual(old.latest_price_date, TODAY - timedelta(days=60))
        self.assertIsNone(missing.market_value)
        self.assertEqual(result['missing_price_count'], 1)
        self.assertEqual(result['total_market_value'], first.market_value + Decimal('50'))
        with self.assertNumQueries(0):
            for holding in result['holdings']:
                self.assertTrue(holding.instrument.asset_class.name)

    @patch('myapp.portfolio_services.timezone.localdate', return_value=TODAY)
    def test_portfolio_page_displays_only_own_holdings(self, unused):
        response = self.client.get(reverse('my_portfolio'), {'portfolio_id': self.other_portfolio.pk})
        self.assertEqual(response.status_code, 200)
        for text in ['My Investments', 'Instrument 0', 'SYM0', 'Equity', '500.00', 'Partial total', 'Unavailable']:
            self.assertContains(response, text)
        self.assertNotContains(response, 'Private Investments')
        for value in ['1.23', '₹5.25', '₹12.35', '2.00', '₹25.00']:
            self.assertContains(response, f'<td class="numeric">{value}</td>')
        self.assertNotContains(response, '12.345678')
        self.assertEqual(response.context['portfolio'].pk, self.portfolio.pk)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, 'protected-history.js')

    def test_empty_portfolio(self):
        self.client.force_login(self.other)
        Holding.objects.filter(portfolio=self.other_portfolio).delete()
        response = self.client.get(reverse('my_portfolio'))
        self.assertContains(response, 'No holdings yet.')
        self.assertEqual(response.context['total_market_value'], Decimal('0'))

    def test_all_prices_missing(self):
        TradePrice.objects.all().delete()
        result = portfolio_valuation(self.portfolio, as_of=TODAY)
        self.assertEqual(result['total_market_value'], Decimal('0'))
        self.assertEqual(result['missing_price_count'], 3)

    def test_no_portfolio_or_profile_is_graceful(self):
        new_user = User.objects.create_user(username='new', email='new@example.com')
        self.client.force_login(new_user)
        for route in ['my_portfolio', 'target_allocation']:
            self.assertContains(self.client.get(reverse(route)), 'No portfolio linked yet.')
        self.assertEqual(Portfolio.objects.count(), 2)

    def test_authentication_and_read_only_access(self):
        self.assertEqual(self.client.post(reverse('my_portfolio')).status_code, 405)
        self.assertEqual(self.client.get(f'/portfolio/{self.other_portfolio.pk}/').status_code, 404)
        self.client.logout()
        for route in ['my_portfolio', 'target_allocation']:
            response = self.client.get(reverse(route))
            self.assertRedirects(response, reverse('login') + '?next=' + reverse(route))
            self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.post(reverse('target_allocation'), payload(self.assets)).status_code, 302)
        self.assertEqual(TargetAllocation.objects.count(), 0)

    def test_dashboard_navigation(self):
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, reverse('my_portfolio'))
        self.assertContains(response, reverse('target_allocation'))


class AllocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.other, cls.portfolio, cls.other_portfolio, cls.assets = fixture()

    def setUp(self):
        self.client.force_login(self.user)

    def test_initial_setup_shows_every_class_once(self):
        response = self.client.get(reverse('target_allocation'))
        self.assertContains(response, 'Set your first allocation')
        for asset in self.assets:
            self.assertContains(response, f'value="{asset.pk}"', count=1)
        self.assertEqual(len(response.context['formset'].forms), 3)
        self.assertIn('no-store', response['Cache-Control'])

    def test_create_and_complete_changed_snapshot(self):
        self.assertRedirects(self.client.post(reverse('target_allocation'), payload(self.assets)), reverse('target_allocation'))
        initial = list(TargetAllocation.objects.filter(version_number=1).values())
        response = self.client.post(reverse('target_allocation'), payload(self.assets, ('50', '40', '10')))
        self.assertRedirects(response, reverse('target_allocation'))
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.current_allocation_version, 2)
        self.assertEqual(TargetAllocation.objects.count(), 6)
        self.assertEqual(initial, list(TargetAllocation.objects.filter(version_number=1).values()))
        self.assertEqual(TargetAllocation.objects.get(version_number=2, asset_class=self.assets[2]).target_percentage, Decimal('10'))
        current = self.client.get(reverse('target_allocation')).context['formset']
        displayed = {form.initial['asset_class']: form.initial['target_percentage'] for form in current}
        self.assertEqual(displayed[self.assets[0].pk], Decimal('50'))

    def test_unchanged_submission_creates_no_new_version(self):
        save_target_allocation(user=self.user, portfolio_id=self.portfolio.pk, rows=rows(self.assets))
        before_updated = Portfolio.objects.get(pk=self.portfolio.pk).updated_at
        response = self.client.post(reverse('target_allocation'), payload(self.assets, ('60.0000', '30.00', '10')), follow=True)
        self.assertRedirects(response, reverse('target_allocation'))
        self.assertContains(response, 'unchanged')
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.current_allocation_version, 1)
        self.assertEqual(self.portfolio.updated_at, before_updated)
        self.assertEqual(TargetAllocation.objects.count(), 3)

    def test_decimal_exact_total_and_zero_hundred_boundaries(self):
        for values in [('33.3333', '33.3333', '33.3334'), ('0', '100', '0')]:
            self.assertRedirects(self.client.post(reverse('target_allocation'), payload(self.assets, values)), reverse('target_allocation'))
        self.assertEqual(TargetAllocation.objects.count(), 6)

    def test_invalid_percentages_preserve_saved_snapshot(self):
        save_target_allocation(user=self.user, portfolio_id=self.portfolio.pk, rows=rows(self.assets))
        for values in [('60', '20', '10'), ('-1', '91', '10'), ('101', '0', '0'), ('abc', '30', '10'),
                       ('NaN', '30', '10'), ('Infinity', '30', '10'), ('60.00001', '30', '9.99999'), ('', '30', '10')]:
            with self.subTest(values=values):
                response = self.client.post(reverse('target_allocation'), payload(self.assets, values))
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context['formset'].is_valid())
                self.assertEqual(TargetAllocation.objects.count(), 3)
                self.assertEqual(Portfolio.objects.get(pk=self.portfolio.pk).current_allocation_version, 1)

    def test_duplicate_missing_unknown_and_management_tampering(self):
        duplicate = payload(self.assets)
        duplicate['allocations-1-asset_class'] = self.assets[0].pk
        missing = payload(self.assets[:2], ('70', '30'))
        unknown = payload(self.assets)
        unknown['allocations-0-asset_class'] = 'not-a-class'
        forged_initial = payload(self.assets, ('0', '0', '0'))
        forged_initial['allocations-INITIAL_FORMS'] = '0'
        for values in [duplicate, missing, unknown, {}, forged_initial]:
            response = self.client.post(reverse('target_allocation'), values)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['formset'].is_valid())
            self.assertEqual(TargetAllocation.objects.count(), 0)

    def test_only_own_portfolio_can_be_updated(self):
        values = payload(self.assets)
        values['portfolio_id'] = self.other_portfolio.pk
        self.assertRedirects(self.client.post(reverse('target_allocation'), values), reverse('target_allocation'))
        self.assertEqual(TargetAllocation.objects.filter(portfolio=self.other_portfolio).count(), 0)
        with self.assertRaises(Portfolio.DoesNotExist):
            save_target_allocation(user=self.other, portfolio_id=self.portfolio.pk, rows=rows(self.assets))

    def test_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('target_allocation'), payload(self.assets)).status_code, 403)

    def test_snapshot_insert_failure_rolls_back_all_rows(self):
        save_target_allocation(user=self.user, portfolio_id=self.portfolio.pk, rows=rows(self.assets))

        def fail_after_partial_insert(objects):
            objects[0].save(force_insert=True)
            raise IntegrityError('simulated partial insert failure')

        with patch.object(TargetAllocation.objects, 'bulk_create', side_effect=fail_after_partial_insert):
            response = self.client.post(reverse('target_allocation'), payload(self.assets, ('50', '40', '10')))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'could not be saved')
        self.assertEqual(TargetAllocation.objects.count(), 3)
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.current_allocation_version, 1)

    def test_version_reference_failure_rolls_back_snapshot(self):
        with patch.object(Portfolio, 'save', side_effect=IntegrityError('reference failed')):
            with self.assertRaises(IntegrityError):
                save_target_allocation(user=self.user, portfolio_id=self.portfolio.pk, rows=rows(self.assets))
        self.assertEqual(TargetAllocation.objects.count(), 0)
        self.assertEqual(Portfolio.objects.get(pk=self.portfolio.pk).current_allocation_version, 0)

    def test_database_snapshot_uniqueness(self):
        save_target_allocation(user=self.user, portfolio_id=self.portfolio.pk, rows=rows(self.assets))
        with self.assertRaises(IntegrityError), transaction.atomic():
            TargetAllocation.objects.create(portfolio=self.portfolio, version_number=1, asset_class=self.assets[0], target_percentage='50')

    def test_version_migration_preserves_rows_and_uses_highest_version(self):
        from importlib import import_module
        from django.apps import apps
        for version in [1, 3]:
            TargetAllocation.objects.bulk_create([
                TargetAllocation(portfolio=self.portfolio, version_number=version,
                                 asset_class_id=row['asset_class'], target_percentage=row['target_percentage'])
                for row in rows(self.assets)
            ])
        before = list(TargetAllocation.objects.order_by('pk').values())
        migration = import_module('myapp.migrations.0009_portfolio_current_allocation_version')
        with connection.schema_editor() as schema_editor:
            migration.initialize_versions(apps, schema_editor)
        self.assertEqual(Portfolio.objects.get(pk=self.portfolio.pk).current_allocation_version, 3)
        self.assertEqual(Portfolio.objects.get(pk=self.other_portfolio.pk).current_allocation_version, 0)
        self.assertEqual(before, list(TargetAllocation.objects.order_by('pk').values()))

    def test_service_rejects_invalid_rows(self):
        invalid = [rows(self.assets, ('60', '30', '9')), rows(self.assets, ('-1', '91', '10')),
                   rows(self.assets, ('NaN', '30', '10')), rows(self.assets[:2], ('50', '50'))]
        for values in invalid:
            with self.assertRaises(ValidationError):
                save_target_allocation(user=self.user, portfolio_id=self.portfolio.pk, rows=values)
        self.assertEqual(TargetAllocation.objects.count(), 0)


class ConcurrentAllocationTests(TransactionTestCase):
    def setUp(self):
        InvestorSequence.objects.get_or_create(pk=1, defaults={'last_value': 0})
        self.user, self.other, self.portfolio, self.other_portfolio, self.assets = fixture()

    def run_saves(self, allocations):
        if connection.vendor != 'mysql':
            self.skipTest('Row locking is verified against the configured MySQL database.')
        barrier = Barrier(2)

        def save(values):
            try:
                barrier.wait(timeout=10)
                return save_target_allocation(user=self.user, portfolio_id=self.portfolio.pk, rows=rows(self.assets, values))
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(save, allocations))

    def test_distinct_concurrent_changes_create_serial_complete_snapshots(self):
        results = self.run_saves([('60', '30', '10'), ('50', '40', '10')])
        self.assertEqual(sorted(version for version, changed in results), [1, 2])
        for version in [1, 2]:
            self.assertEqual(TargetAllocation.objects.filter(version_number=version).count(), 3)
        self.assertEqual(Portfolio.objects.get(pk=self.portfolio.pk).current_allocation_version, 2)

    def test_identical_concurrent_submissions_create_one_snapshot(self):
        results = self.run_saves([('60', '30', '10'), ('60', '30', '10')])
        self.assertEqual(sorted(results), [(1, False), (1, True)])
        self.assertEqual(TargetAllocation.objects.count(), 3)
