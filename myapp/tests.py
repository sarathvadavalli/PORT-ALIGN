from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from .forms import RegistrationForm
from .models import InvestorProfile, InvestorSequence

User = get_user_model()
PASSWORD = 'A-long-unique-password!529'


def data(**overrides):
    values = dict(username='investor', email='investor@example.com', password=PASSWORD,
                  first_name='Alex', last_name='Patel', phno='')
    values.update(overrides)
    return values


def create_account(**overrides):
    form = RegistrationForm(data(**overrides))
    assert form.is_valid(), form.errors
    return form.save()


class AuthenticationTests(TestCase):
    def test_registration(self):
        self.assertRedirects(self.client.post(reverse('register'), data()), reverse('login'))
        user = User.objects.get(username='investor')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertRegex(user.profile.pk, r'^INV-\d{6}$')
        self.assertEqual(user.profile.risk_profile, 'MODERATE')
        self.assertFalse(user.profile.phno)

    def test_required_fields(self):
        response = self.client.post(reverse('register'), {})
        self.assertIn('username', response.context['form'].errors)
        for field in ['username', 'email', 'password', 'first_name', 'last_name']:
            with self.subTest(field=field):
                form = RegistrationForm(data(**{field: ''}))
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_invalid_input(self):
        for field, value in [('username', 'bad name'), ('email', 'bad'), ('phno', '123'), ('password', '123')]:
            with self.subTest(field=field):
                form = RegistrationForm(data(**{field: value}))
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_duplicates(self):
        create_account()
        form = RegistrationForm(data(username='INVESTOR', email='INVESTOR@example.com'))
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertIn('email', form.errors)

    def test_database_uniqueness(self):
        user = create_account()
        for values in [dict(username='different', email=user.email), dict(username='different', email=user.email.upper()),
                       dict(username=user.username, email='other@example.com'), dict(username=user.username.upper(), email='other@example.com')]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                User.objects.create(**values)

    def test_registration_rolls_back(self):
        before = InvestorSequence.objects.get(pk=1).last_value
        with patch.object(InvestorProfile, 'save', side_effect=IntegrityError('failure')):
            response = self.client.post(reverse('register'), data())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(InvestorSequence.objects.get(pk=1).last_value, before)

    def test_sequence_update_rolls_back_with_registration(self):
        before = InvestorSequence.objects.get(pk=1).last_value
        original_save = InvestorSequence.save

        def fail_after_update(instance, *args, **kwargs):
            original_save(instance, *args, **kwargs)
            raise IntegrityError('failure after sequence update')

        with patch.object(InvestorSequence, 'save', fail_after_update):
            response = self.client.post(reverse('register'), data())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(InvestorProfile.objects.count(), 0)
        self.assertEqual(InvestorSequence.objects.get(pk=1).last_value, before)

    def test_availability_and_final_recheck(self):
        url = reverse('availability')
        self.assertTrue(self.client.get(url, {'field': 'username', 'value': 'investor'}).json()['available'])
        create_account()
        for field, value, available in [('username', 'INVESTOR', False), ('email', 'investor@example.com', False),
                                       ('username', 'new', True), ('email', 'new@example.com', True), ('email', 'bad', False)]:
            result = self.client.get(url, {'field': field, 'value': value}).json()
            self.assertEqual(result['field'], field)
            self.assertEqual(result['available'], available)
        self.assertEqual(self.client.get(url, {'field': 'password'}).status_code, 400)
        self.assertEqual(self.client.post(url).status_code, 405)
        response = self.client.post(reverse('register'), data(email='new@example.com'))
        self.assertIn('username', response.context['form'].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_availability_uses_registration_validation_for_each_field(self):
        for field, value in [('username', ''), ('username', '   '), ('username', 'éclair'),
                             ('username', '_alex'), ('username', 'alex-'), ('username', 'alex.name'),
                             ('username', 'alex__name'), ('username', 'alex--name'),
                             ('username', 'alex_-name'), ('username', 'alex-_name'),
                             ('email', ''), ('email', 'not-an-email')]:
            with self.subTest(field=field, value=value):
                form = RegistrationForm(data(**{field: value}))
                self.assertFalse(form.is_valid())
                response = self.client.get(reverse('availability'), {'field': field, 'value': value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {'field': field, 'available': False,
                                                   'message': form.errors[field][0]})
        for field, value in [('username', ' alex_name-1 '), ('email', ' NEW@EXAMPLE.COM ')]:
            with self.subTest(field=field, value=value):
                result = self.client.get(reverse('availability'), {'field': field, 'value': value}).json()
                self.assertTrue(result['available'])
        self.assertEqual(User.objects.count(), 0)

    def test_login_identifiers(self):
        user = create_account()
        for identifier in ['investor', 'INVESTOR@example.com']:
            self.client.logout()
            response = self.client.post(reverse('login') + '?next=https://example.com', {'username': identifier, 'password': PASSWORD})
            self.assertRedirects(response, reverse('dashboard'))
            self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_generic_login_errors(self):
        user = create_account()
        errors = []
        for identifier in ['investor', 'missing', 'missing@example.com']:
            response = self.client.post(reverse('login'), {'username': identifier, 'password': 'wrong'})
            errors.append(list(response.context['form'].non_field_errors()))
            self.assertNotIn('_auth_user_id', self.client.session)
        user.is_active = False
        user.save()
        response = self.client.post(reverse('login'), {'username': 'investor', 'password': PASSWORD})
        errors.append(list(response.context['form'].non_field_errors()))
        self.assertTrue(all(error == errors[0] for error in errors))

    def test_access_and_logout(self):
        for page in ['dashboard', 'profile']:
            self.assertRedirects(self.client.get(reverse(page)), reverse('login') + '?next=' + reverse(page))
        self.client.force_login(create_account())
        for page in ['dashboard', 'profile']:
            response = self.client.get(reverse(page))
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response.headers['Cache-Control'])
            self.assertContains(response, 'myapp/protected-history.js')
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertNotContains(self.client.get(reverse('login')), 'myapp/protected-history.js')
        for page in ['dashboard', 'profile']:
            response = self.client.get(reverse(page))
            self.assertEqual(response.status_code, 302)
            self.assertIn('no-store', response.headers['Cache-Control'])

    def test_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for page in ['register', 'login']:
            self.assertEqual(client.post(reverse(page), data()).status_code, 403)
        client.force_login(create_account())
        for page in ['profile', 'logout']:
            self.assertEqual(client.post(reverse(page), {}).status_code, 403)

    def test_registration_page(self):
        self.assertContains(self.client.get(reverse('register')), 'myapp/availability.js')


class ProfileTests(TestCase):
    def setUp(self):
        self.user = create_account()
        self.other = create_account(username='other', email='other@example.com')
        self.client.force_login(self.user)

    def test_display(self):
        response = self.client.get(reverse('profile'))
        for value in ['investor', 'investor@example.com', 'Alex', 'Patel', 'MODERATE', self.user.profile.pk]:
            self.assertContains(response, value)
        self.assertNotContains(response, 'other@example.com')

    def test_update_and_ownership(self):
        identifier = self.user.profile.pk
        response = self.client.post(reverse('profile'), data(username='updated', email='UPDATED@example.com',
            first_name='New', last_name='Name', phno='+919876543210', risk_profile='HIGH',
            user_id=self.other.pk, investor_id=self.other.profile.pk, is_staff=True))
        self.assertRedirects(response, reverse('profile'))
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'updated')
        self.assertEqual(self.user.email, 'updated@example.com')
        self.assertEqual(self.user.first_name, 'New')
        self.assertEqual(self.user.last_name, 'Name')
        self.assertEqual(str(self.user.profile.phno), '+919876543210')
        self.assertEqual(self.user.profile.risk_profile, 'HIGH')
        self.assertEqual(self.user.profile.pk, identifier)
        self.assertFalse(self.user.is_staff)
        self.other.refresh_from_db()
        self.assertEqual(self.other.username, 'other')
        self.assertEqual(self.other.profile.risk_profile, 'MODERATE')

    def test_invalid_updates_preserve_values(self):
        for overrides in [dict(username='other'), dict(email='OTHER@example.com'), dict(risk_profile='UNKNOWN'), dict(phno='123'), dict(first_name='')]:
            values = data(risk_profile='LOW')
            values.update(overrides)
            response = self.client.post(reverse('profile'), values)
            self.assertEqual(response.status_code, 200)
            self.user.refresh_from_db()
            self.assertEqual(self.user.username, 'investor')
            self.assertEqual(self.user.profile.risk_profile, 'MODERATE')

    def test_unchanged_fields(self):
        self.assertRedirects(self.client.post(reverse('profile'), data(risk_profile='LOW')), reverse('profile'))

    def test_missing_and_other_profile(self):
        self.assertEqual(self.client.get(f'/profile/{self.other.profile.pk}/').status_code, 404)
        self.user.profile.delete()
        self.assertEqual(self.client.get(reverse('profile')).status_code, 404)

    def test_immutable_id_and_no_reuse(self):
        profile = self.user.profile
        original = profile.pk
        profile.pk = 'INV-999999'
        with self.assertRaises(ValidationError):
            profile.save()
        self.assertTrue(InvestorProfile.objects.filter(pk=original).exists())
        last_id = self.other.profile.pk
        self.other.profile.delete()
        third = create_account(username='third', email='third@example.com')
        self.assertGreater(int(third.profile.pk[4:]), int(last_id[4:]))

    def test_update_rollback(self):
        with patch.object(InvestorProfile, 'save', side_effect=IntegrityError('failure')):
            response = self.client.post(reverse('profile'), data(first_name='Changed', risk_profile='HIGH'))
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Alex')


