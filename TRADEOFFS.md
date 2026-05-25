# Tradeoffs — three things we did not build

## 1. Live API connectors (SAP OData, Concur OAuth, utility Green Button)

**Why not:** Each connector needs credentials, sandbox contracts, and error handling for rate limits and partial syncs. The core problem here is *shape normalization and analyst review*, not integration plumbing.

**Cost of skipping:** Analysts must upload files manually. Acceptable for prototype and often true for week-1 onboarding.

**What we’d build next:** SAP PI scheduled drop to S3 + webhook; Concur pull by report date range.

## 2. Emission factor engine and CO₂e calculation

**Why not:** Factors vary by geography, grid year, DEFRA vs EPA, class of travel, and client-specific methodologies. Mixing calculation into ingest confuses “data quality review” with “methodology application.”

**Cost of skipping:** Approved rows are activity data only; carbon totals happen elsewhere.

**What we’d build next:** Versioned factor tables keyed by `category + region + year`, applied only after lock.

## 3. PDF utility bill parsing (OCR)

**Why not:** PDF layouts differ per utility; OCR accuracy and human verification dominate effort. Many clients eventually get CSV access after pushing suppliers.

**Cost of skipping:** Clients stuck on PDF-only bills need manual entry or a separate service.

**What we’d build next:** Template-based extraction for top-10 utilities in client’s portfolio, not generic OCR.
