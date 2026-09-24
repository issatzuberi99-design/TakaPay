from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from django.conf.urls.static import static

from . import views
from apps.accounts import views as account_views

urlpatterns = [
    path("admin/dashboard/", account_views.admin_analytics_dashboard, name="admin_analytics_dashboard"),
    path("admin/operations/token-rates/", account_views.admin_token_rates, name="admin_token_rates"),
    path("admin/operations/collectors/", account_views.collector_applications, name="collector_applications"),
    path("admin/operations/collectors/<int:profile_id>/", account_views.collector_application_detail, name="collector_application_detail"),
    path("admin/operations/collections/", account_views.admin_collection_requests, name="admin_collection_requests"),
    path("admin/operations/collection-history/", account_views.admin_collection_history, name="admin_collection_history"),
    path("admin/operations/wallet-activity/", account_views.admin_wallet_activity, name="admin_wallet_activity"),
    path("admin/operations/published-materials/", account_views.admin_published_materials, name="admin_published_materials"),
    path("admin/operations/buyer-requests/", account_views.admin_buyer_requests, name="admin_buyer_requests"),
    path("admin/operations/buyer-requests/<int:request_id>/transition/", account_views.admin_buyer_request_transition, name="admin_buyer_request_transition"),
    path("admin/operations/cash-outs/", account_views.admin_cashout_requests, name="admin_cashout_requests"),
    path("admin/operations/cash-outs/<int:request_id>/transition/", account_views.admin_cashout_transition, name="admin_cashout_transition"),
    path("admin/operations/marketplace-preparation/", account_views.marketplace_preparation, name="marketplace_preparation"),
    path("admin/operations/marketplace-preparation/<int:material_id>/", account_views.marketplace_preparation_edit, name="marketplace_preparation_edit"),
    path("admin/operations/rewards/", account_views.admin_rewards, name="admin_rewards"),
    path("admin/operations/rewards/new/", account_views.admin_reward_edit, name="admin_reward_create"),
    path("admin/operations/rewards/<int:reward_id>/", account_views.admin_reward_edit, name="admin_reward_edit"),
    path("admin/operations/redemptions/", account_views.admin_redemptions, name="admin_redemptions"),
    path("admin/operations/economics/", account_views.admin_economics, name="admin_economics"),
    path("admin/operations/economics/<str:section>/", account_views.admin_economics, name="admin_economics_section"),
    path("admin/operations/economics/payouts/<int:payout_id>/transition/", account_views.admin_collector_payout_transition, name="admin_collector_payout_transition"),
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("marketplace/", include("apps.marketplace.urls")),
    path("login/", account_views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", account_views.register, name="register"),
    path("register/collector/", account_views.collector_register, name="collector_register"),
    path("dashboard/", account_views.dashboard, name="dashboard"),
    path("admin-dashboard/", account_views.admin_dashboard, name="admin_dashboard"),
    path("collector/jobs/", account_views.collector_jobs, name="collector_jobs"),
    path("collections/", include("apps.collections.urls")),
    path("waste/", include("apps.waste.urls")),
    path("wallet/", include("apps.wallet.urls")),
    path("rewards/", include("apps.rewards.urls")),
    path("cashout/", include("apps.cashout.urls")),
    path("economics/", include("apps.economics.urls")),
    path("service-worker.js", views.service_worker, name="service_worker"),
    path("api/", include("config.api_urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
