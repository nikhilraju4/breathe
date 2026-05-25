from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404, HttpResponseNotFound
from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from core.views import (
    ActivityRecordViewSet,
    DashboardView,
    IngestUploadView,
    IngestionBatchViewSet,
    LoginView,
    TenantViewSet,
    lock_for_audit,
)

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("records", ActivityRecordViewSet, basename="record")
router.register("batches", IngestionBatchViewSet, basename="batch")


def serve_spa(request):
    index = settings.FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(open(index, "rb"), content_type="text/html")
    raise Http404("Frontend not built. Run: cd frontend && npm run build")


def serve_frontend_asset(request, path: str):
    asset = settings.FRONTEND_DIST / "assets" / path
    if not asset.is_file():
        return HttpResponseNotFound("Asset not found")
    content_types = {
        ".js": "application/javascript",
        ".css": "text/css",
        ".map": "application/json",
    }
    ctype = content_types.get(asset.suffix, "application/octet-stream")
    return FileResponse(open(asset, "rb"), content_type=ctype)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/login/", LoginView.as_view()),
    path("api/dashboard/", DashboardView.as_view()),
    path("api/ingest/upload/", IngestUploadView.as_view()),
    path("api/audit/lock/", lock_for_audit),
    path("api/", include(router.urls)),
]

if settings.FRONTEND_DIST.exists():
    urlpatterns += [
        re_path(r"^assets/(?P<path>.*)$", serve_frontend_asset),
        re_path(r"^$", serve_spa),
        re_path(r"^(?!api|admin|static|assets).*$", serve_spa),
    ]
