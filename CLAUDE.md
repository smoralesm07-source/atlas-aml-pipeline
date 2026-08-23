# Identidad del proyecto Atlas

Nota de referencia para no confundir este sistema con otros proyectos de la
cuenta que usan nombres o siglas parecidas ("AML").

## Qué es Atlas

**Atlas AML v1** es el nombre público de **este** sistema: la capa de
ingesta, cómputo y portal público construida en `atlas-aml-pipeline` +
`atlas-aml-methodology`. Es un sistema **paralelo y aislado** — no corre
sobre la base de `AML-Workbench-Portal` ni comparte repositorio, URL, base
de datos o credenciales con él.

## Los tres sistemas de la cuenta — no confundir

| Sistema | Repos | Base Supabase | Notas |
|---|---|---|---|
| **Atlas AML v1** (este sistema) | `atlas-aml-pipeline` (público) + `atlas-aml-methodology` (privado) | `bzqxvidggykkdouotylg` — nombre en el dashboard: **"AML CLAUDE"** | Confirmado en `web/config.js` de este repo (`SUPABASE_URL`). Diseñado desde cero para no tocar el sistema v0 |
| **AML Workbench Portal** (sistema v0, previo y distinto) | `AML-Workbench-Portal` + `Intelligence_Fusion_Layer` + los 8 radares productores (Radar_SII, Radar_UAF, Radar_CGR, Radar_sanciones, Radar_delictual, Radar_OSFL, Radar_prensa, Context-Hub, Rada_Presupuesto_Abierto) | `ldmtlwzqaqmegedktlxr` — nombre en el dashboard: "smoralesm07-source's Project" | Confirmado hardcodeado en `AML-Workbench-Portal/app.js` (`SUPABASE_URL`). Los archivos con prefijo `atlas-*` dentro de ese repo son sólo una convención interna de nombres/versiones de ese portal; **no tienen relación con el sistema Atlas de esta nota** |
| **"AML Claude"** | no identificado en esta sesión | no identificado en esta sesión | Según confirmación del usuario (2026-08-23), es un asunto/proyecto **distinto** de los dos anteriores. Pendiente de documentar cuando se identifique su repo y base |

## Repositorios de Atlas

| Repositorio | Visibilidad | Rol |
|---|---|---|
| `atlas-aml-pipeline` (este repo) | Público | Adaptadores, construcción de tablas canónicas Parquet, shell del portal |
| `atlas-aml-methodology` | Privado | Umbrales de detección, motor de scoring, backtest |

## Base de datos de Atlas (Supabase)

- **Project ref:** `bzqxvidggykkdouotylg`
- **Nombre en el dashboard de Supabase:** "AML CLAUDE"
- **URL:** `https://bzqxvidggykkdouotylg.supabase.co`
- Verificable en `web/config.js` de este repo (URL y clave `anon` públicas por diseño).
- Tablas relevantes: `entities`, `evaluations`, `dispositions`, `audit_trail`,
  `aml_allowed_users`, `aml_sync_state`, `aml_typology_catalog`,
  `aml_entity_score`, `aml_entity_mark`, `aml_audit_log`, `aml_triage_feedback`.

## Confirmado por

Sebastián Morales (smoralesm07@gmail.com), 2026-08-23.
