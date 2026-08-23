# Identidad del proyecto Atlas

Nota de referencia para no confundir este sistema con otros proyectos de la
cuenta que usan nombres o siglas parecidas ("AML").

## Qué es Atlas

**Atlas AML v1** es el nombre público de este sistema. Es la capa de ingesta,
cómputo y portal público que corre sobre la base **AML Workbench Portal**.

## Repositorios

| Repositorio | Visibilidad | Rol |
|---|---|---|
| `atlas-aml-pipeline` (este repo) | Público | Adaptadores, construcción de tablas canónicas Parquet, shell del portal |
| `atlas-aml-methodology` | Privado | Umbrales de detección, motor de scoring, backtest |

## Base de datos (Supabase)

Atlas está respaldado por el proyecto Supabase:

- **Project ref:** `bzqxvidggykkdouotylg`
- **Nombre en el dashboard de Supabase:** "AML CLAUDE"
- **URL:** `https://bzqxvidggykkdouotylg.supabase.co`
- Verificable en `web/config.js` de este repo (URL y clave `anon` públicas por diseño).
- Tablas relevantes: `entities`, `evaluations`, `dispositions`, `audit_trail`,
  `aml_allowed_users`, `aml_sync_state`, `aml_typology_catalog`,
  `aml_entity_score`, `aml_entity_mark`, `aml_audit_log`, `aml_triage_feedback`.

### No confundir con

El proyecto Supabase `ldmtlwzqaqmegedktlxr` ("smoralesm07-source's Project")
**no es la base de Atlas**. Es un proyecto distinto — con tablas genéricas
(`Users`, `Pets`, `Task`) y snapshots gobernados (`aml_v0xx_geo_*`,
`aml_osfl_*`, `aml_sii_*`) que referencian sincronización con AML Workbench
en su versión anterior (v0). No compartir credenciales ni migraciones entre
ambos proyectos.

## Confirmado por

Sebastián Morales (smoralesm07@gmail.com), 2026-08-23.
