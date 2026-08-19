"""ATLAS AML v1 · ingesta sellada de contratos públicos.

Descarga cada artefacto declarado en contracts/producers.yml y lo sella con
SHA-256, tamaño y fecha. Mantiene la disciplina de trazabilidad del sistema v0:
un hecho de fuente nunca entra sin su sello.

No usa credenciales. Todos los contratos son públicos.
No escribe en los repositorios de origen.

Uso:
    python -m src.fetch --out data/raw
    python -m src.fetch --out data/raw --local-root /ruta/a/repos   # desarrollo
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts" / "producers.yml"
TIMEOUT = 120
USER_AGENT = "atlas-aml-pipeline/1.0 (+https://github.com/smoralesm07-source)"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_remote(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, dest.open("wb") as out:
        if resp.status != 200:
            raise RuntimeError(f"{url}: HTTP {resp.status}")
        shutil.copyfileobj(resp, out)


def resolve_local(local_root: Path, repo: str, path: str) -> Path:
    """Mapea la ruta pública /<repo>/data/<archivo> al clon local docs/data/<archivo>."""
    return local_root / repo / "docs" / "data" / Path(path).name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument(
        "--local-root",
        type=Path,
        default=None,
        help="Si se entrega, lee de clones locales en vez de la red (desarrollo).",
    )
    args = ap.parse_args()

    spec = yaml.safe_load(CONTRACTS.read_text(encoding="utf-8"))
    base = spec["base"].rstrip("/")
    args.out.mkdir(parents=True, exist_ok=True)

    seals: list[dict] = []
    failures: list[dict] = []

    for producer, pspec in spec["producers"].items():
        repo = pspec["repo"]
        for name, aspec in pspec["artifacts"].items():
            rel = aspec["path"]
            url = f"{base}{rel}"
            dest = args.out / f"{producer}__{name}{Path(rel).suffix}"
            try:
                if args.local_root:
                    src = resolve_local(args.local_root, repo, rel)
                    if not src.exists():
                        raise FileNotFoundError(src)
                    shutil.copyfile(src, dest)
                    origin = f"file://{src}"
                else:
                    fetch_remote(url, dest)
                    origin = url

                seals.append(
                    {
                        "producer": producer,
                        "artifact": name,
                        "origin": origin,
                        "public_url": url,
                        "format": aspec["format"],
                        "bytes": dest.stat().st_size,
                        "sha256": sha256_of(dest),
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "guardrails": pspec.get("guardrails", []),
                    }
                )
                print(f"[ok]   {producer}/{name}  {dest.stat().st_size:>10,} B")
            except Exception as exc:  # noqa: BLE001 - se reporta, no se oculta
                # Falla de fuente NO es ausencia del fenómeno: se registra explícito.
                failures.append({"producer": producer, "artifact": name,
                                 "url": url, "error": str(exc)})
                print(f"[FALLA] {producer}/{name}: {exc}", file=sys.stderr)

    manifest = {
        "manifest_version": spec["manifest_version"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "LOCAL_DEV" if args.local_root else "PUBLIC_HTTPS",
        "sealed": seals,
        "failures": failures,
        "policy": {
            "source_failure_is_not_zero": True,
            "no_write_access_to_producers": True,
            "no_credentials_required": True,
        },
    }
    (args.out / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nSellados {len(seals)} artefactos · {len(failures)} fallas")
    # Una falla parcial no aborta la corrida: el build decide si puede continuar.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
