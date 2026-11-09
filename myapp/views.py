from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db import IntegrityError
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from django.contrib import messages
from django.core.exceptions import ValidationError

from .forms import AccountForm, RegistrationForm, ProfileForm, IdentifierAuthenticationForm
from .models import InvestorProfile, Portfolio, AssetClass, TargetAllocation
from .allocation_forms import AllocationFormSet
from .portfolio_services import portfolio_valuation, save_target_allocation


def duplicate_errors(form):
    found = False
    for field in ('username', 'email'):
        if get_user_model().objects.filter(**{f'{field}__iexact': form.cleaned_data[field]}).exclude(pk=form.instance.pk).exists():
            form.add_error(field, f'This {field} is already in use.')
            found = True
    if not found:
        form.add_error(None, 'The account could not be saved. Please try again.')

# Create your views here.
def home(request):
    return HttpResponse('Project is setup..')


class AccountLoginView(LoginView):
    template_name = 'myapp/login.html'
    authentication_form = IdentifierAuthenticationForm

    def get_success_url(self):
        return '/dashboard/'


class AccountLogoutView(LogoutView):
    next_page = 'login'


@require_http_methods(['GET', 'POST'])
def register(request):
    form = RegistrationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            duplicate_errors(form)
        else:
            return redirect('login')
    return render(request, 'myapp/register.html', {'form': form})


@require_GET
def availability(request):
    field = request.GET.get('field')
    if field not in ('username', 'email'):
        return JsonResponse({'error': 'Choose username or email.'}, status=400)
    form = AccountForm(data={field: request.GET.get('value', '')})
    # Validate this field independently through Django's normal cleaning lifecycle.
    # This populates cleaned_data before calling clean_username()/clean_email().
    form.fields = {field: form.fields[field]}
    if not form.is_valid():
        return JsonResponse({'field': field, 'available': False, 'message': form.errors[field][0]})
    return JsonResponse({'field': field, 'available': True, 'message': 'Available.'})


@never_cache
@login_required
def dashboard(request):
    return render(request, 'myapp/dashboard.html')


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def profile(request):
    investor = get_object_or_404(InvestorProfile, user=request.user)
    form = ProfileForm(request.POST if request.method == 'POST' else None, instance=request.user, profile=investor)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            duplicate_errors(form)
        else:
            return redirect('profile')
    return render(request, 'myapp/profile.html', {'form': form, 'investor': investor})


@never_cache
@login_required
@require_GET
def my_portfolio(request):
    portfolio = Portfolio.objects.filter(investor__user=request.user).first()
    context = {'portfolio': portfolio}
    if portfolio:
        context.update(portfolio_valuation(portfolio))
    return render(request, 'myapp/portfolio.html', context)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def target_allocation(request):
    portfolio = Portfolio.objects.filter(investor__user=request.user).first()
    if portfolio is None:
        return render(request, 'myapp/target_allocation.html', {'portfolio': None})

    asset_classes = list(AssetClass.objects.order_by('name', 'pk'))
    current = dict(TargetAllocation.objects.filter(
        portfolio=portfolio, version_number=portfolio.current_allocation_version,
    ).values_list('asset_class_id', 'target_percentage'))
    
    formset = AllocationFormSet(
        request.POST if request.method == 'POST' else None,
        initial=[{'asset_class': asset.pk, 'target_percentage': current.get(asset.pk, 0)} for asset in asset_classes],
        asset_classes=asset_classes, prefix='allocations',
    )
    if request.method == 'POST' and formset.is_valid():
        try:
            version, changed = save_target_allocation(
                user=request.user, portfolio_id=portfolio.pk, rows=formset.cleaned_data,
            )
        except ValidationError as exc:
            formset._non_form_errors = formset.error_class(exc.messages)
        except IntegrityError:
            formset._non_form_errors = formset.error_class(['The allocation could not be saved. Please reload and try again.'])
        else:
            messages.success(request, f'Target allocation saved as version {version}.' if changed else 'Your target allocation is unchanged. No new version was created.')
            return redirect('target_allocation')
    return render(request, 'myapp/target_allocation.html', {
        'portfolio': portfolio, 'formset': formset, 'asset_classes': asset_classes,
    })
