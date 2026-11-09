from django import forms
from django.forms import BaseFormSet, formset_factory

from .portfolio_services import validate_allocations


class AllocationForm(forms.Form):
    asset_class = forms.ChoiceField(widget=forms.HiddenInput)
    target_percentage = forms.DecimalField(
        min_value=0, max_value=100, max_digits=7, decimal_places=4,
        label='Target percentage', widget=forms.NumberInput(attrs={'step': '0.0001'}),
    )

    def __init__(self, *args, asset_classes, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['asset_class'].choices = [(asset.pk, asset.name) for asset in asset_classes]
        self.asset_name = dict(self.fields['asset_class'].choices).get(self['asset_class'].value(), 'Asset class')


class BaseAllocationFormSet(BaseFormSet):
    def __init__(self, *args, asset_classes, **kwargs):
        self.asset_classes = asset_classes
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        return {**super().get_form_kwargs(index), 'asset_classes': self.asset_classes, 'empty_permitted': False}

    def clean(self):
        super().clean()
        if not self.management_form.is_valid() or any(self.errors):
            return
        validate_allocations([form.cleaned_data for form in self.forms], [asset.pk for asset in self.asset_classes])


AllocationFormSet = formset_factory(AllocationForm, formset=BaseAllocationFormSet, extra=0)
