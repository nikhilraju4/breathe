import uuid

from django.conf import settings
from django.db import models


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TenantMembership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(
        max_length=20,
        choices=[("analyst", "Analyst"), ("admin", "Admin")],
        default="analyst",
    )

    class Meta:
        unique_together = ("user", "tenant")


class Scope(models.TextChoices):
    SCOPE_1 = "1", "Scope 1"
    SCOPE_2 = "2", "Scope 2"
    SCOPE_3 = "3", "Scope 3"


class SourceType(models.TextChoices):
    SAP = "sap", "SAP (fuel & procurement)"
    UTILITY = "utility", "Utility (electricity)"
    TRAVEL = "travel", "Corporate travel"


class ActivityCategory(models.TextChoices):
    FUEL = "fuel", "Fuel"
    PROCUREMENT = "procurement", "Procurement"
    ELECTRICITY = "electricity", "Electricity"
    FLIGHT = "flight", "Flight"
    HOTEL = "hotel", "Hotel"
    GROUND = "ground", "Ground transport"


class ReviewStatus(models.TextChoices):
    PENDING = "pending", "Pending review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    LOCKED = "locked", "Locked for audit"


class IngestionStatus(models.TextChoices):
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    PARTIAL = "partial", "Partial success"


class IngestionBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="batches")
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    status = models.CharField(
        max_length=20, choices=IngestionStatus.choices, default=IngestionStatus.PROCESSING
    )
    file_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_batches",
    )
    row_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    suspicious_count = models.PositiveIntegerField(default=0)
    error_log = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ActivityRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="records")
    batch = models.ForeignKey(
        IngestionBatch, on_delete=models.CASCADE, related_name="records", null=True, blank=True
    )
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    source_row_id = models.CharField(max_length=100, blank=True)
    scope = models.CharField(max_length=1, choices=Scope.choices)
    category = models.CharField(max_length=20, choices=ActivityCategory.choices)
    activity_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    facility_code = models.CharField(max_length=50, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    unit = models.CharField(max_length=30, blank=True)
    raw_quantity = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    raw_unit = models.CharField(max_length=30, blank=True)
    distance_km = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    origin = models.CharField(max_length=20, blank=True)
    destination = models.CharField(max_length=20, blank=True)
    supplier = models.CharField(max_length=200, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    review_status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING
    )
    is_suspicious = models.BooleanField(default=False)
    suspicious_reason = models.CharField(max_length=500, blank=True)
    parse_error = models.TextField(blank=True)
    source_fingerprint = models.CharField(max_length=64, blank=True)
    edited_by_analyst = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_records",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-activity_date", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "review_status"]),
            models.Index(fields=["tenant", "source_type"]),
            models.Index(fields=["tenant", "is_suspicious"]),
        ]


class RecordAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(
        ActivityRecord, on_delete=models.CASCADE, related_name="audit_logs"
    )
    action = models.CharField(max_length=30)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
