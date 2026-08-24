# ATLAS AML v1 · capa pública de ingesta y cómputo

Sistema paralelo a `AML-Workbench-Portal`. **No comparte con él repositorio,
URL, base de datos ni credenciales.**

## Qué contiene este repositorio

Hechos, no criterios.

- Adaptadores que normalizan la forma de cada contrato de radar.
- Construcción de tablas canónicas en Parquet.
- Ingesta oficial del Registro de Empresas y Sociedades (RES) desde Datos.gob.cl.
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
| No raspa el sitio RES | RES se obtiene exclusivamente del catálogo/API oficial de Datos.gob.cl |

## Registro de Empresas y Sociedades (RES)

`python -m src.res` descubre los CSV oficiales publicados en el dataset RES de
Datos.gob.cl, descarga cada recurso, calcula SHA-256 y produce:

- `res_constitution.parquet`: constituciones y fechas publicadas.
- `res_company.parquet`: maestro por RUT con razón social, capital, tipo y territorio.
- `res_address.parquet`: comuna/región social y tributaria.
- `_res_build.json`: lineage, cobertura, recursos y hashes.

La identidad se construye sólo desde RUT (`ENT-RUT-{RUT}`), nunca por similitud
de nombre. La ingesta RES **no interpreta** que una persona sea socio,
accionista, administrador o beneficiario final cuando el dataset abierto no lo
dice. Esas relaciones requieren una capa documental separada con evidencia.

Prueba local sin red:

```bash
python -m src.res --self-test
```

## Cómo correrlo

```bash
pip install -r requirements.txt

# Producción: lee los contratos públicos por HTTPS
python -m src.fetch --out data/raw

# Desarrollo: lee clones locales, sin red
python -m src.fetch --out data/raw --local-root /ruta/a/los/repos

python -m src.build --raw data/raw --staged data/staged --out site/data

# RES: catálogo + archivos oficiales de Datos.gob.cl
python -m src.res --raw data/raw/res --out site/data
```

## Resultado medido sobre datos reales

| Etapa | Volumen |
|---|---|
| Contratos crudos ingeridos | 48,9 MB |
| JSONL normalizado | 10,2 MB |
| **Parquet canónico publicado** | **943 KB** |

Todo el conjunto analítico previo a RES cabe bajo 1 MB. RES se publica en
Parquet separado para que su mayor volumen no contamine ni duplique las tablas
de los radares.

Tablas producidas por los contratos de radares:

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
respaldo. En RES, por el contrario, la llave oficial publicada es el RUT y se
usa directamente para construir identidad exacta.

## Estado

Ejecutado y verificado extremo a extremo contra los contratos reales.
RES v1 incorpora la ingesta oficial de constituciones y atributos básicos desde
Datos.gob.cl. La extracción documental de modificaciones y relaciones
societarias queda desacoplada hasta contar con un mecanismo permitido y trazable.
