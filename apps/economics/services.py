from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.marketplace.models import MarketplaceMaterial
from apps.wallet.models import Wallet, WalletTransaction
from apps.waste.models import WasteCategory, WasteReport

from .models import (
    CollectorBonus,
    CollectorWallet,
    CollectorWalletTransaction,
    EconomicPolicy,
    EconomicSettlement,
    MaterialRate,
)

MONEY_QUANTUM = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SettlementResult:
    settlement: EconomicSettlement
    customer_transaction: WalletTransaction
    collector_transaction: CollectorWalletTransaction
    marketplace_material: MarketplaceMaterial


def _quantity(collection, category):
    if category.reward_unit == WasteCategory.RewardUnit.PIECE:
        if not collection.actual_piece_count or collection.actual_piece_count <= 0:
            raise ValidationError("Verified piece quantity must be greater than zero.")
        return Decimal(collection.actual_piece_count), WasteCategory.RewardUnit.PIECE, MarketplaceMaterial.Unit.PIECE
    if not collection.actual_weight or collection.actual_weight <= 0:
        raise ValidationError("Verified weight must be greater than zero.")
    quantity = collection.actual_weight
    if collection.weight_unit == WasteReport.WeightUnit.GRAMS:
        quantity = quantity / Decimal("1000")
    return quantity, WasteCategory.RewardUnit.KILOGRAM, MarketplaceMaterial.Unit.KILOGRAM


@transaction.atomic
def settle_collection(collection):
    collection = type(collection).objects.select_for_update().get(pk=collection.pk)
    collection = type(collection).objects.select_related(
        "waste_report__customer", "waste_report__category", "collector",
    ).get(pk=collection.pk)
    if hasattr(collection, "economic_settlement"):
        raise ValidationError("This collection has already been settled.")
    if collection.status != collection.Status.ACCEPTED:
        raise ValidationError("Only accepted collections can be settled.")
    if collection.collector_id is None:
        raise ValidationError("A collector is required for settlement.")

    now = timezone.now()
    category = collection.waste_report.category
    policy = EconomicPolicy.applicable(category.pk, now)
    material_rate = MaterialRate.objects.select_for_update().filter(category=category, active=True, effective_from__lte=now).first()
    if policy is None or material_rate is None:
        raise ValidationError("Configure an active economic policy and material rate before completing this collection.")

    quantity, unit, marketplace_unit = _quantity(collection, category)
    gross = money(quantity * material_rate.rate_per_unit)
    customer_allocation = money(gross * policy.customer_percent / Decimal("100"))
    collector_base = money(gross * policy.collector_percent / Decimal("100"))
    operations = money(gross * policy.operations_percent / Decimal("100"))
    customer_tokens = money(customer_allocation / material_rate.rate_per_unit * category.token_rate)
    bonus = CollectorBonus.applicable(now)
    bonus_amount = bonus.amount if bonus else Decimal("0.00")
    total_collector = money(collector_base + bonus_amount)

    customer_wallet, _ = Wallet.objects.get_or_create(user=collection.waste_report.customer)
    customer_wallet = Wallet.objects.select_for_update().get(pk=customer_wallet.pk)
    collector_wallet, _ = CollectorWallet.objects.get_or_create(user=collection.collector)
    collector_wallet = CollectorWallet.objects.select_for_update().get(pk=collector_wallet.pk)
    settlement = EconomicSettlement.objects.create(
        collection=collection, category=category, policy=policy, material_rate=material_rate, bonus=bonus,
        material=category.name, unit=unit, verified_quantity=quantity, material_rate_value=material_rate.rate_per_unit,
        gross_value=gross, customer_percent=policy.customer_percent, collector_percent=policy.collector_percent,
        operations_percent=policy.operations_percent, customer_allocation=customer_allocation,
        customer_tokens=customer_tokens, collector_base_earning=collector_base, operations_allocation=operations,
        bonus_amount=bonus_amount, total_collector_earning=total_collector,
    )
    customer_transaction = WalletTransaction.objects.create(
        wallet=customer_wallet, transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD,
        amount=customer_tokens, description=f"Collection reward for {category.name}",
        reference=f"settlement-customer-{collection.pk}", collection=collection,
        collection_reward_unit=unit, collection_reward_quantity=quantity,
        collection_reward_rate=category.token_rate, collection_reward_material=category.name,
    )
    collector_transaction = CollectorWalletTransaction.objects.create(
        collector_wallet=collector_wallet, transaction_type=CollectorWalletTransaction.TransactionType.COLLECTION_EARNING,
        amount=collector_base, description=f"Collection earning for {category.name}",
        reference=f"settlement-collector-{collection.pk}", collection=collection,
    )
    if bonus:
        CollectorWalletTransaction.objects.create(
            collector_wallet=collector_wallet, transaction_type=CollectorWalletTransaction.TransactionType.BONUS,
            amount=bonus_amount, description=bonus.name, reference=f"settlement-bonus-{collection.pk}", collection=collection,
        )
    material_quantity = quantity
    marketplace_material = MarketplaceMaterial.objects.create(
        name=category.name, description="", category=category, available_quantity=material_quantity,
        unit=marketplace_unit, active=False, preparation_status=MarketplaceMaterial.PreparationStatus.READY,
        source_collection=collection,
    )
    collection.status = collection.Status.COMPLETED
    collection.completed_at = now
    collection.save(update_fields=["status", "completed_at", "updated_at"])
    report = collection.waste_report
    report.status = WasteReport.Status.COLLECTED
    report.save(update_fields=["status", "updated_at"])
    return SettlementResult(settlement, customer_transaction, collector_transaction, marketplace_material)


def collector_wallet_for(user):
    wallet, _ = CollectorWallet.objects.get_or_create(user=user)
    return wallet


@transaction.atomic
def request_collector_payout(*, collector, amount, payout_method, provider_name, destination):
    from .models import CollectorPayout, EconomicSetting
    settings_record = EconomicSetting.current()
    if amount < settings_record.collector_payout_min_tzs:
        raise ValidationError(f"Collector payouts require at least TZS {settings_record.collector_payout_min_tzs}.")
    wallet = CollectorWallet.objects.select_for_update().get_or_create(user=collector)[0]
    wallet = CollectorWallet.objects.select_for_update().get(pk=wallet.pk)
    if wallet.balance < amount:
        raise ValidationError("Insufficient collector wallet balance.")
    payout = CollectorPayout.objects.create(
        collector=collector, amount=amount, payout_method=payout_method,
        provider_name=provider_name, destination=destination,
    )
    CollectorWalletTransaction.objects.create(
        collector_wallet=wallet, transaction_type=CollectorWalletTransaction.TransactionType.PAYOUT,
        amount=-amount, description=f"Collector payout request #{payout.pk}",
        payout=payout, reference=f"collector-payout-{payout.pk}",
    )
    return payout
