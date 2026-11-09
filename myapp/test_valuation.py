from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse
from django.test.utils import CaptureQueriesContext

from .models import Holding, Instrument, Portfolio, TargetAllocation, TradePrice
from .portfolio_services import portfolio_allocation_valuation, save_target_allocation
from .test_portfolio import TODAY, fixture, rows


class ValuationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.other, cls.portfolio, cls.other_portfolio, cls.assets = fixture()
        cls.holdings = []
        for index, (asset, quantity, price) in enumerate([
            (cls.assets[0], '2', '15'), (cls.assets[0], '3', '10'), (cls.assets[1], '4', '10'),
        ]):
            instrument = Instrument.objects.create(pk=f'V-{index}', name=f'Valuation instrument {index}',
                symbol=f'VAL{index}', asset_class=asset, exchange='TEST', currency='INR')
            cls.holdings.append(Holding.objects.create(pk=f'VH-{index}', portfolio=cls.portfolio,
                instrument=instrument, quantity=quantity))
            TradePrice.objects.create(instrument=instrument, price_date=TODAY, closing_price=price)
        save_target_allocation(user=cls.user, portfolio_id=cls.portfolio.pk, rows=rows(cls.assets, ('60', '40', '0')))
        cls.portfolio.refresh_from_db()

    def setUp(self):
        self.client.force_login(self.user)

    def value(self):
        return portfolio_allocation_valuation(self.portfolio, as_of=TODAY)

    def by_asset(self, result):
        return {row['asset_class'].pk: row for row in result['allocations']}

    def set_equity_weight(self, percentage):
        TradePrice.objects.update(closing_price=1)
        Holding.objects.filter(pk=self.holdings[0].pk).update(quantity=Decimal(percentage) - Decimal('20'))
        Holding.objects.filter(pk=self.holdings[1].pk).update(quantity=20)
        Holding.objects.filter(pk=self.holdings[2].pk).update(quantity=Decimal('100') - Decimal(percentage))
        save_target_allocation(user=self.user, portfolio_id=self.portfolio.pk, rows=rows(self.assets, ('50', '50', '0')))
        self.portfolio.refresh_from_db()

    def test_aggregated_values_percentages_and_unheld_asset_class(self):
        with self.assertNumQueries(3):
            result = self.value()
        by_asset = self.by_asset(result)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['total_market_value'], Decimal('100'))
        self.assertEqual(by_asset[self.assets[0].pk]['market_value'], Decimal('60'))
        self.assertEqual(by_asset[self.assets[0].pk]['current_percentage'], Decimal('60'))
        self.assertEqual(by_asset[self.assets[1].pk]['current_percentage'], Decimal('40'))
        self.assertEqual(by_asset[self.assets[2].pk]['market_value'], Decimal('0'))
        self.assertEqual(by_asset[self.assets[2].pk]['current_percentage'], Decimal('0'))
        self.assertEqual(sum(row['current_percentage'] for row in result['allocations']), Decimal('100'))
        self.assertFalse(result['rebalance_allowed'])
        self.assertEqual(result['message'], 'Your portfolio is balanced. No rebalancing is currently required.')

    def test_latest_target_snapshot_is_used(self):
        save_target_allocation(user=self.user, portfolio_id=self.portfolio.pk, rows=rows(self.assets, ('50', '30', '20')))
        self.portfolio.refresh_from_db()
        result = self.value()
        by_asset = self.by_asset(result)
        self.assertEqual(result['target_version'], 2)
        self.assertEqual(by_asset[self.assets[0].pk]['drift'], Decimal('10'))
        self.assertEqual(by_asset[self.assets[1].pk]['drift'], Decimal('10'))
        self.assertEqual(by_asset[self.assets[2].pk]['drift'], Decimal('-20'))
        self.assertEqual(by_asset[self.assets[2].pk]['direction'], 'Underweight')
        self.assertTrue(result['recommend_rebalancing'])
        self.assertEqual(TargetAllocation.objects.filter(version_number=1).count(), 3)

    def test_thresholds_use_unrounded_decimal_values_and_inclusive_boundaries(self):
        for weight, allowed, recommended, band in [
            ('50', False, False, 'near'), ('52', False, False, 'near'),
            ('48', False, False, 'near'), ('52.00000001', True, False, 'over'),
            ('47.99999999', True, False, 'under'), ('55', True, False, 'over'),
            ('45', True, False, 'under'), ('55.00000001', True, True, 'over'),
            ('44.99999999', True, True, 'under'),
        ]:
            with self.subTest(weight=weight):
                self.set_equity_weight(weight)
                result = self.value()
                equity = self.by_asset(result)[self.assets[0].pk]
                self.assertEqual(result['rebalance_allowed'], allowed)
                self.assertEqual(result['recommend_rebalancing'], recommended)
                self.assertEqual(equity['band'], band)
                self.assertEqual(equity['direction'], {'near': 'Near target', 'over': 'Overweight', 'under': 'Underweight'}[band])
                self.assertEqual(equity['drift'], Decimal(weight) - Decimal('50'))

    def test_missing_price_blocks_complete_valuation_and_names_instrument(self):
        TradePrice.objects.filter(instrument=self.holdings[1].instrument).delete()
        result = self.value()
        self.assertEqual(result['status'], 'missing_prices')
        self.assertIsNone(result['total_market_value'])
        self.assertEqual(result['allocations'], [])
        self.assertEqual(result['missing_instruments'], ['Valuation instrument 1'])
        self.assertFalse(result['can_compare'])
        self.assertFalse(result['rebalance_allowed'])

    def test_empty_portfolio_and_zero_total(self):
        result = portfolio_allocation_valuation(self.other_portfolio, as_of=TODAY)
        self.assertEqual(result['status'], 'empty')
        Holding.objects.filter(portfolio=self.portfolio).update(quantity=0)
        result = self.value()
        self.assertEqual(result['status'], 'zero_value')
        self.assertEqual(result['total_market_value'], Decimal('0'))
        self.assertEqual(result['allocations'], [])

    def test_missing_and_invalid_targets_do_not_fabricate_drift(self):
        TargetAllocation.objects.filter(portfolio=self.portfolio).delete()
        result = self.value()
        self.assertEqual(result['status'], 'missing_target')
        self.assertEqual(len(result['allocations']), 3)
        self.assertTrue(all(row['drift'] is None for row in result['allocations']))
        TargetAllocation.objects.create(portfolio=self.portfolio, version_number=1,
            asset_class=self.assets[0], target_percentage=50)
        result = self.value()
        self.assertEqual(result['status'], 'invalid_target')
        self.assertFalse(result['can_compare'])
        self.assertFalse(result['recommend_rebalancing'])

    def test_prices_are_refreshed_and_calculations_do_not_write(self):
        with CaptureQueriesContext(connection) as queries:
            first = self.value()
        self.assertTrue(all(query['sql'].lstrip().upper().startswith('SELECT') for query in queries))
        TradePrice.objects.filter(instrument=self.holdings[0].instrument).update(closing_price=20)
        second = self.value()
        self.assertEqual(first['total_market_value'], Decimal('100'))
        self.assertEqual(second['total_market_value'], Decimal('110'))

    @patch('myapp.portfolio_services.timezone.localdate', return_value=TODAY)
    def test_page_contains_chart_comparison_and_disabled_button(self, unused):
        response = self.client.get(reverse('my_portfolio'))
        for text in ['Portfolio Valuation', 'Current asset-class allocation', 'Drift (pp)', 'Near target',
                     'Your portfolio is balanced.', 'drift-near', 'Request rebalancing', 'disabled']:
            self.assertContains(response, text)
        self.assertIn('no-store', response['Cache-Control'])

    @patch('myapp.portfolio_services.timezone.localdate', return_value=TODAY)
    def test_exact_two_point_boundary_is_rendered_as_near_target(self, unused):
        self.set_equity_weight('52')
        response = self.client.get(reverse('my_portfolio'))
        self.assertContains(response, '+2.00')
        self.assertContains(response, '-2.00')
        self.assertContains(response, 'Near target')
        self.assertNotContains(response, 'Overweight')
        self.assertNotContains(response, 'Underweight')

    @patch('myapp.portfolio_services.timezone.localdate', return_value=TODAY)
    def test_page_shows_optional_button_and_warning_colors(self, unused):
        self.set_equity_weight('54')
        response = self.client.get(reverse('my_portfolio'))
        for text in ['optional rebalancing request', 'drift-over', 'drift-under', '+4.00', '-4.00']:
            self.assertContains(response, text)
        self.assertNotContains(response, 'type="submit" disabled')

    @patch('myapp.portfolio_services.timezone.localdate', return_value=TODAY)
    def test_missing_price_page_does_not_show_comparison_chart_or_button(self, unused):
        TradePrice.objects.filter(instrument=self.holdings[1].instrument).delete()
        response = self.client.get(reverse('my_portfolio'))
        self.assertContains(response, 'Complete portfolio valuation is unavailable')
        self.assertContains(response, 'Valuation instrument 1')
        self.assertNotContains(response, 'allocation-chart-title')
        self.assertNotContains(response, 'Request rebalancing')

    @patch('myapp.portfolio_services.timezone.localdate', return_value=TODAY)
    def test_placeholder_is_post_only_authenticated_and_rechecks_eligibility(self, unused):
        url = reverse('sample_rebalance')
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 400)
        self.set_equity_weight('54')
        before = {model: list(model.objects.order_by('pk').values()) for model in [Portfolio, Holding, TradePrice, TargetAllocation]}
        response = self.client.post(url, {'portfolio_id': self.other_portfolio.pk})
        self.assertContains(response, 'No proposal was generated')
        self.assertIn('no-store', response['Cache-Control'])
        for model, snapshot in before.items():
            self.assertEqual(list(model.objects.order_by('pk').values()), snapshot)
        # A later price change must invalidate eligibility at submission time.
        self.set_equity_weight('50')
        self.assertEqual(self.client.post(url).status_code, 400)
        self.client.logout()
        self.assertEqual(self.client.post(url).status_code, 302)

    @patch('myapp.portfolio_services.timezone.localdate', return_value=TODAY)
    def test_placeholder_blocks_missing_prices_and_enforces_csrf(self, unused):
        self.set_equity_weight('54')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('sample_rebalance')).status_code, 403)
        TradePrice.objects.filter(instrument=self.holdings[0].instrument).delete()
        self.assertEqual(self.client.post(reverse('sample_rebalance')).status_code, 400)

    @patch('myapp.portfolio_services.timezone.localdate', return_value=TODAY)
    def test_other_investor_cannot_view_or_rebalance_this_portfolio(self, unused):
        self.client.force_login(self.other)
        response = self.client.get(reverse('my_portfolio'), {'portfolio_id': self.portfolio.pk})
        self.assertEqual(response.context['portfolio'].pk, self.other_portfolio.pk)
        self.assertNotContains(response, 'Valuation instrument 0')
        self.assertEqual(self.client.post(reverse('sample_rebalance'), {'portfolio_id': self.portfolio.pk}).status_code, 400)
        newcomer = get_user_model().objects.create_user(username='unlinked', email='unlinked@example.com')
        self.client.force_login(newcomer)
        self.assertEqual(self.client.post(reverse('sample_rebalance')).status_code, 404)
