from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from core.models import (
    ActivityRecord,
    IngestionBatch,
    IngestionStatus,
    RecordAuditLog,
    ReviewStatus,
    SourceType,
    Tenant,
)
from ingest.parsers import SAPFlatFileParser, TravelExportParser, UtilityCSVParser

User = get_user_model()

PARSERS = {
    SourceType.SAP: SAPFlatFileParser,
    SourceType.UTILITY: UtilityCSVParser,
    SourceType.TRAVEL: TravelExportParser,
}


def log_audit(record, action, actor=None, before=None, after=None, note=""):
    RecordAuditLog.objects.create(
        record=record,
        action=action,
        actor=actor,
        before_state=before,
        after_state=after,
        note=note,
    )


@transaction.atomic
def ingest_file(
    tenant: Tenant,
    source_type: str,
    content: str,
    file_name: str,
    user: User | None = None,
) -> IngestionBatch:
    batch = IngestionBatch.objects.create(
        tenant=tenant,
        source_type=source_type,
        file_name=file_name,
        uploaded_by=user,
        status=IngestionStatus.PROCESSING,
    )

    parser_cls = PARSERS.get(source_type)
    if not parser_cls:
        batch.status = IngestionStatus.FAILED
        batch.error_log = [{"error": f"Unknown source type: {source_type}"}]
        batch.save()
        return batch

    parsed_rows = parser_cls().parse(content)
    batch.row_count = len(parsed_rows)
    errors = []
    success = 0
    suspicious = 0

    for row in parsed_rows:
        if not row.ok and row.parse_error:
            errors.append({"row": row.source_row_id, "error": row.parse_error})
            ActivityRecord.objects.create(
                tenant=tenant,
                batch=batch,
                source_type=source_type,
                source_row_id=row.source_row_id,
                scope=row.scope,
                category=row.category,
                description=row.description or "Parse failure",
                review_status=ReviewStatus.REJECTED,
                parse_error=row.parse_error,
                metadata=row.metadata,
                source_fingerprint=row.fingerprint,
            )
            continue

        record = ActivityRecord.objects.create(
            tenant=tenant,
            batch=batch,
            source_type=source_type,
            source_row_id=row.source_row_id,
            scope=row.scope,
            category=row.category,
            activity_date=row.activity_date.date() if row.activity_date else None,
            description=row.description,
            facility_code=row.facility_code,
            quantity=row.quantity,
            unit=row.unit,
            raw_quantity=row.raw_quantity,
            raw_unit=row.raw_unit,
            distance_km=row.distance_km,
            origin=row.origin,
            destination=row.destination,
            supplier=row.supplier,
            metadata=row.metadata,
            is_suspicious=row.is_suspicious,
            suspicious_reason=row.suspicious_reason,
            parse_error=row.parse_error,
            source_fingerprint=row.fingerprint,
        )
        log_audit(
            record,
            "ingested",
            actor=user,
            after={"source": source_type, "row": row.source_row_id},
            note=f"From batch {batch.id}",
        )
        success += 1
        if row.is_suspicious:
            suspicious += 1

    batch.success_count = success
    batch.error_count = len(errors)
    batch.suspicious_count = suspicious
    batch.error_log = errors
    if success == 0:
        batch.status = IngestionStatus.FAILED
    elif errors:
        batch.status = IngestionStatus.PARTIAL
    else:
        batch.status = IngestionStatus.COMPLETED
    batch.save()
    return batch


def approve_record(record: ActivityRecord, user: User) -> ActivityRecord:
    if record.review_status == ReviewStatus.LOCKED:
        raise ValueError("Record is locked for audit")
    before = {"review_status": record.review_status}
    record.review_status = ReviewStatus.APPROVED
    record.approved_by = user
    record.approved_at = timezone.now()
    record.save()
    log_audit(record, "approved", actor=user, before=before, after={"review_status": "approved"})
    return record


def reject_record(record: ActivityRecord, user: User, note: str = "") -> ActivityRecord:
    if record.review_status == ReviewStatus.LOCKED:
        raise ValueError("Record is locked for audit")
    before = {"review_status": record.review_status}
    record.review_status = ReviewStatus.REJECTED
    record.save()
    log_audit(record, "rejected", actor=user, before=before, after={"review_status": "rejected"}, note=note)
    return record


def lock_approved_records(tenant: Tenant, user: User) -> int:
    qs = ActivityRecord.objects.filter(
        tenant=tenant, review_status=ReviewStatus.APPROVED
    )
    count = 0
    now = timezone.now()
    for record in qs:
        before = {"review_status": record.review_status}
        record.review_status = ReviewStatus.LOCKED
        record.locked_at = now
        record.save()
        log_audit(record, "locked", actor=user, before=before, after={"review_status": "locked"})
        count += 1
    return count
