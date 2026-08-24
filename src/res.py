"""Ingesta pública del Registro de Empresas y Sociedades (RES).

Fuente permitida: dataset oficial de Datos.gob.cl. Este módulo NO consulta ni
raspa registrodeempresasysociedades.cl. Descubre los CSV publicados en CKAN,
los sella con SHA-256 y produce hechos canónicos en Parquet.

Salidas:
- res_constitution.parquet: una fila por actuación publicada en el dataset.
- res_company.parquet: una fila canónica por RUT.
- res_address.parquet: comunas/regiones social y tributaria publicadas.
- _res_build.json: trazabilidad de recursos, hashes y cobertura.

La fuente abierta publicada por RES cubre constituciones y atributos básicos.
Socios, accionistas, administradores y modificaciones documentales NO se
infieren desde este CSV y deben provenir de evidencia documental separada.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import duckdb

DATASET_ID = "363edd60-4919-4ff1-b85f-f8e14d61285a"
PACKAGE_ENDPOINTS = (
    "https://datos.gob.cl/api/3/action/package_show",
    "https://datos.gob.cl/es/api/3/action/package_show",
)
UA = "Atlas-AML-RES/1.0 (+public-facts; no-site-scraping)"

ALIASES = {
    "source_record_id": ("id", "_id"),
    "rut": ("rut",),
    "legal_name": ("razon_social", "razon_social_"),
    "actuation_date": ("fecha_de_actuacion_1era_firma", "fecha_de_actuacion"),
    "registry_date": ("fecha_de_registro_ultima_firma", "fecha_de_registro"),
    "sii_approval_date": ("fecha_de_aprobacion_x_sii", "fecha_aprobacion_x_sii"),
    "source_year": ("anio", "ano"),
    "source_month": ("mes",),
    "tax_commune": ("comuna_tributaria",),
    "tax_region": ("region_tributaria",),
    "company_code": ("codigo_de_sociedad", "codigo_sociedad"),
    "actuation_type": ("tipo_de_actuacion", "tipo_actuacion"),
    "capital": ("capital",),
    "social_commune": ("comuna_social",),
    "social_region": ("region_social",),
}


def _json(url: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def package_show() -> dict:
    last: Exception | None = None
    query = urllib.parse.urlencode({"id": DATASET_ID})
    for base in PACKAGE_ENDPOINTS:
        try:
            payload = _json(f"{base}?{query}")
            if payload.get("success") and isinstance(payload.get("result"), dict):
                return payload["result"]
        except Exception as exc:  # pragma: no cover - depende de red externa
            last = exc
    raise RuntimeError(f"No fue posible consultar metadata CKAN RES: {type(last).__name__ if last else 'unknown'}")


def _is_res_csv(resource: dict) -> bool:
    fmt = str(resource.get("format") or "").lower()
    name = " ".join(str(resource.get(k) or "") for k in ("name", "url", "description")).lower()
    return fmt == "csv" and "constit" in name and "sociedad" in name


def resources_from_package(package: dict) -> list[dict]:
    resources = [r for r in package.get("resources") or [] if isinstance(r, dict) and _is_res_csv(r)]
    if not resources:
        raise RuntimeError("El paquete RES no contiene recursos CSV de constituciones reconocibles")
    return resources


def _download(url: str, dest: Path) -> tuple[str, int]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != "datos.gob.cl":
        raise ValueError("URL RES fuera de datos.gob.cl")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    h = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=300) as response, dest.open("wb") as out:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            out.write(block)
            h.update(block)
            size += len(block)
    return h.hexdigest(), size


def fetch(raw: Path) -> dict:
    raw.mkdir(parents=True, exist_ok=True)
    package = package_show()
    sealed: list[dict] = []
    failures: list[dict] = []
    for r in resources_from_package(package):
        rid = str(r.get("id") or "")
        url = str(r.get("url") or "")
        filename = Path(urllib.parse.urlsplit(url).path).name or f"{rid}.csv"
        dest = raw / f"{rid}__{filename}"
        try:
            sha256, size = _download(url, dest)
            sealed.append({
                "resource_id": rid,
                "name": r.get("name"),
                "url": url,
                "ckan_hash": r.get("hash"),
                "sha256": sha256,
                "bytes": size,
                "last_modified": r.get("last_modified") or r.get("metadata_modified"),
                "created": r.get("created"),
                "path": str(dest),
            })
            print(f"[RES] {filename}: {size:,} B · sha256={sha256[:12]}…")
        except Exception as exc:  # pragma: no cover - depende de red externa
            failures.append({"resource_id": rid, "url": url, "error": f"{type(exc).__name__}: {exc}"})
            print(f"[RES][WARN] {rid}: {type(exc).__name__}: {exc}")
    manifest = {
        "dataset_id": DATASET_ID,
        "dataset_title": package.get("title"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "license": package.get("license_title") or package.get("license_id"),
        "sealed": sealed,
        "failures": failures,
        "collection_mode": "DATOS_GOB_CKAN",
        "scrapes_res_website": False,
    }
    (raw / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if not sealed:
        raise RuntimeError("No se pudo sellar ningún recurso RES")
    return manifest


def _qid(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _pick(columns: set[str], key: str, required: bool = False) -> str:
    for alias in ALIASES[key]:
        if alias in columns:
            return _qid(alias)
    if required:
        raise RuntimeError(f"Columna RES requerida no resuelta: {key}; disponibles={sorted(columns)}")
    return "NULL"


def _date(expr: str) -> str:
    if expr == "NULL":
        return "NULL::DATE"
    return (
        f"COALESCE(TRY_CAST({expr} AS DATE), "
        f"CAST(TRY_STRPTIME(TRIM({expr}), '%d-%m-%Y') AS DATE), "
        f"CAST(TRY_STRPTIME(TRIM({expr}), '%d/%m/%Y') AS DATE))"
    )


def _num(expr: str, sql_type: str) -> str:
    if expr == "NULL":
        return f"NULL::{sql_type}"
    return f"TRY_CAST(REGEXP_REPLACE(TRIM({expr}), '[^0-9-]', '', 'g') AS {sql_type})"


def _sql_text(expr: str) -> str:
    return "NULL::VARCHAR" if expr == "NULL" else f"NULLIF(TRIM({expr}), '')"


def _insert_csv(con: duckdb.DuckDBPyConnection, path: Path, meta: dict) -> int:
    p = str(path).replace("'", "''")
    rel = f"read_csv_auto('{p}', header=true, all_varchar=true, normalize_names=true, union_by_name=true)"
    columns = {d[0] for d in con.execute(f"SELECT * FROM {rel} LIMIT 0").description}
    src_id = _pick(columns, "source_record_id")
    rut = _pick(columns, "rut", required=True)
    legal = _pick(columns, "legal_name", required=True)
    act_date = _pick(columns, "actuation_date")
    reg_date = _pick(columns, "registry_date")
    sii_date = _pick(columns, "sii_approval_date")
    year = _pick(columns, "source_year")
    month = _pick(columns, "source_month")
    tax_commune = _pick(columns, "tax_commune")
    tax_region = _pick(columns, "tax_region")
    company_code = _pick(columns, "company_code")
    act_type = _pick(columns, "actuation_type")
    capital = _pick(columns, "capital")
    social_commune = _pick(columns, "social_commune")
    social_region = _pick(columns, "social_region")
    resource_id = str(meta.get("resource_id") or "").replace("'", "''")
    source_hash = str(meta.get("sha256") or "").replace("'", "''")
    source_url = str(meta.get("url") or "").replace("'", "''")

    con.execute(f"""
        INSERT INTO res_raw
        SELECT
          {_sql_text(src_id)} AS source_record_id,
          REGEXP_REPLACE(UPPER(TRIM({rut})), '[^0-9K-]', '', 'g') AS rut,
          REGEXP_REPLACE(UPPER(TRIM({rut})), '[^0-9K]', '', 'g') AS rut_key,
          {_sql_text(legal)} AS legal_name,
          {_date(act_date)} AS actuation_date,
          {_date(reg_date)} AS registry_date,
          {_date(sii_date)} AS sii_approval_date,
          {_num(year, 'INTEGER')} AS source_year,
          {_sql_text(month)} AS source_month,
          {_sql_text(tax_commune)} AS tax_commune,
          {_num(tax_region, 'INTEGER')} AS tax_region,
          {_sql_text(company_code)} AS company_code,
          UPPER(COALESCE({_sql_text(act_type)}, 'CONSTITUCIÓN')) AS actuation_type,
          {_num(capital, 'DOUBLE')} AS capital,
          {_sql_text(social_commune)} AS social_commune,
          {_num(social_region, 'INTEGER')} AS social_region,
          '{resource_id}' AS source_resource_id,
          '{source_hash}' AS source_sha256,
          '{source_url}' AS source_url
        FROM {rel}
        WHERE NULLIF(TRIM({rut}), '') IS NOT NULL
    """)
    return int(con.execute("SELECT changes()").fetchone()[0]) if False else 0


def build(raw: Path, out: Path) -> dict:
    manifest = json.loads((raw / "_manifest.json").read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("""
      CREATE TABLE res_raw (
        source_record_id VARCHAR, rut VARCHAR, rut_key VARCHAR, legal_name VARCHAR,
        actuation_date DATE, registry_date DATE, sii_approval_date DATE,
        source_year INTEGER, source_month VARCHAR, tax_commune VARCHAR,
        tax_region INTEGER, company_code VARCHAR, actuation_type VARCHAR,
        capital DOUBLE, social_commune VARCHAR, social_region INTEGER,
        source_resource_id VARCHAR, source_sha256 VARCHAR, source_url VARCHAR
      )
    """)

    loaded_files = 0
    for meta in manifest["sealed"]:
        path = Path(meta["path"])
        if not path.exists():
            continue
        _insert_csv(con, path, meta)
        loaded_files += 1
    if loaded_files == 0:
        raise RuntimeError("Manifest RES sin archivos locales utilizables")

    constitution = out / "res_constitution.parquet"
    company = out / "res_company.parquet"
    address = out / "res_address.parquet"
    con.execute(f"""
      COPY (
        SELECT
          CASE WHEN rut_key <> '' THEN 'ENT-RUT-' || rut_key END AS entity_id,
          source_record_id, rut, rut_key, legal_name,
          actuation_date AS constitution_date, registry_date, sii_approval_date,
          source_year, source_month, tax_commune, tax_region, company_code,
          actuation_type, capital, social_commune, social_region,
          source_resource_id, source_sha256, source_url
        FROM res_raw
      ) TO '{constitution}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    con.execute(f"""
      COPY (
        SELECT * EXCLUDE (rn) FROM (
          SELECT
            CASE WHEN rut_key <> '' THEN 'ENT-RUT-' || rut_key END AS entity_id,
            rut, rut_key, legal_name, actuation_date AS constitution_date,
            registry_date, sii_approval_date, source_year, source_month,
            tax_commune, tax_region, company_code, capital,
            social_commune, social_region, source_resource_id,
            source_sha256, source_url,
            ROW_NUMBER() OVER (
              PARTITION BY rut_key
              ORDER BY actuation_date DESC NULLS LAST, registry_date DESC NULLS LAST,
                       source_year DESC NULLS LAST, source_record_id DESC NULLS LAST
            ) AS rn
          FROM res_raw WHERE rut_key <> ''
        ) WHERE rn = 1
      ) TO '{company}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    con.execute(f"""
      COPY (
        SELECT entity_id, rut, address_type, commune, region,
               constitution_date AS valid_from, source_resource_id, source_sha256
        FROM (
          SELECT 'ENT-RUT-' || rut_key AS entity_id, rut, 'SOCIAL' AS address_type,
                 social_commune AS commune, social_region AS region,
                 actuation_date AS constitution_date, source_resource_id, source_sha256
          FROM res_raw WHERE rut_key <> '' AND social_commune IS NOT NULL
          UNION ALL
          SELECT 'ENT-RUT-' || rut_key, rut, 'TRIBUTARIO', tax_commune, tax_region,
                 actuation_date, source_resource_id, source_sha256
          FROM res_raw WHERE rut_key <> '' AND tax_commune IS NOT NULL
        )
      ) TO '{address}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    rows_raw = con.execute("SELECT count(*) FROM res_raw").fetchone()[0]
    rows_company = con.execute(f"SELECT count(*) FROM '{company}'").fetchone()[0]
    rows_address = con.execute(f"SELECT count(*) FROM '{address}'").fetchone()[0]
    rut_coverage = con.execute("SELECT avg(CASE WHEN rut_key <> '' THEN 1.0 ELSE 0 END) FROM res_raw").fetchone()[0]
    legal_coverage = con.execute("SELECT avg(CASE WHEN legal_name IS NOT NULL THEN 1.0 ELSE 0 END) FROM res_raw").fetchone()[0]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layer": "PUBLIC_FACTS",
        "source": "Registro de Empresas y Sociedades vía Datos.gob.cl",
        "dataset_id": DATASET_ID,
        "resources_loaded": loaded_files,
        "rows_constitution": rows_raw,
        "rows_company": rows_company,
        "rows_address": rows_address,
        "identity_coverage": round(float(rut_coverage or 0), 6),
        "legal_name_coverage": round(float(legal_coverage or 0), 6),
        "contains_criteria": False,
        "contains_scores": False,
        "contains_aml_marks": False,
        "scrapes_res_website": False,
        "open_dataset_scope": ["constitución", "fechas", "capital", "tipo societario", "comuna/región social y tributaria"],
        "not_inferred_from_open_csv": ["socios", "accionistas vigentes", "administradores", "modificaciones documentales", "beneficiario final"],
        "files": {
            "res_constitution.parquet": constitution.stat().st_size,
            "res_company.parquet": company.stat().st_size,
            "res_address.parquet": address.stat().st_size,
        },
    }
    (out / "_res_build.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[RES] {rows_raw:,} constituciones · {rows_company:,} RUT · {rows_address:,} domicilios comunales")
    return result


