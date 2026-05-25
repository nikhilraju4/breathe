"""Parsers for realistic SAP flat-file, utility portal CSV, and travel exports."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass
class ParsedRow:
    ok: bool
    source_row_id: str
    scope: str
    category: str
    activity_date: datetime | None
    description: str
    facility_code: str
    quantity: Decimal | None
    unit: str
    raw_quantity: Decimal | None
    raw_unit: str
    distance_km: Decimal | None
    origin: str
    destination: str
    supplier: str
    metadata: dict[str, Any]
    is_suspicious: bool
    suspicious_reason: str
    parse_error: str
    fingerprint: str


SAP_HEADER_MAP = {
    "werks": "plant",
    "plant": "plant",
    "bukrs": "company_code",
    "company code": "company_code",
    "matnr": "material",
    "material": "material",
    "menge": "quantity",
    "quantity": "quantity",
    "meins": "unit",
    "unit": "unit",
    "budat": "posting_date",
    "posting date": "posting_date",
    "lifnr": "vendor",
    "vendor": "vendor",
    "ktext": "description",
    "description": "description",
    "material group": "material_group",
    "matkl": "material_group",
}

UTILITY_HEADER_MAP = {
    "account number": "account",
    "meter id": "meter_id",
    "service address": "address",
    "billing period start": "period_start",
    "billing period end": "period_end",
    "usage (kwh)": "usage_kwh",
    "usage kwh": "usage_kwh",
    "total kwh": "usage_kwh",
    "peak demand (kw)": "peak_kw",
    "rate schedule": "tariff",
    "total charges": "total_charges",
}

TRAVEL_HEADER_MAP = {
    "expense id": "expense_id",
    "employee id": "employee_id",
    "transaction date": "txn_date",
    "expense type": "expense_type",
    "vendor": "vendor",
    "amount": "amount",
    "currency": "currency",
    "origin airport": "origin",
    "destination airport": "destination",
    "distance (km)": "distance_km",
    "distance km": "distance_km",
    "nights": "nights",
    "city": "city",
}


def _normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip().lower())


def _parse_decimal(val: str) -> Decimal | None:
    if not val or not str(val).strip():
        return None
    cleaned = str(val).strip().replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_date(val: str) -> datetime | None:
    if not val or not str(val).strip():
        return None
    val = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def _fingerprint(source: str, row_id: str, payload: str) -> str:
    raw = f"{source}:{row_id}:{payload}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _detect_delimiter(sample: str) -> str:
    if sample.count(";") > sample.count(","):
        return ";"
    return ","


def _read_csv_rows(content: str) -> tuple[list[str], list[dict[str, str]]]:
    sample = content[:2048]
    delimiter = _detect_delimiter(sample)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if not reader.fieldnames:
        return [], []
    headers = [_normalize_header(h) for h in reader.fieldnames]
    rows = []
    for raw in reader:
        row = {}
        for orig, norm in zip(reader.fieldnames, headers):
            row[norm] = (raw.get(orig) or "").strip()
        rows.append(row)
    return headers, rows


def _map_row(row: dict[str, str], mapping: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, val in row.items():
        canonical = mapping.get(key, key)
        out[canonical] = val
    return row | {mapping.get(k, k): v for k, v in row.items()}


class SAPFlatFileParser:
    """SAP MM/FI flat export (semicolon-delimited); subset: fuel + procurement lines."""

    FUEL_GROUPS = {"DIESEL", "GASOLINE", "NATGAS", "HEATING_OIL", "LPG"}
    PROCUREMENT_GROUPS = {"OFFICE", "PACKAGING", "RAW_MATERIAL"}

    def parse(self, content: str) -> list[ParsedRow]:
        _, rows = _read_csv_rows(content)
        results: list[ParsedRow] = []
        for idx, raw in enumerate(rows, start=1):
            row = _map_row(raw, SAP_HEADER_MAP)
            row_id = f"SAP-{idx}"
            try:
                results.append(self._parse_row(row_id, row))
            except Exception as exc:
                results.append(
                    ParsedRow(
                        ok=False,
                        source_row_id=row_id,
                        scope="1",
                        category="fuel",
                        activity_date=None,
                        description="",
                        facility_code="",
                        quantity=None,
                        unit="",
                        raw_quantity=None,
                        raw_unit="",
                        distance_km=None,
                        origin="",
                        destination="",
                        supplier="",
                        metadata=row,
                        is_suspicious=False,
                        suspicious_reason="",
                        parse_error=str(exc),
                        fingerprint=_fingerprint("sap", row_id, str(row)),
                    )
                )
        return results

    def _parse_row(self, row_id: str, row: dict[str, str]) -> ParsedRow:
        plant = row.get("plant", "")
        qty = _parse_decimal(row.get("quantity", ""))
        unit = (row.get("unit") or "").upper()
        mat_group = (row.get("material_group") or "").upper()
        desc = row.get("description", "")
        vendor = row.get("vendor", "")
        dt = _parse_date(row.get("posting_date", ""))

        suspicious = False
        reason = ""
        if qty is not None and qty < 0:
            suspicious = True
            reason = "Negative quantity in SAP posting"
        if unit in ("L", "LTR") and qty and qty > 50000:
            suspicious = True
            reason = reason or "Unusually high fuel volume for single posting"

        category = "procurement"
        scope = "3"
        if mat_group in self.FUEL_GROUPS or "DIESEL" in desc.upper() or "FUEL" in desc.upper():
            category = "fuel"
            scope = "1"

        normalized_qty, normalized_unit = self._normalize_quantity(qty, unit)
        if unit and normalized_unit != unit and unit not in ("KG", "KWH"):
            suspicious = True
            reason = reason or f"Converted unit {unit} -> {normalized_unit}"

        if not plant:
            suspicious = True
            reason = reason or "Missing plant code (Werks)"

        return ParsedRow(
            ok=bool(qty is not None or desc),
            source_row_id=row_id,
            scope=scope,
            category=category,
            activity_date=dt,
            description=desc,
            facility_code=plant,
            quantity=normalized_qty,
            unit=normalized_unit,
            raw_quantity=qty,
            raw_unit=unit,
            distance_km=None,
            origin="",
            destination="",
            supplier=vendor,
            metadata={
                "material": row.get("material", ""),
                "material_group": mat_group,
                "company_code": row.get("company_code", ""),
            },
            is_suspicious=suspicious,
            suspicious_reason=reason,
            parse_error="" if qty is not None else "Missing quantity",
            fingerprint=_fingerprint("sap", row_id, str(row)),
        )

    def _normalize_quantity(
        self, qty: Decimal | None, unit: str
    ) -> tuple[Decimal | None, str]:
        if qty is None:
            return None, ""
        conversions = {
            "L": ("liters", Decimal("1")),
            "LTR": ("liters", Decimal("1")),
            "GAL": ("liters", Decimal("3.78541")),
            "M3": ("liters", Decimal("1000")),
            "KG": ("kg", Decimal("1")),
            "ST": ("each", Decimal("1")),
            "EA": ("each", Decimal("1")),
        }
        if unit in conversions:
            name, factor = conversions[unit]
            return qty * factor, name
        return qty, unit.lower() if unit else ""


class UtilityCSVParser:
    """Utility portal monthly CSV export; subset: electricity kWh per billing period."""

    def parse(self, content: str) -> list[ParsedRow]:
        _, rows = _read_csv_rows(content)
        results: list[ParsedRow] = []
        for idx, raw in enumerate(rows, start=1):
            row = _map_row(raw, UTILITY_HEADER_MAP)
            row_id = f"UTL-{idx}"
            results.append(self._parse_row(row_id, row))
        return results

    def _parse_row(self, row_id: str, row: dict[str, str]) -> ParsedRow:
        usage = _parse_decimal(row.get("usage_kwh", ""))
        period_start = _parse_date(row.get("period_start", ""))
        period_end = _parse_date(row.get("period_end", ""))
        meter = row.get("meter_id", "")
        address = row.get("address", "")

        suspicious = False
        reason = ""
        if usage and usage > 500000:
            suspicious = True
            reason = "Monthly kWh exceeds typical commercial threshold"
        if period_start and period_end and period_end < period_start:
            suspicious = True
            reason = reason or "Billing period end before start"

        activity_date = period_end or period_start
        return ParsedRow(
            ok=usage is not None,
            source_row_id=row_id,
            scope="2",
            category="electricity",
            activity_date=activity_date,
            description=f"Electricity — {address[:80]}",
            facility_code=meter,
            quantity=usage,
            unit="kwh",
            raw_quantity=usage,
            raw_unit="kwh",
            distance_km=None,
            origin="",
            destination="",
            supplier=row.get("tariff", ""),
            metadata={
                "account": row.get("account", ""),
                "period_start": row.get("period_start", ""),
                "period_end": row.get("period_end", ""),
                "peak_kw": row.get("peak_kw", ""),
                "total_charges": row.get("total_charges", ""),
            },
            is_suspicious=suspicious,
            suspicious_reason=reason,
            parse_error="" if usage is not None else "Missing usage (kWh)",
            fingerprint=_fingerprint("utility", row_id, str(row)),
        )


class TravelExportParser:
    """Concur-style expense CSV; subset: flights, hotels, ground."""

    def parse(self, content: str) -> list[ParsedRow]:
        _, rows = _read_csv_rows(content)
        results: list[ParsedRow] = []
        for idx, raw in enumerate(rows, start=1):
            row = _map_row(raw, TRAVEL_HEADER_MAP)
            row_id = row.get("expense_id") or f"TRV-{idx}"
            results.append(self._parse_row(row_id, row))
        return results

    def _parse_row(self, row_id: str, row: dict[str, str]) -> ParsedRow:
        expense_type = (row.get("expense_type") or "").lower()
        dt = _parse_date(row.get("txn_date", ""))
        origin = (row.get("origin") or "").upper()
        dest = (row.get("destination") or "").upper()
        distance = _parse_decimal(row.get("distance_km", ""))
        amount = _parse_decimal(row.get("amount", ""))
        vendor = row.get("vendor", "")
        city = row.get("city", "")
        nights = _parse_decimal(row.get("nights", ""))

        category = "ground"
        scope = "3"
        if "air" in expense_type or "flight" in expense_type:
            category = "flight"
        elif "hotel" in expense_type or "lodging" in expense_type:
            category = "hotel"
        elif "rail" in expense_type or "taxi" in expense_type or "ground" in expense_type:
            category = "ground"

        suspicious = False
        reason = ""
        if category == "flight" and not distance and origin and dest:
            suspicious = True
            reason = "Flight without distance — needs airport-pair estimation"
        if category == "flight" and not origin:
            suspicious = True
            reason = reason or "Flight missing origin airport code"
        if amount and amount > 15000:
            suspicious = True
            reason = reason or "Unusually high travel expense amount"

        desc = f"{expense_type.title()} — {vendor or city}"
        qty = distance or nights or amount
        unit = "km" if distance else ("nights" if nights else "usd")

        return ParsedRow(
            ok=bool(expense_type),
            source_row_id=row_id,
            scope=scope,
            category=category,
            activity_date=dt,
            description=desc,
            facility_code="",
            quantity=qty,
            unit=unit,
            raw_quantity=qty,
            raw_unit=unit,
            distance_km=distance,
            origin=origin,
            destination=dest,
            supplier=vendor,
            metadata={
                "employee_id": row.get("employee_id", ""),
                "currency": row.get("currency", "USD"),
                "amount": str(amount) if amount else "",
            },
            is_suspicious=suspicious,
            suspicious_reason=reason,
            parse_error="" if expense_type else "Missing expense type",
            fingerprint=_fingerprint("travel", row_id, str(row)),
        )
