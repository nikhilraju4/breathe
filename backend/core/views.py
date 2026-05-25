from django.contrib.auth import authenticate
from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import ActivityRecord, IngestionBatch, RecordAuditLog, ReviewStatus, Tenant
from core.serializers import (
    ActivityRecordSerializer,
    ActivityRecordUpdateSerializer,
    DashboardStatsSerializer,
    IngestionBatchSerializer,
    RecordAuditLogSerializer,
    TenantSerializer,
    UserSerializer,
)
from ingest.services import approve_record, ingest_file, lock_approved_records, log_audit, reject_record


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)
        if not user:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        token, _ = Token.objects.get_or_create(user=user)
        tenant = user.memberships.select_related("tenant").first()
        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
                "tenant": TenantSerializer(tenant.tenant).data if tenant else None,
            }
        )


class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Tenant.objects.filter(members__user=self.request.user)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = self._tenant(request)
        if not tenant:
            return Response({"detail": "No tenant membership"}, status=400)
        qs = ActivityRecord.objects.filter(tenant=tenant)
        by_source = dict(qs.values_list("source_type").annotate(c=Count("id")).values_list("source_type", "c"))
        by_scope = dict(qs.values_list("scope").annotate(c=Count("id")).values_list("scope", "c"))
        data = {
            "total_records": qs.count(),
            "pending": qs.filter(review_status=ReviewStatus.PENDING).count(),
            "approved": qs.filter(review_status=ReviewStatus.APPROVED).count(),
            "rejected": qs.filter(review_status=ReviewStatus.REJECTED).count(),
            "locked": qs.filter(review_status=ReviewStatus.LOCKED).count(),
            "suspicious": qs.filter(is_suspicious=True).count(),
            "failed_parses": qs.exclude(parse_error="").count(),
            "by_source": by_source,
            "by_scope": by_scope,
            "recent_batches": IngestionBatch.objects.filter(tenant=tenant)[:5],
        }
        return Response(DashboardStatsSerializer(data).data)

    def _tenant(self, request):
        tid = request.query_params.get("tenant") or request.headers.get("X-Tenant-ID")
        if tid:
            return Tenant.objects.filter(id=tid, members__user=request.user).first()
        m = request.user.memberships.select_related("tenant").first()
        return m.tenant if m else None


class ActivityRecordViewSet(viewsets.ModelViewSet):
    serializer_class = ActivityRecordSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        tenant = self._tenant()
        if not tenant:
            return ActivityRecord.objects.none()
        qs = ActivityRecord.objects.filter(tenant=tenant).select_related("batch")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(review_status=status_filter)
        source = self.request.query_params.get("source")
        if source:
            qs = qs.filter(source_type=source)
        if self.request.query_params.get("suspicious") == "true":
            qs = qs.filter(is_suspicious=True)
        if self.request.query_params.get("errors") == "true":
            qs = qs.filter(~Q(parse_error=""))
        search = self.request.query_params.get("q")
        if search:
            qs = qs.filter(
                Q(description__icontains=search)
                | Q(facility_code__icontains=search)
                | Q(source_row_id__icontains=search)
            )
        return qs

    def get_serializer_class(self):
        if self.action in ("partial_update", "update"):
            return ActivityRecordUpdateSerializer
        return ActivityRecordSerializer

    def partial_update(self, request, *args, **kwargs):
        record = self.get_object()
        if record.review_status == ReviewStatus.LOCKED:
            return Response({"detail": "Locked records cannot be edited"}, status=400)
        before = ActivityRecordSerializer(record).data
        serializer = ActivityRecordUpdateSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(edited_by_analyst=True)
        log_audit(
            record,
            "edited",
            actor=request.user,
            before=before,
            after=ActivityRecordSerializer(record).data,
        )
        return Response(ActivityRecordSerializer(record).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        record = self.get_object()
        try:
            approve_record(record, request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(ActivityRecordSerializer(record).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        record = self.get_object()
        try:
            reject_record(record, request.user, note=request.data.get("note", ""))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(ActivityRecordSerializer(record).data)

    @action(detail=True, methods=["get"])
    def audit_trail(self, request, pk=None):
        record = self.get_object()
        logs = RecordAuditLog.objects.filter(record=record)
        return Response(RecordAuditLogSerializer(logs, many=True).data)

    def _tenant(self):
        tid = self.request.query_params.get("tenant") or self.request.headers.get("X-Tenant-ID")
        if tid:
            return Tenant.objects.filter(id=tid, members__user=self.request.user).first()
        m = self.request.user.memberships.select_related("tenant").first()
        return m.tenant if m else None


class IngestionBatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngestionBatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = self._tenant()
        if not tenant:
            return IngestionBatch.objects.none()
        return IngestionBatch.objects.filter(tenant=tenant)

    def _tenant(self):
        tid = self.request.query_params.get("tenant") or self.request.headers.get("X-Tenant-ID")
        if tid:
            return Tenant.objects.filter(id=tid, members__user=self.request.user).first()
        m = self.request.user.memberships.select_related("tenant").first()
        return m.tenant if m else None


class IngestUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = self._tenant(request)
        if not tenant:
            return Response({"detail": "No tenant"}, status=400)
        source_type = request.data.get("source_type")
        upload = request.FILES.get("file")
        if not source_type or not upload:
            return Response({"detail": "source_type and file required"}, status=400)
        content = upload.read().decode("utf-8-sig", errors="replace")
        batch = ingest_file(tenant, source_type, content, upload.name, request.user)
        return Response(IngestionBatchSerializer(batch).data, status=201)

    def _tenant(self, request):
        tid = request.data.get("tenant") or request.headers.get("X-Tenant-ID")
        if tid:
            return Tenant.objects.filter(id=tid, members__user=request.user).first()
        m = request.user.memberships.select_related("tenant").first()
        return m.tenant if m else None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def lock_for_audit(request):
    tenant_id = request.data.get("tenant") or request.headers.get("X-Tenant-ID")
    tenant = Tenant.objects.filter(id=tenant_id, members__user=request.user).first()
    if not tenant:
        m = request.user.memberships.select_related("tenant").first()
        tenant = m.tenant if m else None
    if not tenant:
        return Response({"detail": "No tenant"}, status=400)
    count = lock_approved_records(tenant, request.user)
    return Response({"locked_count": count})
