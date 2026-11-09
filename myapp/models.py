from decimal import Decimal
from phonenumber_field.modelfields import PhoneNumberField

from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone

ZERO = Decimal('0')
HUNDRED = Decimal('100')


class InvestorSequence(models.Model):
    """A locked singleton row allocates investor numbers independently of deletions."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    last_value = models.PositiveIntegerField(default=0)


class InvestorProfile(models.Model):
    class RiskProfile(models.TextChoices):
        LOW = "LOW", "Low Risk"
        MODERATE = "MODERATE", "Moderate Risk"
        HIGH = "HIGH", "High Risk"

    investor_id = models.CharField(
        max_length=10,
        primary_key=True,
        editable=False
    )
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name='profile')
    phno = PhoneNumberField(null=True, blank=True, region="IN")
    risk_profile = models.CharField(
        max_length=10,
        choices=RiskProfile.choices,
        default=RiskProfile.MODERATE
    )

    class Meta:
        db_table = 'investor_profile'

    def __str__(self):
        return self.investor_id

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._original_investor_id = instance.pk
        return instance

    def save(self, *args, **kwargs):
        using = kwargs.get('using') or self._state.db or 'default'
        if not self._state.adding and self.pk != getattr(self, '_original_investor_id', self.pk):
            raise ValidationError('Investor IDs cannot be changed.')
        existing = type(self).objects.using(using).filter(user_id=self.user_id).first()
        if existing and existing.pk != self.pk:
            raise ValidationError('Investor IDs cannot be changed.')
        if not self._state.adding:
            return super().save(*args, **kwargs)
        with transaction.atomic(using=using):
            sequence = InvestorSequence.objects.using(using).select_for_update().get(pk=1)
            if self.pk:
                raise ValidationError('Investor IDs are allocated automatically.')
            if sequence.last_value >= 999999:
                raise ValidationError('Investor ID sequence exhausted.')
            sequence.last_value += 1
            sequence.save(using=using, update_fields=['last_value'])
            self.investor_id = f'INV-{sequence.last_value:06d}'
            result = super().save(*args, **kwargs)
            self._original_investor_id = self.pk
            return result


class Portfolio(models.Model):
    portfolio_id = models.CharField(
        max_length=18,
        primary_key=True,
        editable=False
    )
    investor = models.OneToOneField(InvestorProfile, on_delete=models.PROTECT, related_name='portfolio')
    portfolio_name = models.CharField(max_length=100)
    cash_balance = models.DecimalField(max_digits=20, decimal_places=4, default=ZERO,
                                       validators=[MinValueValidator(ZERO)])
    current_allocation_version = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portfolio'
        constraints = [models.CheckConstraint(check=Q(cash_balance__gte=0), name='portfolio_cash_nonneg')]

    def __str__(self):
        return self.portfolio_name


class AssetClass(models.Model):
    assest_class_id = models.CharField(
        max_length=10,
        primary_key=True,
        editable=False
    )
    name = models.CharField(max_length=100)
    
    class Meta:
        db_table = 'asset_class'

    def __str__(self):
        return f'{self.name}'


class Instrument(models.Model):
    instrument_id = models.CharField(
        max_length=10,
        primary_key=True,
        editable=False
    )
    symbol = models.CharField(max_length=30)
    name = models.CharField(max_length=100)
    asset_class = models.ForeignKey(AssetClass, on_delete=models.PROTECT, related_name='instruments')
    exchange = models.CharField(max_length=30)
    currency = models.CharField(max_length=3)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'instrument'
        constraints = [models.UniqueConstraint(fields=['symbol', 'exchange'], name='uq_instrument_symbol_exchange')]

    def __str__(self):
        return f'{self.symbol} ({self.exchange})'


class Holding(models.Model):
    holding_id = models.CharField(
        max_length=34,
        primary_key=True,
        editable=False
    )
    portfolio = models.ForeignKey(Portfolio, on_delete=models.PROTECT, related_name='holdings')
    instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name='holdings')
    quantity = models.DecimalField(max_digits=20, decimal_places=8, validators=[MinValueValidator(ZERO)])
    average_cost = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True,
                                       validators=[MinValueValidator(ZERO)])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'holding'
        constraints = [
            models.UniqueConstraint(fields=['portfolio', 'instrument'], name='uq_holding_portfolio_instrument'),
            models.CheckConstraint(check=Q(quantity__gte=0), name='holding_quantity_nonneg'),
            models.CheckConstraint(check=Q(average_cost__isnull=True) | Q(average_cost__gte=0), name='holding_cost_nonneg'),
        ]


class TargetAllocation(models.Model):
    target_id = models.BigAutoField(primary_key=True)
    portfolio = models.ForeignKey(Portfolio, on_delete=models.PROTECT, related_name='allocation_versions')
    version_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    asset_class = models.ForeignKey(AssetClass, on_delete=models.PROTECT, related_name='target_allocations')
    target_percentage = models.DecimalField(max_digits=7, decimal_places=4,
                                            validators=[MinValueValidator(ZERO), MaxValueValidator(HUNDRED)])

    class Meta:
        db_table = 'target_allocation'
        constraints = [
            models.UniqueConstraint(fields=['portfolio', 'version_number', 'asset_class'], name='uq_target_version_instrument'),
            models.CheckConstraint(check=Q(target_percentage__gte=0) & Q(target_percentage__lte=100), name='target_percent_range'),
        ]


# class TradingCalendar(models.Model):
#     # Logical PK = (market_code, session_date); surrogate PK for Django compatibility.
#     id = models.BigAutoField(primary_key=True)
#     market_code = models.CharField(max_length=30)
#     session_date = models.DateField()
#     is_trading_day = models.BooleanField(default=True)

#     class Meta:
#         db_table = 'trading_calendar'
#         constraints = [models.UniqueConstraint(fields=['market_code', 'session_date'], name='uq_market_session_date')]
#         indexes = [models.Index(fields=['market_code', '-session_date'], name='idx_market_session_desc')]


class TradePrice(models.Model):
    price_id = models.BigAutoField(primary_key=True)
    instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name='daily_prices')
    price_date = models.DateField()
    closing_price = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True,
                                        validators=[MinValueValidator(Decimal('0.000001'))])
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = 'trade_prices'
        constraints = [
            models.UniqueConstraint(fields=['instrument', 'price_date'], name='uq_price_instrument_date'),
            models.CheckConstraint(check=Q(closing_price__isnull=True) | Q(closing_price__gt=0), name='price_null_or_positive'),
        ]
        indexes = [models.Index(fields=['instrument', '-price_date'], name='idx_price_instrument_date')]


# class FeeSchedule(models.Model):
#     class FeeType(models.TextChoices):
#         FLAT = 'FLAT', 'Flat'
#         PERCENTAGE = 'PERCENTAGE', 'Percentage'

#     fee_schedule_id = models.BigAutoField(primary_key=True)
#     name = models.CharField(max_length=100)
#     fee_type = models.CharField(max_length=16, choices=FeeType.choices)
#     fee_value = models.DecimalField(max_digits=18, decimal_places=6, validators=[MinValueValidator(ZERO)])
#     minimum_fee = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO,
#                                       validators=[MinValueValidator(ZERO)])
#     maximum_fee = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
#     effective_from = models.DateTimeField()
#     effective_to = models.DateTimeField(null=True, blank=True)

#     class Meta:
#         db_table = 'fee_schedule'
#         constraints = [
#             models.CheckConstraint(condition=Q(fee_value__gte=0), name='fee_value_nonneg'),
#             models.CheckConstraint(condition=Q(minimum_fee__gte=0), name='fee_min_nonneg'),
#             models.CheckConstraint(condition=Q(maximum_fee__isnull=True) | Q(maximum_fee__gte=F('minimum_fee')), name='fee_max_gte_min'),
#             models.CheckConstraint(condition=Q(effective_to__isnull=True) | Q(effective_to__gt=F('effective_from')), name='fee_valid_dates'),
#         ]


# class PortfolioConstraint(models.Model):
#     constraint_id = models.BigAutoField(primary_key=True)
#     portfolio = models.ForeignKey(Portfolio, on_delete=models.PROTECT, related_name='portfolio_constraints')
#     instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name='portfolio_constraints',
#                                    null=True, blank=True)
#     constraint_type = models.CharField(max_length=50)
#     constraint_value = models.DecimalField(max_digits=20, decimal_places=6)
#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(default=timezone.now, editable=False)

#     class Meta:
#         db_table = 'portfolio_constraint'


# class RebalanceProposal(models.Model):
#     class Status(models.TextChoices):
#         PENDING = 'PENDING', 'Pending'
#         APPROVED = 'APPROVED', 'Approved'
#         REJECTED = 'REJECTED', 'Rejected'
#         OUTDATED = 'OUTDATED', 'Outdated'

#     proposal_id = models.CharField(
#         max_length=14,
#         primary_key=True,
#         editable=False
#     )
#     portfolio = models.ForeignKey(Portfolio, on_delete=models.PROTECT, related_name='rebalance_proposals')
#     allocation_version = models.ForeignKey(TargetAllocationVersion, on_delete=models.PROTECT,
#                                            related_name='rebalance_proposals')
#     status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
#     portfolio_value = models.DecimalField(max_digits=20, decimal_places=4, validators=[MinValueValidator(ZERO)])
#     starting_cash = models.DecimalField(max_digits=20, decimal_places=4, validators=[MinValueValidator(ZERO)])
#     estimated_total_fees = models.DecimalField(max_digits=20, decimal_places=4,
#                                                validators=[MinValueValidator(ZERO)])
#     estimated_cash_after = models.DecimalField(max_digits=20, decimal_places=4)
#     created_at = models.DateTimeField(default=timezone.now, editable=False)
#     expires_at = models.DateTimeField()
#     reviewed_at = models.DateTimeField(null=True, blank=True)

#     class Meta:
#         db_table = 'rebalance_proposal'
#         constraints = [
#             models.CheckConstraint(condition=Q(portfolio_value__gte=0), name='proposal_value_nonneg'),
#             models.CheckConstraint(condition=Q(starting_cash__gte=0), name='proposal_start_cash_nonneg'),
#             models.CheckConstraint(condition=Q(estimated_total_fees__gte=0), name='proposal_fees_nonneg'),
#             models.CheckConstraint(condition=Q(expires_at__gt=F('created_at')), name='proposal_expires_after_created'),
#         ]
#         indexes = [models.Index(fields=['portfolio', 'status'], name='idx_proposal_port_status')]


# class Trade(models.Model):
#     class Side(models.TextChoices):
#         BUY = 'BUY', 'Buy'
#         SELL = 'SELL', 'Sell'

#     trade_id = models.BigAutoField(primary_key=True)
#     proposal = models.ForeignKey(RebalanceProposal, on_delete=models.PROTECT, related_name='trades')
#     instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name='proposed_trades')
#     fee_schedule = models.ForeignKey(FeeSchedule, on_delete=models.PROTECT, related_name='trades',
#                                      null=True, blank=True)
#     side = models.CharField(max_length=4, choices=Side.choices)
#     quantity = models.DecimalField(max_digits=20, decimal_places=8,
#                                    validators=[MinValueValidator(Decimal('0.00000001'))])
#     estimated_price = models.DecimalField(max_digits=20, decimal_places=6,
#                                           validators=[MinValueValidator(Decimal('0.000001'))])
#     estimated_value = models.DecimalField(max_digits=20, decimal_places=4, validators=[MinValueValidator(ZERO)])
#     estimated_fee = models.DecimalField(max_digits=20, decimal_places=4, validators=[MinValueValidator(ZERO)])

#     class Meta:
#         db_table = 'trade'
#         constraints = [
#             models.CheckConstraint(condition=Q(quantity__gt=0), name='trade_quantity_positive'),
#             models.CheckConstraint(condition=Q(estimated_price__gt=0), name='trade_price_positive'),
#             models.CheckConstraint(condition=Q(estimated_value__gte=0), name='trade_value_nonneg'),
#             models.CheckConstraint(condition=Q(estimated_fee__gte=0), name='trade_fee_nonneg'),
#         ]


# class ProposalHoldingSnapshot(models.Model):
#     snapshot_id = models.BigAutoField(primary_key=True)
#     proposal = models.ForeignKey(RebalanceProposal, on_delete=models.PROTECT, related_name='holding_snapshots')
#     instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT, related_name='proposal_snapshots')
#     price = models.ForeignKey(TradePrice, on_delete=models.PROTECT, related_name='proposal_snapshots')
#     quantity = models.DecimalField(max_digits=20, decimal_places=8, validators=[MinValueValidator(ZERO)])
#     price_used = models.DecimalField(max_digits=20, decimal_places=6,
#                                      validators=[MinValueValidator(Decimal('0.000001'))])
#     price_date = models.DateField()
#     market_value = models.DecimalField(max_digits=20, decimal_places=4, validators=[MinValueValidator(ZERO)])

#     class Meta:
#         db_table = 'proposal_holding_snapshot'
#         constraints = [
#             models.UniqueConstraint(fields=['proposal', 'instrument'], name='uq_snapshot_proposal_instrument'),
#             models.CheckConstraint(condition=Q(quantity__gte=0), name='snapshot_quantity_nonneg'),
#             models.CheckConstraint(condition=Q(price_used__gt=0), name='snapshot_price_positive'),
#             models.CheckConstraint(condition=Q(market_value__gte=0), name='snapshot_value_nonneg'),
#         ]


# class ProposalConstraintSnapshot(models.Model):
#     snapshot_id = models.BigAutoField(primary_key=True)
#     proposal = models.ForeignKey(RebalanceProposal, on_delete=models.PROTECT, related_name='constraint_snapshots')
#     constraint = models.ForeignKey(PortfolioConstraint, on_delete=models.PROTECT,
#                                    related_name='proposal_snapshots', null=True, blank=True)
#     constraint_type = models.CharField(max_length=50)
#     instrument = models.ForeignKey(Instrument, on_delete=models.PROTECT,
#                                    related_name='constraint_snapshots', null=True, blank=True)
#     constraint_value = models.DecimalField(max_digits=20, decimal_places=6)

#     class Meta:
#         db_table = 'proposal_constraint_snapshot'