class ConcurrentRegistrationTests(TransactionTestCase):
    def setUp(self):
        InvestorSequence.objects.get_or_create(pk=1, defaults={'last_value': 0})

    def test_concurrent_ids(self):
        if connection.vendor != 'mysql':
            self.skipTest('Production row locking is verified on MySQL.')
        barrier = Barrier(2)

        def register(index):
            try:
                barrier.wait(timeout=10)
                return create_account(username=f'user{index}', email=f'user{index}@example.com').profile.pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(register, [1, 2]))
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(InvestorProfile.objects.count(), 2)

    def test_duplicate_race_is_rejected_by_database_without_orphans(self):
        for duplicate_field in ['username', 'email']:
            with self.subTest(field=duplicate_field):
                barrier = Barrier(2)

                def register(index):
                    try:
                        values = dict(username=f'{duplicate_field}{index}', email=f'{duplicate_field}{index}@example.com')
                        values[duplicate_field] = 'shared' if duplicate_field == 'username' else 'shared@example.com'
                        form = RegistrationForm(data(**values))
                        assert form.is_valid(), form.errors
                        barrier.wait(timeout=10)
                        try:
                            form.save()
                            return True
                        except IntegrityError:
                            return False
                    finally:
                        connections.close_all()

                before = User.objects.count()
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(register, [1, 2]))
                self.assertEqual(sorted(results), [False, True])
                self.assertEqual(User.objects.count(), before + 1)
                self.assertEqual(InvestorProfile.objects.count(), before + 1)
