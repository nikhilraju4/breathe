from django.contrib import admin

from core.models import ActivityRecord, IngestionBatch, RecordAuditLog, Tenant, TenantMembership


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant", "role")


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    list_display = ("file_name", "source_type", "status", "tenant", "created_at")


@admin.register(ActivityRecord)
class ActivityRecordAdmin(admin.ModelAdmin):
    list_display = ("source_row_id", "category", "scope", "review_status", "is_suspicious", "tenant")
    list_filter = ("review_status", "source_type", "scope", "is_suspicious")


@admin.register(RecordAuditLog)
class RecordAuditLogAdmin(admin.ModelAdmin):
    list_display = ("record", "action", "actor", "created_at")
