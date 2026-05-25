# Data model

## Overview

The prototype centers on **normalized activity records** that analysts review before locking for audit. Every row traces back to a **tenant**, an **ingestion batch** (source file), and an append-only **audit log**.

```
Tenant
  └── IngestionBatch (per file upload)
        └── ActivityRecord (one per source row, normalized)
              └── RecordAuditLog (immutable events)
  └── TenantMembership → User (analyst)
```

## Entities

### Tenant

Multi-tenancy boundary. All queries filter by `tenant_id`. A user may belong to multiple tenants via `TenantMembership` (role: analyst or admin). The demo seeds one tenant: Acme Corporation.

### IngestionBatch

Represents a single ingest operation (file upload). Tracks:

- `source_type`: sap | utility | travel
- `status`: processing → completed | partial | failed
- Counts: rows, successes, errors, suspicious flags
- `error_log`: JSON array of per-row parse failures
- `uploaded_by`, `file_name`, `created_at`

This is the **source-of-truth anchor** for “when did this file arrive and what happened.”

### ActivityRecord

The normalized unit of work for analysts and auditors.

| Concern | Fields |
|--------|--------|
| Provenance | `batch`, `source_type`, `source_row_id`, `source_fingerprint` |
| GHG scope | `scope` (1/2/3), `category` (fuel, electricity, flight, …) |
| Activity | `activity_date`, `description`, `facility_code`, `supplier` |
| Units | `quantity` + `unit` (normalized), `raw_quantity` + `raw_unit` (as ingested) |
| Travel-specific | `distance_km`, `origin`, `destination` |
| Review | `review_status`: pending → approved/rejected → locked |
| Quality | `is_suspicious`, `suspicious_reason`, `parse_error` |
| Analyst edits | `edited_by_analyst` (boolean; full diff in audit log) |
| Sign-off | `approved_by`, `approved_at`, `locked_at` |
| Extensibility | `metadata` JSON for source-specific fields |

**Scope mapping (this prototype):**

- Scope 1: SAP fuel lines (diesel, gasoline, natural gas material groups)
- Scope 2: Utility electricity (kWh)
- Scope 3: SAP procurement + all corporate travel categories

### RecordAuditLog

Append-only trail: `ingested`, `edited`, `approved`, `rejected`, `locked`. Stores `before_state` / `after_state` JSON snapshots so auditors can see what changed after ingest.

## Design choices

1. **Batch + row, not raw staging table** — For a 4-day prototype, we persist failed rows as `ActivityRecord` with `parse_error` rather than a separate raw JSON table. Production would likely add `RawStagingRow` for reprocessing.

2. **Fingerprint** — SHA-256 hash of source + row id + payload supports idempotency discussions (not fully enforced in prototype).

3. **No emission factors table** — We normalize quantities and flag suspicious data; carbon calculation is downstream. Keeps the model honest about what this app does: ingest + review, not full LCA.

4. **Lock is batch-oriented via API** — `lock_for_audit` locks all approved rows for a tenant. Production would add per-period or per-batch locks with PM approval.

## Indexes

- `(tenant, review_status)` — dashboard and analyst queues
- `(tenant, source_type)` — source filters
- `(tenant, is_suspicious)` — review queue for flagged rows
