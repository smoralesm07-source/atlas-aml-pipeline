/* ATLAS AML v1 · portal.
 *
 * El navegador no calcula riesgo. Lee lo que la base protegida le entrega y lo
 * presenta con su explicación. Los umbrales no existen en este archivo: llegan
 * desde `aml_typology_catalog`, que sólo leen los usuarios habilitados.
 */
'use strict';

const CFG = window.ATLAS_CONFIG;
const sb = window.supabase.createClient(CFG.supabase.url, CFG.supabase.anonKey, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
});

const app = document.querySelector('#app');
const state = { user: null, view: 'queue', entity: null, catalog: null };

/* ---------------------------------------------------------------- utilidades */
const esc = (v) =>
  String(v ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// Un valor ausente se muestra como «—», nunca como cero.
const num = (v, d = 1) => (Number.isFinite(Number(v)) ? Number(v).toFixed(d) : '—');
const pct = (v) => (Number.isFinite(Number(v)) ? `${Math.round(Number(v) * 100)}%` : '—');
const band = (s) => (s >= 70 ? 'alta' : s >= 45 ? 'media' : 'baja');

async function sha256(text) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/* La bitácora es solo-escritura: NO encadenar .select(), porque RETURNING
 * exige permiso de lectura y aquí está deliberadamente denegado. */
async function audit(eventType, extra = {}) {
  if (!state.user) return;
  try {
    await sb.from('aml_audit_log').insert({
      event_type: eventType,
      object_type: extra.objectType ?? null,
      object_id: extra.objectId ?? null,
      query_sha256: extra.queryHash ?? null,
      query_length: extra.queryLength ?? null,
      payload: extra.payload ?? {},
    });
  } catch (e) {
    console.warn('bitácora no disponible:', e.message);
  }
}

/* ------------------------------------------------------------------ pantallas */
function gate({ title, body, action = '', error = '' }) {
  app.innerHTML = `<section class="gate"><div class="gate-card">
    <div class="brand">ATLAS</div>
    <p class="eyebrow">Priorización analítica sobre información pública</p>
    <h1>${esc(title)}</h1><p>${esc(body)}</p>
    ${error ? `<p class="error">${esc(error)}</p>` : ''}${action}
  </div></section>`;
}

function renderLogin() {
  gate({
    title: 'Acceso controlado',
    body: 'Autenticación con Microsoft Entra. Autenticarse no otorga acceso: la autorización se valida por separado.',
    action: '<button class="primary" id="login">Ingresar con Microsoft</button>',
  });
  document.querySelector('#login').addEventListener('click', signIn);
}

function renderPending() {
  gate({
    title: 'Acceso pendiente de habilitación',
    body: 'Tu identidad fue autenticada, pero la seguridad a nivel de fila mantiene los datos cerrados hasta que la cuenta sea habilitada.',
    action: '<button class="ghost" id="logout">Cerrar sesión</button>',
  });
  document.querySelector('#logout').addEventListener('click', signOut);
}

function renderError(msg) {
  gate({
    title: 'No fue posible abrir el portal',
    body: 'Ocurrió un error al validar la sesión o consultar los datos.',
    error: msg,
    action: '<button class="ghost" id="logout">Cerrar sesión</button>',
  });
  document.querySelector('#logout').addEventListener('click', signOut);
}

/* ----------------------------------------------------------------- sesión */
async function signIn() {
  const { error } = await sb.auth.signInWithOAuth({
    provider: CFG.auth.provider,
    options: { scopes: CFG.auth.scopes, redirectTo: CFG.auth.redirectTo },
  });
  if (error) renderError(error.message);
}
async function signOut() {
  await sb.auth.signOut();
  location.href = CFG.auth.redirectTo;
}

/* ------------------------------------------------------------------- shell */
function shell(inner, subtitle = '') {
  app.innerHTML = `<div class="shell">
    <header class="top">
      <div class="idbox"><span class="brand-sm">ATLAS</span>
        <span class="sep">·</span><span class="sub">${esc(subtitle)}</span></div>
      <div class="who"><span class="mail">${esc(state.user?.email ?? '')}</span>
        <button class="ghost sm" id="logout">Salir</button></div>
    </header>
    <p class="notice">Los puntajes expresan <strong>prioridad analítica</strong>, no probabilidad de LA/FT.
      Un dato ausente se muestra como «—», nunca como cero.</p>
    <div id="body">${inner}</div>
  </div>`;
  document.querySelector('#logout').addEventListener('click', signOut);
}

/* ------------------------------------------------------- cola de prioridad */
async function loadQueue() {
  state.view = 'queue';
  shell('<p class="loading">Consultando el corte…</p>', 'Cola de revisión');

  const [queueRes, syncRes] = await Promise.all([
    sb.from('aml_priority_queue')
      .select('entity_id,rut,legal_name,region,score,score_confidence,coverage,scoring_marks,total_marks,drivers')
      .order('score', { ascending: false })
      .limit(100),
    sb.from('aml_sync_state').select('*').eq('pipeline', 'ATLAS_V1').maybeSingle(),
  ]);

  if (queueRes.error) return renderError(queueRes.error.message);
  const rows = queueRes.data ?? [];

  // Cero filas con sesión válida = cuenta no habilitada. No es un error.
  if (rows.length === 0 && !syncRes.data) return renderPending();

  await audit('QUEUE_VIEW', { payload: { rows: rows.length } });

  const sync = syncRes.data;
  const stamp = sync
    ? `Corte ${esc(sync.snapshot_id ?? '—')} · registro ${esc(sync.registry_version ?? '—')}`
    : 'Sin corte publicado todavía';
  const shadow = sync?.detail?.production_enabled === false
    ? '<span class="pill hold">modelo en sombra</span>' : '';

  shell(`
    <div class="bar">
      <div class="stamp">${stamp} ${shadow}</div>
      <input id="filter" class="filter" type="search" placeholder="Filtrar por nombre o RUT…"
             autocomplete="off" spellcheck="false">
    </div>
    ${rows.length === 0 ? '<p class="empty">El corte no contiene entidades con marcas.</p>' : `
    <div class="tbl-wrap"><table class="queue">
      <thead><tr>
        <th>Entidad</th><th>Región</th><th class="r">Prioridad</th>
        <th class="r">Confianza</th><th class="r">Cobertura</th><th>Marcas</th>
      </tr></thead>
      <tbody>${rows.map((r) => `
        <tr data-id="${esc(r.entity_id)}" tabindex="0"
            data-hay="${esc(((r.legal_name ?? '') + ' ' + (r.rut ?? '')).toLowerCase())}">
          <td><span class="nm">${esc(r.legal_name ?? '—')}</span>
              <span class="rut">${esc(r.rut ?? r.entity_id)}</span></td>
          <td>${esc(r.region ?? '—')}</td>
          <td class="r"><span class="score ${band(r.score)}">${num(r.score)}</span></td>
          <td class="r">${pct(r.score_confidence)}</td>
          <td class="r">${pct(r.coverage)}</td>
          <td class="drivers">${(r.drivers ?? []).map((d) => `<code>${esc(d)}</code>`).join(' ')}
              ${r.total_marks > r.scoring_marks
                ? `<span class="muted">+${r.total_marks - r.scoring_marks} sin aporte</span>` : ''}</td>
        </tr>`).join('')}
      </tbody>
    </table></div>`}
  `, 'Cola de revisión');

  document.querySelectorAll('tr[data-id]').forEach((tr) => {
    const open = () => loadEntity(tr.dataset.id);
    tr.addEventListener('click', open);
    tr.addEventListener('keydown', (e) => { if (e.key === 'Enter') open(); });
  });

  const filter = document.querySelector('#filter');
  filter?.addEventListener('input', async () => {
    const q = filter.value.trim().toLowerCase();
    document.querySelectorAll('tr[data-hay]').forEach((tr) => {
      tr.hidden = q !== '' && !tr.dataset.hay.includes(q);
    });
    if (q.length >= 3) {
      // El texto buscado no se persiste: sólo su hash y su longitud.
      await audit('SEARCH', { queryHash: await sha256(q), queryLength: q.length });
    }
  });
}

/* -------------------------------------------------------------- entidad 360 */
async function loadCatalog() {
  if (state.catalog) return state.catalog;
  const { data, error } = await sb.from('aml_typology_catalog').select('*');
  if (error) throw error;
  state.catalog = Object.fromEntries((data ?? []).map((t) => [t.mark_id, t]));
  return state.catalog;
}

async function loadEntity(entityId) {
  shell('<p class="loading">Abriendo entidad…</p>', 'Entidad');
  try {
    const [scoreRes, marksRes, catalog] = await Promise.all([
      sb.from('aml_entity_score').select('*').eq('entity_id', entityId).maybeSingle(),
      sb.from('aml_entity_mark').select('*').eq('entity_id', entityId)
        .order('contribution', { ascending: false }),
      loadCatalog(),
    ]);
    if (scoreRes.error) throw scoreRes.error;
    if (marksRes.error) throw marksRes.error;
    const e = scoreRes.data;
    if (!e) return renderError('La entidad no está en el corte vigente.');

    state.entity = e;
    await audit('ENTITY_VIEW', { objectType: 'entity', objectId: entityId });

    const marks = marksRes.data ?? [];
    const card = (m) => {
      const t = catalog[m.mark_id] ?? {};
      const off = !m.included_in_score;
      const why = m.absorbed_by
        ? `Absorbida por <code>${esc(m.absorbed_by)}</code>: reutiliza la misma evidencia.`
        : m.group_driver
        ? `El grupo lo conduce <code>${esc(m.group_driver)}</code>: marcas correlacionadas no se suman.`
        : '';
      return `<article class="mark ${off ? 'off' : ''}">
        <header>
          <code>${esc(m.mark_id)}</code>
          <h4>${esc(t.name ?? m.mark_id)}</h4>
          <span class="contrib">${off ? 'aporte 0' : `+${num(m.contribution)}`}</span>
        </header>
        ${t.rationale ? `<p class="why">${esc(t.rationale)}</p>` : ''}
        ${why ? `<p class="absorb">${why}</p>` : ''}
        <details><summary>Cómo se calculó</summary>
          <p class="thr">${esc(t.threshold_explanation ?? 'Sin explicación registrada.')}</p>
          <p class="meta">Intensidad observada ${num(m.raw_intensity)} · confianza ${pct(m.confidence)}
             · estado <code>${esc(m.readiness)}</code></p>
          ${(t.guardrails ?? []).length
            ? `<ul class="rails">${t.guardrails.map((g) => `<li>${esc(g)}</li>`).join('')}</ul>` : ''}
        </details>
      </article>`;
    };

    shell(`
      <button class="ghost sm back" id="back">← Volver a la cola</button>
      <section class="ent">
        <div class="ent-head">
          <div><h2>${esc(e.legal_name ?? '—')}</h2>
            <p class="rut">${esc(e.rut ?? e.entity_id)}${e.region ? ` · ${esc(e.region)}` : ''}</p></div>
          <div class="big"><span class="score ${band(e.score)}">${num(e.score)}</span>
            <span class="cap">prioridad analítica</span></div>
        </div>
        <dl class="quality">
          <div><dt>Confianza de la evidencia</dt><dd>${pct(e.score_confidence)}</dd></div>
          <div><dt>Cobertura de fuentes</dt><dd>${pct(e.coverage)}</dd></div>
          <div><dt>Marcas que aportan</dt><dd>${marks.filter((m) => m.included_in_score).length} de ${marks.length}</dd></div>
        </dl>
        <p class="fine">Confianza y cobertura describen la calidad de la evidencia. No son riesgo y nunca elevan el puntaje.</p>
        <h3>Marcas</h3>
        ${marks.map(card).join('')}
        <h3>Resultado de la revisión</h3>
        <p class="fine">Tu juicio es el insumo de calibración del sistema. Queda registrado a tu nombre.</p>
        <div class="triage" id="triage">
          ${[['REVISADO_UTIL', 'Útil'],
             ['DESCARTADO_NO_RELEVANTE', 'No relevante'],
             ['FALSO_POSITIVO', 'Falso positivo'],
             ['REQUIERE_MAS_INFORMACION', 'Falta información'],
             ['ESCALADO', 'Escalar']]
            .map(([v, l]) => `<button class="tri" data-out="${v}">${l}</button>`).join('')}
        </div>
        <p class="tri-msg" id="triMsg" role="status"></p>
      </section>`, 'Entidad');

    document.querySelector('#back').addEventListener('click', loadQueue);
    document.querySelectorAll('.tri').forEach((b) =>
      b.addEventListener('click', () => sendFeedback(entityId, b.dataset.out, b)));
  } catch (err) {
    renderError(err.message);
  }
}

async function sendFeedback(entityId, outcome, button) {
  const msg = document.querySelector('#triMsg');
  document.querySelectorAll('.tri').forEach((b) => (b.disabled = true));
  const { error } = await sb.from('aml_triage_feedback').insert({
    entity_id: entityId,
    outcome,
    snapshot_id: state.entity?.snapshot_id ?? null,
  });
  if (error) {
    msg.textContent = `No se pudo registrar: ${error.message}`;
    msg.className = 'tri-msg bad';
    document.querySelectorAll('.tri').forEach((b) => (b.disabled = false));
    return;
  }
  button.classList.add('done');
  msg.textContent = 'Revisión registrada. Gracias: esto es lo que permite calibrar el sistema.';
  msg.className = 'tri-msg ok';
  await audit('TRIAGE', { objectType: 'entity', objectId: entityId, payload: { outcome } });
}

/* ------------------------------------------------------------------ arranque */
async function boot() {
  const { data: { session } } = await sb.auth.getSession();
  if (!session) return renderLogin();
  state.user = session.user;
  await audit('SESSION_START');
  await loadQueue();
}

sb.auth.onAuthStateChange((event) => {
  // Diferido: onAuthStateChange no admite trabajo asíncrono en su callback.
  if (event === 'SIGNED_IN' || event === 'SIGNED_OUT') setTimeout(boot, 0);
});

boot().catch((e) => renderError(e.message));
