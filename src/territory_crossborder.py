from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "ATLAS_TERRITORY_CROSSBORDER_FACT_V1"


def _clean(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def normalize_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize an official border/logistics fact without deriving risk or score."""
    node_type = (_clean(raw.get("node_type")) or "").lower()
    if node_type not in {"border_crossing", "port", "international_airport", "customs_office"}:
        raise ValueError(f"unsupported node_type: {node_type!r}")
    name = _clean(raw.get("name"))
    region = _clean(raw.get("region"))
    if not name or not region:
        raise ValueError("name and region are required")

    lat = raw.get("lat")
    lon = raw.get("lon")
    lat = float(lat) if lat not in (None, "") else None
    lon = float(lon) if lon not in (None, "") else None
    if (lat is None) != (lon is None):
        raise ValueError("lat/lon must be both present or both absent")

    return {
        "schema": SCHEMA,
        "node_type": node_type,
        "name": name,
        "region": region,
        "commune": _clean(raw.get("commune")),
        "lat": lat,
        "lon": lon,
        "cargo_enabled": raw.get("cargo_enabled") if isinstance(raw.get("cargo_enabled"), bool) else None,
        "international_enabled": raw.get("international_enabled") if isinstance(raw.get("international_enabled"), bool) else None,
        "flow_period": _clean(raw.get("flow_period")),
        "flow_value": float(raw["flow_value"]) if raw.get("flow_value") not in (None, "") else None,
        "flow_unit": _clean(raw.get("flow_unit")),
        "source_name": _clean(raw.get("source_name")),
        "source_url": _clean(raw.get("source_url")),
        "source_date": _clean(raw.get("source_date")),
        "location_precision": _clean(raw.get("location_precision")) or ("coordinate" if lat is not None else "region"),
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
        "node_type": "border_crossing", "name": "Paso Demo", "region": "Región Demo",
        "lat": -20.0, "lon": -68.0, "cargo_enabled": True,
        "source_name": "Fuente oficial", "source_url": "https://example.invalid"
    })
    assert row["schema"] == SCHEMA
    assert row["cargo_enabled"] is True
    assert "score" not in row and "risk" not in row
    print("territory_crossborder: OK")


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
