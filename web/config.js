/* ATLAS AML v1 · configuración pública del portal.
 *
 * Todo lo que hay aquí es público por diseño y puede leerse desde el navegador:
 *   · La URL del proyecto Supabase.
 *   · La clave `anon`, que está hecha para vivir en el cliente. No otorga
 *     acceso a nada: la autorización la resuelve la lista de habilitados y la
 *     seguridad a nivel de fila, del lado del servidor.
 *
 * Lo que NUNCA debe aparecer en este archivo ni en ningún otro de este
 * repositorio: la clave `service_role`, secretos de Entra, y cualquier umbral
 * de detección.
 */
'use strict';

window.ATLAS_CONFIG = Object.freeze({
  release: '1.0.0',
  build: '0100',

  supabase: {
    url: 'https://bzqxvidggykkdouotylg.supabase.co',
    // Clave anon (rol `anon` verificado en el JWT). Diseñada para el cliente.
    anonKey:
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6' +
      'ImJ6cXh2aWRnZ3lra2RvdW90eWxnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY5MDY5NT' +
      'MsImV4cCI6MjEwMjQ4Mjk1M30.PXQIof_L3G410XKPkgm_lqk2KFHRqzvu2LZxHw6PbXM',
  },

  auth: {
    provider: 'azure',
    scopes: 'email',
    redirectTo: 'https://smoralesm07-source.github.io/atlas-aml-pipeline/',
  },

  // Hechos públicos servidos por CDN desde este mismo sitio.
  facts: {
    base: './data/',
    tables: [
      'entity_osfl',
      'sanction_event',
      'tax_profile',
      'sector_reportability',
    ],
    manifest: './data/_build.json',
  },

  // Semántica que la interfaz debe mostrar siempre junto a cualquier score.
  semantics: {
    score: 'Prioridad analítica, no probabilidad de LA/FT.',
    missing: 'Un dato ausente se muestra como «—», nunca como cero.',
    confidence: 'Confianza y cobertura describen la evidencia, no el riesgo.',
  },
});
