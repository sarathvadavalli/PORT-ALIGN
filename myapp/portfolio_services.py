"""Read portfolio prices and save complete, serialized allocation snapshots."""
from decimal import Decimal, localcontext

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from .models import AssetClass, Holding, Portfolio, TargetAllocation, TradePrice


def portfolio_valuation(portfolio, *, as_of=None):
    as_of = as_of or timezone.localdate()
    prices = TradePrice.objects.filter(
        instrument_id=OuterRef('instrument_id'), price_date__lte=as_of,
        closing_price__gt=0,
    ).order_by('-price_date', '-price_id')

    holdings = list(Holding.objects.filter(portfolio=portfolio).select_related(
        'instrument__asset_class',
    ).annotate(
        latest_price=Subquery(prices.values('closing_price')[:1]),
        latest_price_date=Subquery(prices.values('price_date')[:1]),
    ).order_by('instrument__name', 'holding_id'))

    with localcontext() as context:
        context.prec = 64
        total = Decimal('0')
        missing = 0
        for holding in holdings:
            holding.market_value = None
            if holding.latest_price is None:
                missing += 1
            else:
                holding.market_value = holding.quantity * holding.latest_price
                total += holding.market_value

    return {'holdings': holdings, 'total_market_value': total,
            'missing_price_count': missing, 'as_of': as_of}


def validate_allocations(rows, asset_ids):
    ids = [row['asset_class'] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValidationError('Each asset class must appear exactly once; duplicates are not allowed.')
    if set(ids) != set(asset_ids):
        raise ValidationError('Submit an allocation for every supported asset class.')
    total = Decimal('0')
    for row in rows:
        value = row['target_percentage']
        if not isinstance(value, Decimal) or not value.is_finite() or not Decimal('0') <= value <= Decimal('100'):
            raise ValidationError('Each percentage must be a valid number between 0 and 100.')
        # Reuse the model's supported decimal precision as well as its validators.
        TargetAllocation._meta.get_field('target_percentage').clean(value, None)
        total += value
    if total != Decimal('100'):
        raise ValidationError(f'Target allocations must total exactly 100%. Current total: {total}%.')


@transaction.atomic
def save_target_allocation(*, user, portfolio_id, rows):
    # Ownership and serialization are checked together; callers cannot select another account.
    portfolio = Portfolio.objects.select_for_update().get(pk=portfolio_id, investor__user=user)
    asset_ids = list(AssetClass.objects.values_list('pk', flat=True))
    validate_allocations(rows, asset_ids)

    current = dict(TargetAllocation.objects.filter(
        portfolio=portfolio, version_number=portfolio.current_allocation_version,
    ).values_list('asset_class_id', 'target_percentage'))

    proposed = {row['asset_class']: row['target_percentage'] for row in rows}
    if current == proposed:
        return portfolio.current_allocation_version, False
        
    next_version = portfolio.current_allocation_version + 1
    TargetAllocation.objects.bulk_create([
        TargetAllocation(portfolio=portfolio, version_number=next_version,
                         asset_class_id=asset_id, target_percentage=percentage)
        for asset_id, percentage in proposed.items()
    ])
    portfolio.current_allocation_version = next_version
    portfolio.save(update_fields=['current_allocation_version', 'updated_at'])
    return next_version, True
