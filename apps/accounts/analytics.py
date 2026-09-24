from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import (
    Case,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.accounts.models import CollectorProfile
from apps.cashout.models import CashOutRequest
from apps.collections.models import CollectionRequest
from apps.marketplace.models import BuyerRequest, MarketplaceMaterial
from apps.rewards.models import Reward, RewardRedemption
from apps.wallet.models import WalletTransaction
from apps.waste.models import WasteCategory, WasteReport


ZERO = Decimal("0.0000")
WEIGHT_FIELD = DecimalField(max_digits=20, decimal_places=4)


def weight_in_kilograms(weight_field, unit_field):
    """Return an ORM expression that converts the project's kg/g values to kilograms."""
    grams = ExpressionWrapper(
        F(weight_field) / Value(Decimal("1000")),
        output_field=WEIGHT_FIELD,
    )
    return Case(
        When(**{unit_field: WasteReport.WeightUnit.GRAMS}, then=grams),
        default=F(weight_field),
        output_field=WEIGHT_FIELD,
    )


def dashboard_context(request):
    periods = {"7": 7, "30": 30, "90": 90, "all": None}
    period = request.GET.get("period", "30")
    if period not in periods:
        period = "30"

    today = timezone.localdate()
    start_date = None
    start_time = None
    if periods[period] is not None:
        start_date = today - timedelta(days=periods[period] - 1)
        start_time = timezone.make_aware(
            datetime.combine(start_date, time.min),
            timezone.get_current_timezone(),
        )

    def since(queryset, field):
        if start_time is not None:
            return queryset.filter(**{f"{field}__gte": start_time})
        return queryset

    weight_field = WEIGHT_FIELD
    report_weight = weight_in_kilograms("estimated_weight", "weight_unit")
    collection_weight = weight_in_kilograms("actual_weight", "weight_unit")

    reports = since(WasteReport.objects.all(), "created_at")
    report_totals = reports.aggregate(
        count=Count("id"),
        estimated_kg=Coalesce(Sum(report_weight), Value(ZERO), output_field=weight_field),
        estimated_pieces=Coalesce(Sum("estimated_piece_count"), Value(ZERO), output_field=weight_field),
    )
    verified_reports = reports.filter(status=WasteReport.Status.VERIFIED)
    verified_weight = verified_reports.aggregate(
        total=Coalesce(Sum(report_weight), Value(ZERO), output_field=weight_field),
    )["total"]

    completed_collections = since(
        CollectionRequest.objects.filter(status=CollectionRequest.Status.COMPLETED),
        "completed_at",
    )
    collection_weight_total = completed_collections.aggregate(
        total=Coalesce(Sum(collection_weight), Value(ZERO), output_field=weight_field),
        pieces=Coalesce(Sum("actual_piece_count"), Value(ZERO), output_field=weight_field),
        count=Count("id"),
        collectors=Count("collector", distinct=True),
    )
    collection_scope = since(CollectionRequest.objects.all(), "created_at")
    collection_counts = {value: 0 for value, _ in CollectionRequest.Status.choices}
    for row in collection_scope.values("status").annotate(count=Count("id")):
        collection_counts[row["status"]] = row["count"]
    total_collection_requests = sum(collection_counts.values())
    completion_rate = (
        (Decimal(collection_counts[CollectionRequest.Status.COMPLETED]) * Decimal("100")
         / Decimal(total_collection_requests)).quantize(Decimal("0.1"))
        if total_collection_requests
        else Decimal("0.0")
    )

    approved_collectors = CollectorProfile.objects.filter(
        verification_status=CollectorProfile.VerificationStatus.APPROVED,
    ).count()

    token_transactions = since(WalletTransaction.objects.all(), "created_at").aggregate(
        issued=Coalesce(
            Sum("amount", filter=Q(transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD)),
            Value(ZERO), output_field=weight_field,
        ),
        redeemed=Coalesce(
            Sum("amount", filter=Q(transaction_type=WalletTransaction.TransactionType.REWARD_REDEMPTION)),
            Value(ZERO), output_field=weight_field,
        ),
        cashout=Coalesce(
            Sum("amount", filter=Q(transaction_type=WalletTransaction.TransactionType.CASHOUT)),
            Value(ZERO), output_field=weight_field,
        ),
        adjustments=Coalesce(
            Sum("amount", filter=Q(transaction_type=WalletTransaction.TransactionType.ADJUSTMENT)),
            Value(ZERO), output_field=weight_field,
        ),
        kg_rewards=Coalesce(
            Sum("amount", filter=Q(
                transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD,
                collection_reward_unit="kg",
            )), Value(ZERO), output_field=weight_field,
        ),
        piece_rewards=Coalesce(
            Sum("amount", filter=Q(
                transaction_type=WalletTransaction.TransactionType.COLLECTION_REWARD,
                collection_reward_unit="piece",
            )), Value(ZERO), output_field=weight_field,
        ),
    )

    cashout_scope = since(CashOutRequest.objects.all(), "requested_at")
    cashout_counts = {value: 0 for value, _ in CashOutRequest.Status.choices}
    for row in cashout_scope.values("status").annotate(count=Count("id")):
        cashout_counts[row["status"]] = row["count"]
    cashout_totals = cashout_scope.aggregate(
        tokens=Coalesce(Sum("token_amount"), Value(ZERO), output_field=weight_field),
        money=Coalesce(Sum("money_amount"), Value(ZERO), output_field=weight_field),
    )
    pending_cashouts = CashOutRequest.objects.filter(status=CashOutRequest.Status.PENDING).count()

    active_rewards = Reward.objects.filter(active=True).count()
    inactive_rewards = Reward.objects.filter(active=False).count()
    redemption_scope = since(RewardRedemption.objects.all(), "created_at")
    redemption_counts = {value: 0 for value, _ in RewardRedemption.Status.choices}
    for row in redemption_scope.values("status").annotate(count=Count("id")):
        redemption_counts[row["status"]] = row["count"]
    most_redeemed = list(
        redemption_scope.values("reward__name")
        .annotate(redemption_count=Count("id"))
        .order_by("-redemption_count", "reward__name")[:5]
    )

    active_materials = MarketplaceMaterial.objects.filter(active=True)
    material_summary = active_materials.aggregate(
        active_count=Count("id"),
        available_count=Count("id", filter=Q(available_quantity__gt=0)),
    )
    marketplace_inventory = list(
        active_materials.values("unit")
        .annotate(quantity=Coalesce(Sum("available_quantity"), Value(ZERO), output_field=weight_field))
        .order_by("unit")
    )
    unit_labels = dict(MarketplaceMaterial.Unit.choices)
    for row in marketplace_inventory:
        row["unit_label"] = unit_labels.get(row["unit"], row["unit"])
    buyer_scope = since(BuyerRequest.objects.all(), "requested_at")
    buyer_counts = {value: 0 for value, _ in BuyerRequest.Status.choices}
    for row in buyer_scope.values("status").annotate(count=Count("id")):
        buyer_counts[row["status"]] = row["count"]
    pending_buyer_requests = BuyerRequest.objects.filter(status=BuyerRequest.Status.PENDING).count()

    category_activity_filter = Q(reports__created_at__gte=start_time) if start_time is not None else Q(reports__isnull=False)
    report_period_filter = Q(reports__created_at__gte=start_time) if start_time is not None else Q()
    completed_period_filter = Q(reports__collection_request__completed_at__gte=start_time) if start_time is not None else Q()
    relevant_categories = WasteCategory.objects.filter(Q(active=True) | category_activity_filter)
    category_rows = list(
        relevant_categories.annotate(
            report_count=Count("reports", filter=report_period_filter, distinct=True),
            estimated_kg=Coalesce(
                Sum(
                    weight_in_kilograms("reports__estimated_weight", "reports__weight_unit"),
                    filter=report_period_filter,
                ),
                Value(ZERO), output_field=weight_field,
            ),
            estimated_pieces=Coalesce(
                Sum("reports__estimated_piece_count", filter=report_period_filter),
                Value(ZERO), output_field=weight_field,
            ),
            collected_pieces=Coalesce(
                Sum(
                    "reports__collection_request__actual_piece_count",
                    filter=Q(reports__collection_request__status=CollectionRequest.Status.COMPLETED) & completed_period_filter,
                ),
                Value(ZERO), output_field=weight_field,
            ),
            collected_kg=Coalesce(
                Sum(
                    weight_in_kilograms(
                        "reports__collection_request__actual_weight",
                        "reports__collection_request__weight_unit",
                    ),
                    filter=Q(reports__collection_request__status=CollectionRequest.Status.COMPLETED)
                    & completed_period_filter,
                ),
                Value(ZERO), output_field=weight_field,
            ),
            verified_count=Count(
                "reports",
                filter=report_period_filter & Q(reports__status=WasteReport.Status.VERIFIED),
                distinct=True,
            ),
        ).order_by("name")
    )
    max_category_weight = max((row.estimated_kg for row in category_rows), default=ZERO)
    for row in category_rows:
        row.bar_width = int(row.estimated_kg * Decimal("100") / max_category_weight) if max_category_weight else 0

    daily_rows = list(
        reports.annotate(day=TruncDate("created_at", tzinfo=timezone.get_current_timezone()))
        .values("day")
        .annotate(
            report_count=Count("id"),
            estimated_kg=Coalesce(Sum(report_weight), Value(ZERO), output_field=weight_field),
        )
        .order_by("day")
    )
    daily_values = {row["day"]: row for row in daily_rows}
    if start_date is not None:
        chart_dates = [start_date + timedelta(days=offset) for offset in range(periods[period])]
    else:
        chart_dates = sorted(daily_values)
    daily_activity = [
        {
            "day": day,
            "report_count": daily_values.get(day, {}).get("report_count", 0),
            "estimated_kg": daily_values.get(day, {}).get("estimated_kg", ZERO),
        }
        for day in chart_dates
    ]
    max_daily_weight = max((row["estimated_kg"] for row in daily_activity), default=ZERO)
    for row in daily_activity:
        row["bar_height"] = (
            max(4, int(row["estimated_kg"] * Decimal("100") / max_daily_weight))
            if row["estimated_kg"] > 0 and max_daily_weight
            else 0
        )

    # Recent records intentionally omit customer, buyer, and payout contact details.
    recent_activity = []
    for report in reports.select_related("category").order_by("-created_at")[:5]:
        recent_activity.append({
            "date": report.created_at,
            "title": f"Waste report · {report.category.name}",
            "status": report.get_status_display(),
            "detail": f"{report.estimated_weight} {report.get_weight_unit_display()} estimated",
        })
    for collection in completed_collections.select_related("waste_report__category").order_by("-completed_at")[:5]:
        recent_activity.append({
            "date": collection.completed_at,
            "title": f"Collection completed · {collection.waste_report.category.name}",
            "status": collection.get_status_display(),
            "detail": (
                f"{collection.actual_piece_count} pieces collected"
                if collection.actual_piece_count is not None
                else f"{collection.actual_weight or ZERO} {collection.get_weight_unit_display()} collected"
            ),
        })
    for cashout in cashout_scope.order_by("-requested_at")[:5]:
        recent_activity.append({
            "date": cashout.requested_at,
            "title": f"Cash-out request #{cashout.pk}",
            "status": cashout.get_status_display(),
            "detail": f"{cashout.money_amount} {cashout.currency}",
        })
    for buyer_request in buyer_scope.select_related("material").order_by("-requested_at")[:5]:
        recent_activity.append({
            "date": buyer_request.requested_at,
            "title": f"Buyer request TP-{buyer_request.pk:06d} · {buyer_request.material_name or buyer_request.material.name}",
            "status": buyer_request.get_status_display(),
            "detail": f"{buyer_request.requested_quantity} {buyer_request.get_unit_display()}",
        })
    recent_activity.sort(key=lambda item: item["date"], reverse=True)

    collection_status_rows = [
        {"label": label, "count": collection_counts[value]}
        for value, label in CollectionRequest.Status.choices
    ]
    cashout_status_rows = [
        {"label": label, "count": cashout_counts[value]}
        for value, label in CashOutRequest.Status.choices
    ]
    redemption_status_rows = [
        {"label": label, "count": redemption_counts[value]}
        for value, label in RewardRedemption.Status.choices
    ]
    buyer_status_rows = [
        {"label": label, "count": buyer_counts[value]}
        for value, label in BuyerRequest.Status.choices
    ]

    return {
        "period": period,
        "period_label": "All time" if period == "all" else f"Last {period} days",
        "period_choices": (("7", "Last 7 days"), ("30", "Last 30 days"), ("90", "Last 90 days"), ("all", "All time")),
        "today": today,
        "total_waste_reports": report_totals["count"],
        "estimated_waste_kg": report_totals["estimated_kg"],
        "estimated_waste_pieces": report_totals["estimated_pieces"],
        "collected_waste_kg": collection_weight_total["total"],
        "collected_waste_pieces": collection_weight_total["pieces"],
        "verified_waste_kg": verified_weight,
        "approved_collectors": approved_collectors,
        "collectors_with_completions": collection_weight_total["collectors"],
        "available_collections": collection_counts[CollectionRequest.Status.AVAILABLE],
        "completed_collections": collection_counts[CollectionRequest.Status.COMPLETED],
        "completed_collection_count": collection_weight_total["count"],
        "collection_counts": collection_counts,
        "collection_status_rows": collection_status_rows,
        "collection_statuses": CollectionRequest.Status.choices,
        "total_collection_requests": total_collection_requests,
        "collection_completion_rate": completion_rate,
        "tokens_issued": token_transactions["issued"],
        "tokens_issued_for_kg": token_transactions["kg_rewards"],
        "tokens_issued_for_pieces": token_transactions["piece_rewards"],
        "tokens_redeemed": abs(token_transactions["redeemed"]),
        "tokens_requested_for_cashout": abs(token_transactions["cashout"]),
        "token_adjustments": token_transactions["adjustments"],
        "cashout_counts": cashout_counts,
        "cashout_statuses": CashOutRequest.Status.choices,
        "cashout_status_rows": cashout_status_rows,
        "total_cashout_requests": sum(cashout_counts.values()),
        "pending_cashouts": pending_cashouts,
        "cashout_token_total": cashout_totals["tokens"],
        "cashout_money_total": cashout_totals["money"],
        "active_rewards": active_rewards,
        "inactive_rewards": inactive_rewards,
        "redemption_counts": redemption_counts,
        "redemption_statuses": RewardRedemption.Status.choices,
        "redemption_status_rows": redemption_status_rows,
        "total_redemptions": sum(redemption_counts.values()),
        "most_redeemed": most_redeemed,
        "active_materials": material_summary["active_count"],
        "available_materials": material_summary["available_count"],
        "marketplace_inventory": marketplace_inventory,
        "buyer_counts": buyer_counts,
        "buyer_statuses": BuyerRequest.Status.choices,
        "buyer_status_rows": buyer_status_rows,
        "total_buyer_requests": sum(buyer_counts.values()),
        "pending_buyer_requests": pending_buyer_requests,
        "category_activity": category_rows,
        "daily_activity": daily_activity,
        "recent_activity": recent_activity[:12],
    }
