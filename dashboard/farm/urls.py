from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="farm/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("lang/<str:code>/", views.set_language, name="set_language"),
    path("manifest.json", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="sw"),
    path("offline/", views.offline, name="offline"),

    path("", views.dashboard, name="dashboard"),
    path("field/<int:field_id>/", views.dashboard, name="field"),
    path("field/<int:field_id>/series.json", views.series, name="series"),
    path("field/<int:field_id>/settings/", views.field_settings, name="field_settings"),
    path("field/<int:field_id>/valve/", views.valve_control, name="valve_control"),
    path("fields/new/", views.field_create, name="field_create"),
    path("explore/", views.explore, name="explore"),
    path("schedule/", views.schedule, name="schedule"),
    path("alerts/", views.alerts, name="alerts"),
    path("savings/", views.savings, name="savings"),
    path("savings.json", views.savings_json, name="savings_json"),
    path("health/", views.sensor_health, name="health"),
    path("health/<int:sensor_id>/calibrate/", views.calibrate, name="calibrate"),
    path("reports/", views.reports, name="reports"),
    path("reports/<str:kind>.csv", views.report_csv, name="report_csv"),
    path("reports/summary.pdf", views.report_pdf, name="report_pdf"),
    path("coop/", views.coop, name="coop"),
]
