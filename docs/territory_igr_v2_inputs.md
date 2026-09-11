# Territorio · insumos públicos para IGR v2

Esta rama prepara dos pipelines de **hechos territoriales** para ATLAS. No contiene pesos, umbrales, scores ni reglas de riesgo; esos criterios pertenecen a la capa metodológica privada.

## 1. Exposición transfronteriza / logística

Contrato canónico: `ATLAS_TERRITORY_CROSSBORDER_FACT_V1`.

Hechos admitidos:
- pasos fronterizos;
- puertos;
- aeropuertos internacionales;
- oficinas/nodos aduaneros;
- habilitación de carga/internacional cuando esté publicada;
- coordenadas y comuna/región cuando estén explícitas;
- series de flujo sólo cuando una fuente oficial permita asociarlas al nodo con trazabilidad.

Guardarraíles:
- no usar número de empresas, SO, importadores o agentes como sustituto de exposición territorial;
- no derivar score en este repositorio;
- no inventar comuna a partir de la región;
- conservar fuente, fecha y precisión territorial.

Fuentes objetivo a conectar en las siguientes iteraciones:
- Unidad de Pasos Fronterizos / complejos fronterizos;
- Servicio Nacional de Aduanas / datos abiertos;
- fuentes oficiales de puertos y aeropuertos cuando entreguen localización/flujo trazable.

## 2. Evidencia territorial de lavado de activos

Contrato canónico: `ATLAS_TERRITORY_LA_EVIDENCE_FACT_V1`.

Hechos admitidos:
- sentencia/condena publicada;
- caso o evento oficial publicado;
- año;
- delito precedente cuando esté explícito;
- tipología cuando esté explícita;
- montos/decomisos cuando estén publicados;
- región/comuna del fenómeno sólo cuando la fuente la señale.

### Política de localización

`commune_explicit`: la fuente atribuye explícitamente el fenómeno a una comuna.

`region_explicit`: la fuente sólo permite atribución regional. La comuna se mantiene nula.

`national_only`: la fuente no permite una atribución territorial inferior al país.

**Prohibido:** inferir la localización del fenómeno a partir de la sede del tribunal, fiscalía, oficina UAF o lugar de publicación del documento.

Fuentes objetivo a conectar:
- publicaciones UAF de sentencias/tipologías;
- Ministerio Público/Fiscalía cuando exista evidencia territorial explícita;
- otros registros oficiales sólo si conservan trazabilidad documental.

## Integración futura

Estos pipelines producirán hechos normalizados. El portal podrá mostrar cobertura y estado de construcción antes de que una capa sea elegible para el IGR. La ausencia de un hecho no equivale a cero y no habilita renormalización silenciosa.

Pruebas locales:

```bash
python -m src.territory_crossborder --self-test
python -m src.territory_la_evidence --self-test
```