def self_test() -> None:
    sample = """ID;RUT;Razon Social;Fecha de actuacion (1era firma);Fecha de registro (ultima firma);Fecha de aprobacion x SII;Anio;Mes;Comuna Tributaria;Region Tributaria;Codigo de sociedad;Tipo de actuacion;Capital;Comuna Social;Region Social\n1;78325627-4;Astraly SpA;01-01-2026;01-01-2026;01-01-2026;2026;Enero;EST CENTRAL;13;SpA;CONSTITUCIÓN;1000000;EST CENTRAL;13\n"""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        raw, out = root / "raw", root / "out"
        raw.mkdir()
        csv_path = raw / "sample.csv"
        csv_path.write_text(sample, encoding="utf-8")
        sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        manifest = {"sealed": [{"resource_id": "test", "sha256": sha, "url": "https://datos.gob.cl/test.csv", "path": str(csv_path)}]}
        (raw / "_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = build(raw, out)
        assert result["rows_company"] == 1
        row = duckdb.connect().execute(f"SELECT entity_id, rut_key, capital FROM '{out / 'res_company.parquet'}'").fetchone()
        assert row == ("ENT-RUT-783256274", "783256274", 1000000.0), row
    print("[OK] RES self-test")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("data/raw/res"))
    ap.add_argument("--out", type=Path, default=Path("site/data"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    fetch(args.raw)
    build(args.raw, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
