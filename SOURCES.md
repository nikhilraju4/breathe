# Sources — research and sample data

## 1. SAP (fuel & procurement)

### Real-world formats researched

- **IDoc** (e.g. MATMAS, INVOIC02) — standard for SAP-to-SAP integration; XML, complex.
- **OData** MM/FI services — modern but needs SAP Gateway and auth.
- **Flat file / ALV export** — semicolon-separated; common for ESG consultants receiving monthly dumps.

### What we learned

- Column names vary by locale (German: Werks, Menge, Meins, Budat).
- Units are inconsistent (L, GAL, M3, ST).
- Plant codes are meaningless without a client-specific plant master.
- Fuel vs procurement is often inferred from material group, not a single “scope” column.

### Sample data (`sample_data/sap_fuel_procurement_export.csv`)

- Semicolon delimiter, mixed DE/EN style headers.
- Includes intentional defects: missing Werks, negative quantity, very large liter posting.
- Material groups: DIESEL, NATGAS, GASOLINE, OFFICE, PACKAGING, RAW_MATERIAL.

### What breaks in production

- Multi-company codes (BUKRS) without mapping table.
- Duplicate postings across delta loads (no idempotency key from SAP doc number).
- IDoc instead of CSV would require an XML parser and partner profiles.

---

## 2. Utility (electricity)

### Real-world formats researched

- **Portal CSV** — monthly download from suppliers (E.ON, ConEd-style column sets).
- **PDF bill** — universal but hostile to automation.
- **Green Button / utility API** — rare, consent-heavy.

### What we learned

- Billing periods rarely align to calendar months.
- kWh is the normalize target; peak kW and charges are supplementary.
- One suspicious row (520,000 kWh) simulates meter mis-read or wrong decimal.

### Sample data (`sample_data/utility_portal_electricity.csv`)

- Comma-separated, US/EU style addresses.
- Multiple meters per account, TOU rate schedule field preserved in metadata.

### What breaks in production

- 40+ utilities × different column names.
- Estimated vs actual reads.
- Cogen / on-site solar net metering not in CSV.

---

## 3. Corporate travel

### Real-world formats researched

- **SAP Concur** expense exports and Reporting v3 APIs ([Concur developer docs](https://developer.concur.com/)).
- **Navan** — similar trip/expense exports for flights and hotels.

### What we learned

- Flights may lack distance; only airport codes → need great-circle fallback.
- Hotels use nights; ground uses amount only.
- High amounts and missing routes should flag analyst review, not auto-approve.

### Sample data (`sample_data/concur_travel_export.csv`)

- Mixed rows: flight with km, flight without km (SFO-JFK), hotel with nights, ground, rail, outlier GBP airfare.

### What breaks in production

- Multi-leg itineraries collapsed to one line.
- Personal vs business expense not tagged.
- API pagination and reimbursement vs booked ticket timing.
