from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "ATLAS_TERRITORY_LA_EVIDENCE_FACT_V1"
ALLOWED_PRECISION = {"commune_explicit", "region_explicit", "national_only"}


def _clean(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def normalize_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a published LA fact. Never infer phenomenon location from court location."""
    evidence_type = _clean(raw.get("evidence_type"))
    source_url = _clean(raw.get("source_url"))
    precision = _clean(raw.get("location_precision"))
    if not evidence_type or not source_url:
        raise ValueError("evidence_type and source_url are required")
    if precision not in ALLOWED_PRECISION:
        raise ValueError(f"location_precision must be one of {sorted(ALLOWED_PRECISION)}")

    region = _clean(raw.get("region"))
    commune = _clean(raw.get("commune"))
    if precision == "commune_explicit" and (not region or not commune):
        raise ValueError("commune_explicit requires region and commune")
    if precision == "region_explicit" and not region:
        raise ValueError("region_explicit requires region")
    if precision != "commune_explicit":
        commune = None

    return {
        "schema": SCHEMA,
        "evidence_id": _clean(raw.get("evidence_id")),
        "evidence_type": evidence_type,
        "case_year": int(raw["case_year"]) if raw.get("case_year") not in (None, "") else None,
        "predicate_offence": _clean(raw.get("predicate_offence")),
        "typology": _clean(raw.get("typology")),
        "region": region,
        "commune": commune,
        "location_precision": precision,
        "location_basis": _clean(raw.get("location_basis")),
        "amount_clp": float(raw["amount_clp"]) if raw.get("amount_clp") not in (None, "") else None,
        "forfeiture_clp": float(raw["forfeiture_clp"]) if raw.get("forfeiture_clp") not in (None, "") else None,
        "source_name": _clean(raw.get("source_name")),
        "source_url": source_url,
        "source_date": _clean(raw.get("source_date")),
    }


def normalize(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_record(r) for r in records]


def _load(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("input must be a JSON array")
    return data


def self_test() -> None:
    row = normalize_record({
        "evidence_type": "conviction", "case_year": 2024,
        "region": "Región Demo", "location_precision": "region_explicit",
        "location_basis": "region stated by official publication",
        "source_url": "https://example.invalid"
    })
    assert row["commune"] is None
    assert "score" not in row and "risk" not in row
    print("territory_la_evidence: OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test(); return
    if not args.input or not args.out:
        ap.error("--input and --out are required unless --self-test is used")
    rows = normalize(_load(args.input))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
