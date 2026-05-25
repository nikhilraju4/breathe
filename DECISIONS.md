# Decisions

## Ingestion mechanism (all three sources)

**Choice: CSV file upload via analyst UI.**

| Source | Real-world alternatives | Why upload |
|--------|-------------------------|------------|
| SAP | IDoc, OData, BAPI, flat file | Enterprise onboarding often starts with scheduled flat-file drops from SAP PI/BOBJ. No SAP sandbox available; upload matches “first integration” reality. |
| Utility | Portal CSV, PDF bill, Green Button API | Facilities teams routinely download CSV from supplier portals. PDF OCR is a separate product bet; API access is utility-specific and slow to contract. |
| Travel | Concur/Navan API, SFTP export | API requires OAuth app approval; CSV export is what analysts already email to sustainability teams. |

**If I could ask the PM:** Do we have an existing MuleSoft/Boomi pipe for SAP, or is this client still on manual exports? Is utility data monthly batch or near-real-time?

## SAP — subset handled

**Format:** Semicolon-delimited flat file (German-style headers: Werks, MENGE, MEINS, BUDAT).

**Handled:** Fuel postings (Scope 1) and procurement material groups (Scope 3). Unit normalization L/GAL/M3 → liters, KG unchanged.

**Ignored:** IDoc XML, OData MM endpoints, multi-plant controlling hierarchies, currency conversion, GR/IR matching, full material master.

**Justification:** SAP MM/FI CSV extracts are common in mid-market ESG onboarding before API investment. IDoc is more “real” for SAP shops but opaque without a sandbox.

## Utility — subset handled

**Format:** Portal CSV with billing period start/end, meter ID, kWh, tariff code.

**Handled:** Electricity kWh per billing period (Scope 2). Flags period inversion and absurd monthly kWh.

**Ignored:** PDF bill OCR, tariff line-item breakdown, demand charges for emissions, renewable energy certificates, Green Button XML.

**Justification:** CSV is what facilities teams actually attach to emails; billing periods ≠ calendar months is preserved in metadata for downstream allocation.

## Travel — subset handled

**Format:** Concur-style expense CSV (air, hotel, ground, rail).

**Handled:** Category → Scope 3, airport codes, distance when present, flag missing distance on flights.

**Ignored:** Live Concur API, per-diems, personal car mileage logs, hotel night-level occupancy, class of service for factors.

**Justification:** Matches [SAP Concur Expense Report](https://developer.concur.com/) export shapes without OAuth setup.

## Suspicious vs failed

- **Failed:** Missing required fields → row stored with `parse_error`, status rejected.
- **Suspicious:** Parsed but needs analyst judgment (negative qty, missing plant, flight without km, huge expense).

## Review workflow

Pending → Approved/Rejected → Locked. Analysts cannot edit locked rows. Edits set `edited_by_analyst` and write audit diff.

## Auth

Token auth + demo user. Production would use SSO (SAML/OIDC) and tenant-scoped JWT claims.

## Frontend served by Django

Single deploy on Render: Django serves built React `dist/` for simplicity. Alternative would be separate static host + CORS.

## Questions for PM (summary)

1. SAP: flat file today or IDoc in 6 months?
2. Utility: one portal or 40 regional suppliers?
3. Travel: Concur or Navan — which API tier is contracted?
4. Audit: lock per fiscal quarter or per ingestion batch?
5. Multi-tenant: separate DB schemas or row-level isolation (current: row-level)?
