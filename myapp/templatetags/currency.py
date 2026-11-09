from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

from django import template
from django.utils.numberformat import format as format_number

register = template.Library()


@register.filter
def indian_currency(value):
    """Display a rupee amount with Indian grouping and exactly two decimals."""
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            return ''
        with localcontext() as context:
            context.prec = max(64, amount.adjusted() + 4)
            amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return ''
    return '₹' + format_number(amount, decimal_sep='.', decimal_pos=2,
                               grouping=(3, 2, 0), thousand_sep=',',
                               force_grouping=True, use_l10n=False)
