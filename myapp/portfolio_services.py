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


def portfolio_allocation_valuation(portfolio, *, valuation=None, as_of=None):
    """Calculate a read-only allocation comparison; never compare partial valuations."""
    valuation = valuation if valuation is not None else portfolio_valuation(portfolio, as_of=as_of)
    result = {
        'status': 'unavailable', 'message': '', 'allocations': [],
        'total_market_value': None, 'can_compare': False,
        'recommend_rebalancing': False, 'rebalance_allowed': False,
        'missing_instruments': [holding.instrument.name for holding in valuation['holdings']
                                if holding.latest_price is None],
        'target_version': portfolio.current_allocation_version,
    }
    if result['missing_instruments']:
        result.update(status='missing_prices', message='Complete portfolio valuation is unavailable because some instruments have no valid historical closing price.')
        return result
    if not valuation['holdings']:
        result.update(status='empty', message='Your portfolio has no holdings to value.')
        return result

    total = valuation['total_market_value']
    result['total_market_value'] = total
    if total == 0:
        result.update(status='zero_value', message='Your portfolio market value is zero. Allocation percentages cannot be calculated.')
        return result

    assets = list(AssetClass.objects.order_by('name', 'pk'))
    targets = list(TargetAllocation.objects.filter(
        portfolio=portfolio, version_number=portfolio.current_allocation_version,
    ).values('asset_class_id', 'target_percentage'))
    target_rows = [{'asset_class': row['asset_class_id'], 'target_percentage': row['target_percentage']} for row in targets]
    targets_valid = False
    if not target_rows:
        result.update(status='missing_target', message='Set your target allocation to compare current weights and drift.')
    else:
        try:
            validate_allocations(target_rows, [asset.pk for asset in assets])
        except ValidationError:
            result.update(status='invalid_target', message='Your latest target allocation is incomplete or invalid. Update it before comparing drift.')
        else:
            targets_valid = True
            result.update(status='ready', can_compare=True)

    target_by_asset = {row['asset_class']: row['target_percentage'] for row in target_rows}
    palette = ('#285c49', '#5485ad', '#c58b3d', '#8b73a4', '#7d9560', '#b36265', '#338b8a', '#8b7350')
    with localcontext() as context:
        context.prec = 64
        values = {asset.pk: Decimal('0') for asset in assets}
        for holding in valuation['holdings']:
            asset_id = holding.instrument.asset_class_id
            values[asset_id] += holding.market_value
        offset = Decimal('0')

        for index, asset in enumerate(assets):
            percentage = round(values[asset.pk] / total * Decimal('100'), 2)
            target = target_by_asset[asset.pk] if targets_valid else None
            drift = percentage - target if targets_valid else None
            band = 'near' if drift is None or abs(drift) <= Decimal('2') else ('over' if drift > 0 else 'under')
            direction = None if drift is None else {
                'near': 'Near target', 'over': 'Overweight', 'under': 'Underweight',
            }[band]
            result['allocations'].append({
                'asset_class': asset, 'market_value': values[asset.pk], 'current_percentage': percentage,
                'target_percentage': target, 'drift': drift, 'band': band, 'direction': direction,
                'color': palette[index % len(palette)], 'chart_gap': Decimal('100') - percentage,
                'chart_offset': -offset,
            })
            offset += percentage
            if drift is not None:
                result['rebalance_allowed'] |= abs(drift) > Decimal('2')
                result['recommend_rebalancing'] |= abs(drift) > Decimal('5')
    if targets_valid:
        result['message'] = ('Consider rebalancing: Some asset class exceeds the ±5 percentage-point safe limit.'
                             if result['recommend_rebalancing'] else
                             'Your portfolio is balanced. No rebalancing is currently required.')
    return result


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
