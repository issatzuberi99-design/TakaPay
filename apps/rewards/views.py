from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import role_required
from apps.accounts.models import User
from apps.wallet.models import Wallet, WalletTransaction

from .models import Reward, RewardRedemption


def _customer_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


@role_required(User.Role.CUSTOMER)
def reward_list(request):
    wallet = _customer_wallet(request.user)
    rewards = Reward.objects.filter(active=True)
    return render(request, "rewards/reward_list.html", {"rewards": rewards, "wallet": wallet})


@role_required(User.Role.CUSTOMER)
def reward_detail(request, reward_id):
    reward = get_object_or_404(Reward, pk=reward_id, active=True)
    wallet = _customer_wallet(request.user)
    return render(request, "rewards/reward_detail.html", {"reward": reward, "wallet": wallet})


@role_required(User.Role.CUSTOMER)
def redeem_reward(request, reward_id):
    if request.method != "POST":
        return redirect("reward_detail", reward_id=reward_id)

    try:
        with transaction.atomic():
            reward = get_object_or_404(
                Reward.objects.select_for_update(),
                pk=reward_id,
                active=True,
            )
            wallet = Wallet.objects.select_for_update().get(user=request.user)

            if reward.inventory <= 0:
                raise ValueError("This reward is out of stock.")
            if wallet.balance < reward.token_cost:
                raise ValueError("You do not have enough TakaPay Tokens for this reward.")

            redemption = RewardRedemption.objects.create(
                customer=request.user,
                reward=reward,
                token_amount=reward.token_cost,
                status=RewardRedemption.Status.PENDING,
            )
            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type=WalletTransaction.TransactionType.REWARD_REDEMPTION,
                amount=-reward.token_cost,
                description=f"Redeemed reward: {reward.name}",
                reference=f"redemption-{redemption.pk}",
            )
            reward.inventory -= 1
            reward.save(update_fields=["inventory", "updated_at"])
            redemption.status = RewardRedemption.Status.COMPLETED
            redemption.save(update_fields=["status", "updated_at"])
    except Wallet.DoesNotExist:
        messages.error(request, "This reward cannot be redeemed right now.")
    except ValueError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Reward redeemed successfully.")

    return redirect("reward_detail", reward_id=reward_id)


@role_required(User.Role.CUSTOMER)
def redemption_history(request):
    redemptions = RewardRedemption.objects.filter(customer=request.user).select_related("reward")
    return render(request, "rewards/redemption_history.html", {"redemptions": redemptions})