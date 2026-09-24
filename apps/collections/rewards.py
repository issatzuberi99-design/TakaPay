from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from apps.waste.models import WasteCategory, WasteReport


@dataclass(frozen=True)
class CollectionReward:
    amount: Decimal
    unit: str
    quantity: Decimal
    rate: Decimal
    material: str


def weight_to_kilograms(weight, unit):
    if unit == WasteReport.WeightUnit.KILOGRAMS:
        return weight
    if unit == WasteReport.WeightUnit.GRAMS:
        return weight / Decimal("1000")
    raise ValidationError("Unsupported collection weight unit.")


def calculate_collection_reward(collection, category):
    """Calculate and snapshot a collection's verified quantity against the current rate."""
    rate = category.token_rate
    if rate is None or rate <= 0:
        raise ValidationError("This material has no positive token rate. Ask an administrator to configure its rate before completing the collection.")

    if category.reward_unit == WasteCategory.RewardUnit.KILOGRAM:
        if collection.actual_weight is None or collection.actual_weight <= 0:
            raise ValidationError("Verified weight must be greater than zero.")
        quantity = weight_to_kilograms(collection.actual_weight, collection.weight_unit)
        unit = WasteCategory.RewardUnit.KILOGRAM
    elif category.reward_unit == WasteCategory.RewardUnit.PIECE:
        if collection.actual_piece_count is None or collection.actual_piece_count <= 0:
            raise ValidationError("Verified piece quantity must be greater than zero.")
        quantity = Decimal(collection.actual_piece_count)
        unit = WasteCategory.RewardUnit.PIECE
    else:
        raise ValidationError("Unsupported reward unit for this waste category.")

    amount = (quantity * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return CollectionReward(amount=amount, unit=unit, quantity=quantity, rate=rate, material=category.name)
