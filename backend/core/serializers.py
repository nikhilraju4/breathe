from django.contrib.auth import get_user_model
from rest_framework import serializers

from core.models import ActivityRecord, IngestionBatch, RecordAuditLog, Tenant

User = get_user_model()


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]


class IngestionBatchSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = IngestionBatch
        fields = [
            "id",
            "source_type",
            "source_type_display",
            "status",
            "status_display",
            "file_name",
            "row_count",
            "success_count",
            "error_count",
            "suspicious_count",
            "error_log",
            "created_at",
        ]


class ActivityRecordSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source="get_scope_display", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    review_status_display = serializers.CharField(source="get_review_status_display", read_only=True)
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    batch_file = serializers.CharField(source="batch.file_name", read_only=True, default="")

    class Meta:
        model = ActivityRecord
        fields = [
            "id",
            "source_type",
            "source_type_display",
            "source_row_id",
            "scope",
            "scope_display",
            "category",
            "category_display",
            "activity_date",
            "description",
            "facility_code",
            "quantity",
            "unit",
            "raw_quantity",
            "raw_unit",
            "distance_km",
            "origin",
            "destination",
            "supplier",
            "metadata",
            "review_status",
            "review_status_display",
            "is_suspicious",
            "suspicious_reason",
            "parse_error",
            "edited_by_analyst",
            "approved_at",
            "locked_at",
            "batch_file",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "source_type",
            "source_row_id",
            "source_fingerprint",
            "created_at",
            "updated_at",
            "approved_at",
            "locked_at",
        ]


class ActivityRecordUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityRecord
        fields = [
            "description",
            "quantity",
            "unit",
            "facility_code",
            "activity_date",
            "distance_km",
            "origin",
            "destination",
        ]


class RecordAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.username", read_only=True, default="system")

    class Meta:
        model = RecordAuditLog
        fields = ["id", "action", "actor_name", "before_state", "after_state", "note", "created_at"]


class DashboardStatsSerializer(serializers.Serializer):
    total_records = serializers.IntegerField()
    pending = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    locked = serializers.IntegerField()
    suspicious = serializers.IntegerField()
    failed_parses = serializers.IntegerField()
    by_source = serializers.DictField()
    by_scope = serializers.DictField()
    recent_batches = IngestionBatchSerializer(many=True)
