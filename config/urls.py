from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from django.conf.urls.static import static

from . import views
from apps.accounts import views as account_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("marketplace/", views.marketplace, name="marketplace"),
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
    path("service-worker.js", views.service_worker, name="service_worker"),
    path("api/", include("config.api_urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
