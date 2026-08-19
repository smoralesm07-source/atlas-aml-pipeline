# ATLAS AML v1 · capa pública de ingesta y cómputo

Sistema paralelo a `AML-Workbench-Portal`. **No comparte con él repositorio,
URL, base de datos ni credenciales.**

## Qué contiene este repositorio

Hechos, no criterios.

- Adaptadores que normalizan la forma de cada contrato de radar.
- Construcción de tablas canónicas en Parquet.
- El shell del portal, sin lógica de riesgo.

## Qué NO contiene, por diseño

- Umbrales, pesos, curvas de intensidad ni reglas de selección.
- Marcas de riesgo ni scores.
- Datos AML materializados.

Esos activos viven en `atlas-aml-methodology`, que es **privado**. El workflow
falla si detecta criterios en esta capa.

## Aislamiento respecto del sistema actual

| Garantía | Cómo se cumple |
|---|---|
| No puede alterar los radares | Sólo hace `GET` a URLs públicas. Sin token, sin permisos de escritura |
| No puede alterar el portal v0 | Repositorio, Pages y base de datos distintos |
| No consume su cuota | Base de datos separada; el cómputo ocurre en Actions |
| No comparte secretos | No usa ninguno en esta capa |

## Cómo correrlo

```bash
pip install duckdb pyyaml

# Producción: lee los contratos públicos por HTTPS
python -m src.fetch --out data/raw

# Desarrollo: lee clones locales, sin red
python -m src.fetch --out data/raw --local-root /ruta/a/los/repos

python -m src.build --raw data/raw --staged data/staged --out site/data
```

## Resultado medido sobre datos reales

| Etapa | Volumen |
|---|---|
| Contratos crudos ingeridos | 48,9 MB |
| JSONL normalizado | 10,2 MB |
| **Parquet canónico publicado** | **943 KB** |

Todo el conjunto analítico cabe bajo 1 MB. Se sirve por CDN desde Pages y se
consulta en el navegador con DuckDB-WASM, sin costo y sin tocar la base de datos.

Tablas producidas:

| Tabla | Filas | Cobertura de identidad |
|---|---:|---|
| `entity_osfl` | 36.832 | 100% |
| `sanction_event` | 976 | 100% |
| `tax_profile` | 869 | 100% |
| `sector_reportability` | 48 | sin llave de entidad, por diseño |

## Una nota sobre identidad

El 73% de los eventos sancionatorios **no trae RUT**, pero el 100% trae
`entity_id` ya resuelto por el radar de origen bajo su propio gobierno. Filtrar
por RUT descartaría dos tercios del universo en silencio.

El adaptador prefiere el `entity_id` del productor y usa el RUT sólo como
respaldo. Esto respeta la regla de no resolver identidad por nombre en esta
capa: la identidad ya viene resuelta desde arriba.

## Estado

Ejecutado y verificado extremo a extremo contra los contratos reales.
Pendiente: adaptador del release Parquet de Radar SII (grafo societario).
