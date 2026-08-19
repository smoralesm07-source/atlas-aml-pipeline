"""ATLAS AML v1 · adaptadores de forma por productor.

Cada radar publica su contrato con un contenedor distinto: arreglo JSON,
diccionario indexado por RUT, JSONL, u objeto anidado. Normalizar esa varianza
en SQL es frágil; aquí se resuelve una sola vez y se emite JSONL uniforme para
que DuckDB haga el trabajo tipado sobre una forma estable.

Un adaptador SOLO cambia la forma del contenedor y normaliza la identidad.
No filtra, no interpreta, no puntúa. Si un registro no tiene identidad
resoluble, se emite igual con `entity_id = null` y se cuenta como cobertura:
ausencia de identidad no es ausencia del hecho.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator

RUT_CLEAN = re.compile(r"[^0-9K]")


def canonical_entity_id(rut: str | None) -> str | None:
    """ENT-RUT-{RUT normalizado}. Devuelve None si no hay RUT utilizable.

    No inventa identidad: sin RUT no hay entity_id derivado.
    """
    if not rut:
        return None
    cleaned = RUT_CLEAN.sub("", str(rut).upper().strip())
    return f"ENT-RUT-{cleaned}" if cleaned else None


def _iter_container(payload, keys: tuple[str, ...] = ()) -> Iterator[dict]:
    """Recorre arreglo o diccionario indexado, devolviendo registros."""
    node = payload
    for k in keys:
        if not isinstance(node, dict):
            return
        node = node.get(k)
    if isinstance(node, list):
        yield from (r for r in node if isinstance(r, dict))
    elif isinstance(node, dict):
        # Diccionario indexado por clave natural (p. ej. RUT).
        for key, value in node.items():
            if isinstance(value, dict):
                yield {"_container_key": key, **value}


def adapt_sanctions(src: Path) -> Iterator[dict]:
    """Radar Sanciones · arreglo JSON de eventos."""
    payload = json.loads(src.read_text(encoding="utf-8"))
    for r in _iter_container(payload):
        # El productor ya resuelve identidad bajo su propio gobierno;
        # se prefiere su entity_id y el RUT actúa sólo como respaldo.
        eid = (r.get("entity_id") or "").strip() or canonical_entity_id(r.get("rut_fuente"))
        yield {
            "source_event_id": r.get("id"),
            "entity_id": eid,
            "rut": r.get("rut_fuente"),
            "subject_name": r.get("sujeto_fuente"),
            "regulator": r.get("supervisor"),
            "event_date": r.get("fecha"),
            "decision_year": r.get("decision_year"),
            "category": r.get("categoria"),
            "event_type": r.get("tipo_evento"),
            "status": r.get("estado"),
            "amount": r.get("monto"),
            "amount_unit": r.get("unidad"),
            "laft_direct_flag": r.get("laft_directo"),
            "document_status": r.get("document_status"),
            "document_confidence": r.get("document_confidence"),
            "evidence_id": r.get("evidence_id"),
            "source_record_id": r.get("source_record_id"),
            "resolution_url": r.get("resolution_url"),
        }


def adapt_tax_profile(src: Path) -> Iterator[dict]:
    """Radar Presupuesto Abierto · diccionario indexado por RUT."""
    payload = json.loads(src.read_text(encoding="utf-8"))
    for r in _iter_container(payload, ("entities",)):
        rut = r.get("rut") or r.get("_container_key")
        yield {
            "entity_id": (r.get("entity_id") or "").strip() or canonical_entity_id(rut),
            "rut": rut,
            "legal_name": r.get("legal_name"),
            "tax_status": r.get("tax_status"),
            "activity_start_date": r.get("start_date"),
            "termination_date": r.get("termination_date"),
            "commercial_year": r.get("commercial_year"),
            "sales_band_code": r.get("sales_band_code"),
            "sales_band_label": r.get("sales_band_label"),
            "workers": r.get("workers"),
            "main_region": r.get("main_region"),
            "main_activity": r.get("main_activity"),
            "acteco": r.get("acteco"),
            "taxpayer_type": r.get("taxpayer_type"),
            "negative_equity_band": r.get("negative_equity_band"),
            # Marcas del radar de origen: hecho con procedencia, no señal AML.
            "source_marks": r.get("marks") or [],
            "history_years": r.get("history_available_years") or [],
        }


def adapt_osfl(src: Path) -> Iterator[dict]:
    """Radar OSFL · JSONL ya en esquema canónico Entity."""
    with src.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield {
                "entity_id": r.get("entity_id"),
                "entity_type": r.get("entity_type"),
                "canonical_name": r.get("canonical_name"),
                "rut": r.get("rut_normalized"),
                "identity_method": r.get("identity_method"),
                "identity_confidence": r.get("identity_confidence"),
                "evidence_count": len(r.get("evidence_ids") or []),
            }


def adapt_sector_reportability(src: Path) -> Iterator[dict]:
    """Radar UAF · grano SECTOR, deliberadamente sin llave de entidad."""
    payload = json.loads(src.read_text(encoding="utf-8"))
    for r in _iter_container(payload, ("sectors",)):
        yield {k: v for k, v in r.items() if not isinstance(v, (dict, list))}


ADAPTERS = {
    "sanction_event": ("RADAR_SANCIONES__events.json", adapt_sanctions),
    "tax_profile": ("RADAR_PRESUPUESTO__entity_enrichment.json", adapt_tax_profile),
    "entity_osfl": ("RADAR_OSFL__entity_hub.jsonl", adapt_osfl),
    "sector_reportability": ("RADAR_UAF__reportability.json", adapt_sector_reportability),
}


def run(raw: Path, staged: Path) -> dict[str, dict]:
    staged.mkdir(parents=True, exist_ok=True)
    report: dict[str, dict] = {}
    for name, (filename, fn) in ADAPTERS.items():
        src = raw / filename
        if not src.exists():
            report[name] = {"status": "SOURCE_MISSING", "rows": 0}
            print(f"[falta] {name}: {filename}")
            continue
        dest = staged / f"{name}.jsonl"
        rows = with_id = 0
        with dest.open("w", encoding="utf-8") as out:
            for rec in fn(src):
                rows += 1
                if rec.get("entity_id"):
                    with_id += 1
                out.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        has_identity = "entity_id" in (rec if rows else {})
        report[name] = {
            "status": "OK",
            "rows": rows,
            "with_entity_id": with_id if has_identity else None,
            "identity_coverage": round(with_id / rows, 4) if (rows and has_identity) else None,
        }
        cov = report[name]["identity_coverage"]
        cov_txt = f"· identidad {cov:.1%}" if cov is not None else "· sin llave de entidad (por diseño)"
        print(f"[stage] {name:<22} {rows:>8,} filas {cov_txt}")
    return report
