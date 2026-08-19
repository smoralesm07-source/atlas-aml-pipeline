# Puesta en marcha · qué necesito y qué necesitas hacer tú

Respuesta corta a «¿a qué necesitarías acceder además de GitHub, Entra y
Supabase?»: **a nada más**. Y de dos de esos tres no necesito credenciales,
sólo identificadores públicos.

---

## 1. Fuentes de datos · nada que otorgar

Los ocho radares publican sus contratos como archivos estáticos en GitHub Pages
o como release público. Se leen con HTTPS y **cero credenciales**.

Consecuencia de diseño: el sistema v1 **no puede afectar al v0**, porque nunca
obtiene permiso de escritura sobre él. No es una promesa operativa, es una
propiedad estructural.

No hace falta duplicar los radares. El sistema nuevo es una capa de análisis y
servicio distinta sobre los mismos productores.

---

## 2. GitHub · una acción tuya

**No puedo crear repositorios**: la integración de GitHub de esta sesión no
tiene ese permiso (devuelve `403 Resource not accessible by integration`).

Necesito que crees dos repositorios vacíos:

| Repositorio | Visibilidad | Por qué |
|---|---|---|
| `atlas-aml-pipeline` | **Público** | Actions gratuito e ilimitado; sostiene el cómputo pesado. No contendrá criterios ni datos |
| `atlas-aml-methodology` | **Privado** | Umbrales de detección. Trabajo liviano, cabe en los minutos gratuitos |

Después, habilita en el público: *Settings → Pages → Source: GitHub Actions*.

Por último, dame acceso en la sesión (yo ejecuto `add_repo`; sólo necesito que
existan).

---

## 3. Supabase · un proyecto nuevo, y una credencial que NO debes darme

Crea un **proyecto nuevo** (decisión ya tomada: aislamiento total de cuota,
claves, RLS y respaldos).

De ahí necesito **sólo dos valores, ambos seguros de compartir**:

- La **URL del proyecto**.
- La **clave publicable** (`anon` / publishable). Está diseñada para vivir en el
  navegador; es la que hoy ya está en el `app.js` público del sistema actual.

**No me entregues la `service_role` key.** Esa credencial la pegas tú
directamente en *Settings → Secrets and variables → Actions* del repositorio
privado, con el nombre `SUPABASE_SERVICE_ROLE_KEY`. Yo escribo el workflow que
la consume por nombre y nunca la veo. Lo mismo aplica a cualquier secreto de
importación.

---

## 4. Microsoft Entra · configuración tuya, sin credenciales para mí

Necesita un registro de aplicación (o un URI de redirección adicional) que
apunte a la nueva URL de Pages.

- El **client secret** va en la configuración del proveedor Azure **dentro de
  Supabase**, cargado por ti. No pasa por mí.
- De mi lado sólo necesito la **URL de redirección final**, para fijarla en el
  código del portal.

---

## 5. Lo que puedo hacer sin nada de lo anterior

Ya está hecho y verificado contra datos reales:

- Manifiesto de productores e ingesta sellada con SHA-256.
- Adaptadores de forma por productor.
- Construcción de hechos canónicos en Parquet (48,9 MB → 943 KB).
- Registro de tipologías con umbrales, absorción y conductor de grupo.
- Motor de scoring.
- Backtest temporal con ablación.
- Workflows, incluida la verificación que impide que un criterio se filtre a la
  capa pública.

Nada de eso requirió una sola credencial. Supabase y Entra recién hacen falta
en el momento de exponer **detalle por entidad autenticado** — es decir, al
final, no al principio.

---

## 6. Resumen de la lista

| # | Acción | Quién |
|---|---|---|
| 1 | Crear `atlas-aml-pipeline` (público) y `atlas-aml-methodology` (privado) | Tú |
| 2 | Habilitar Pages con origen GitHub Actions en el público | Tú |
| 3 | Empujar el código ya construido | Yo, apenas existan |
| 4 | Crear el proyecto Supabase nuevo | Tú |
| 5 | Pasarme URL y clave publicable | Tú |
| 6 | Cargar `SUPABASE_SERVICE_ROLE_KEY` como secreto del repo privado | Tú, sin mostrármela |
| 7 | Registrar la app en Entra con el nuevo URI de redirección | Tú |
| 8 | Migraciones SQL, RLS, portal y wiring completo | Yo |

Ningún paso toca el sistema actual.
