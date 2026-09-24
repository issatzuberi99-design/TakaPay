from django.urls import path

from . import views

urlpatterns = [
    path("", views.reward_list, name="reward_list"),
    path("history/", views.redemption_history, name="redemption_history"),
    path("<int:reward_id>/", views.reward_detail, name="reward_detail"),
    path("<int:reward_id>/redeem/", views.redeem_reward, name="redeem_reward"),
]