"""ATLAS AML v1 · construcción de hechos canónicos en Parquet.

Lee el JSONL uniforme que producen los adaptadores y emite Parquet tipado y
comprimido, listo para consultarse desde el navegador con DuckDB-WASM o desde
el motor de scoring protegido.

REGLA DE SEPARACIÓN — este módulo pertenece al repositorio PÚBLICO:
    produce HECHOS, nunca CRITERIOS.
No contiene umbrales, pesos, marcas de riesgo ni reglas de selección. Eso vive
en el repositorio de metodología, que es privado.

Uso:
    python -m src.build --raw data/raw --staged data/staged --out data/parquet
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from . import adapters

# Tipado explícito por tabla. Lo que no se declara queda como lo infiere DuckDB.
CASTS: dict[str, dict[str, str]] = {
    "sanction_event": {
        "event_date": "DATE",
        "decision_year": "INTEGER",
        "amount": "DOUBLE",
        "document_confidence": "DOUBLE",
        "laft_direct_flag": "BOOLEAN",
    },
    "tax_profile": {
        "activity_start_date": "DATE",
        "termination_date": "DATE",
        "commercial_year": "INTEGER",
        "workers": "BIGINT",
        "sales_band_code": "INTEGER",
    },
    "entity_osfl": {"identity_confidence": "DOUBLE", "evidence_count": "INTEGER"},
}


def build(staged: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    tables: dict[str, dict] = {}

    for name in adapters.ADAPTERS:
        src = staged / f"{name}.jsonl"
        if not src.exists():
            continue

        cols = [
            c[0]
            for c in con.execute(
                f"SELECT * FROM read_json_auto('{src}', format='newline_delimited', "
                f"union_by_name=true) LIMIT 0"
            ).description
        ]
        casts = CASTS.get(name, {})
        projection = ", ".join(
            f"TRY_CAST({c} AS {casts[c]}) AS {c}" if c in casts else c for c in cols
        )

        target = out / f"{name}.parquet"
        con.execute(
            f"""
            COPY (
                SELECT {projection}
                FROM read_json_auto('{src}', format='newline_delimited',
                                    union_by_name=true)
            ) TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )
        rows = con.execute(f"SELECT count(*) FROM '{target}'").fetchone()[0]
        size = target.stat().st_size
        raw_size = src.stat().st_size
        tables[name] = {
            "rows": rows,
            "parquet_bytes": size,
            "jsonl_bytes": raw_size,
            "compression_ratio": round(raw_size / size, 1) if size else None,
        }
        print(
            f"[parquet] {name:<22} {rows:>8,} filas  "
            f"{size:>9,} B  ({raw_size / size:.1f}× vs JSONL)"
        )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layer": "PUBLIC_FACTS",
        "contains_criteria": False,
        "contains_scores": False,
        "contains_aml_marks": False,
        "identity_rule": "ENT-RUT-{RUT}; nunca por similitud de nombre",
        "tables": tables,
    }
    (out / "_build.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--staged", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    print("== adaptación de formas ==")
    adapters.run(args.raw, args.staged)
    print("\n== construcción Parquet ==")
    m = build(args.staged, args.out)

    rows = sum(t["rows"] for t in m["tables"].values())
    pq = sum(t["parquet_bytes"] for t in m["tables"].values())
    js = sum(t["jsonl_bytes"] for t in m["tables"].values())
    print(f"\n{len(m['tables'])} tablas · {rows:,} filas · {pq:,} B Parquet")
    print(f"Reducción frente a JSONL: {js:,} → {pq:,} B ({js / pq:.1f}×)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
