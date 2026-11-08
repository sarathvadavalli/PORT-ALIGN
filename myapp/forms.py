from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from phonenumber_field.formfields import PhoneNumberField

from .models import InvestorProfile

User = get_user_model()


class AccountForm(forms.ModelForm):
    email = forms.EmailField(max_length=254, required=True)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    phno = PhoneNumberField(region='IN', required=False, label='Phone number')

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']

    def clean_username(self):
        value = self.cleaned_data['username']
        if not value.isascii():
            raise ValidationError("Username must contain only ASCII characters")

        if not value[0].isalnum() or not value[-1].isalnum():
            raise ValidationError(
                "Username must start and end with a letter or digit"
            )

        if not all(c.isalnum() or c in "_-" for c in value):
            raise ValidationError(
                "Username can contain only letters, digits, '_' and '-'"
            )

        if "__" in value or "--" in value or "_-" in value or "-_" in value:
            raise ValidationError(
                "Username cannot contain consecutive '_' or '-'"
            )

        if User.objects.filter(username__iexact=value).exclude(pk=self.instance.pk).exists():
            raise ValidationError('This username is already in use.')
        return value

    def clean_email(self):
        value = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise ValidationError('This email address is already in use.')
        return value


class RegistrationForm(AccountForm):
    password = forms.CharField(widget=forms.PasswordInput, strip=False)

    def _post_clean(self):
        super()._post_clean()
        if 'password' in self.cleaned_data:
            try:
                validate_password(self.cleaned_data['password'], self.instance)
            except ValidationError as exc:
                self.add_error('password', exc)

    @transaction.atomic
    def save(self):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.save()
        InvestorProfile.objects.create(user=user, phno=self.cleaned_data['phno'] or None)
        return user


class ProfileForm(AccountForm):
    risk_profile = forms.ChoiceField(choices=InvestorProfile.RiskProfile.choices)

    def __init__(self, *args, profile, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.update(phno=profile.phno, risk_profile=profile.risk_profile)

    @transaction.atomic
    def save(self):
        user = super().save()
        self.profile.phno = self.cleaned_data['phno'] or None
        self.profile.risk_profile = self.cleaned_data['risk_profile']
        self.profile.save(update_fields=['phno', 'risk_profile'])
        return user


class IdentifierAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label='Username or email', max_length=254)

    def clean(self):
        identifier = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if identifier and password:
            # A syntactically valid email is treated as an email identifier.
            try:
                forms.EmailField().clean(identifier)
                lookup = {'email__iexact': identifier}
            except ValidationError:
                lookup = {'username__iexact': identifier}
            matches = list(User.objects.filter(**lookup)[:2])
            if len(matches) == 1:
                self.user_cache = authenticate(self.request, username=matches[0].username, password=password)
            else:
                # Match the expensive password work even for nonexistent accounts.
                User().set_password(password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data
