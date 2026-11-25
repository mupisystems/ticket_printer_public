/*
 * Agente de Impressão — interface.
 *
 * JavaScript puro (sem build). Conversa com o Python pela ponte do pywebview:
 *   - chamadas:  call('nome_do_metodo', ...args)  → classe Api em app_window.py
 *   - eventos:   window.agent.receive({type, data}) ← AppWindow.emit()
 *
 * Telas:
 *   - Assistente (primeiro uso): Boas-vindas → Conexão → Impressora → Comprovante → Concluir
 *   - Painel: Visão geral · Configurações · Registros
 */
'use strict';

(function () {
  // ─── Utilidades ────────────────────────────────────────────────────────────
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // Ícones no estilo Lucide (traço 2px, viewBox 24).
  const ICONS = {
    'check': '<path d="M20 6 9 17l-5-5"/>',
    'x': '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    'arrow-right': '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    'arrow-left': '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    'chevron-right': '<path d="m9 18 6-6-6-6"/>',
    'chevron-down': '<path d="m6 9 6 6 6-6"/>',
    'printer': '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6"/><rect x="6" y="14" width="12" height="8" rx="1"/>',
    'refresh-cw': '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    'key-round': '<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>',
    'server': '<rect width="20" height="8" x="2" y="2" rx="2"/><rect width="20" height="8" x="2" y="14" rx="2"/><path d="M6 6h.01"/><path d="M6 18h.01"/>',
    'wifi-off': '<path d="M12 20h.01"/><path d="M8.5 16.429a5 5 0 0 1 7 0"/><path d="M5 12.859a10 10 0 0 1 5.17-2.69"/><path d="M19 12.859a10 10 0 0 0-2.007-1.523"/><path d="M2 8.82a15 15 0 0 1 4.177-2.643"/><path d="M22 8.82a15 15 0 0 0-11.288-3.764"/><path d="m2 2 20 20"/>',
    'receipt-text': '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M14 8H8"/><path d="M16 12H8"/><path d="M13 16H8"/>',
    'triangle-alert': '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    'info': '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    'eye': '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
    'eye-off': '<path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"/><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"/><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"/><path d="m2 2 20 20"/>',
    'clipboard-paste': '<path d="M15 2H9a1 1 0 0 0-1 1v2c0 .6.4 1 1 1h6c.6 0 1-.4 1-1V3c0-.6-.4-1-1-1Z"/><path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2M16 4h2a2 2 0 0 1 2 2v2M11 14h10"/><path d="m17 10 4 4-4 4"/>',
    'copy': '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    'trash-2': '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/>',
    'folder-open': '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    'settings': '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    'layout-dashboard': '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
    'file-text': '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    'activity': '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    'list-checks': '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
    'shield-check': '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    'clock': '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    'plug': '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    'globe': '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    'circle-check': '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    'circle-x': '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    'help-circle': '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    'zoom-in': '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/><path d="M11 8v6"/><path d="M8 11h6"/>',
    'image': '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
    'upload': '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
  };
  const icon = (name, cls = '') =>
    `<svg class="ic ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`;
  const spinner = (cls = '') => `<span class="spinner ${cls}" aria-hidden="true"></span>`;

  const TONE_ICON = { success: 'check', error: 'x', warning: 'triangle-alert', info: 'info', neutral: 'info' };

  // ─── Ponte com o Python ────────────────────────────────────────────────────
  let resolveApi;
  const apiReady = new Promise((resolve) => { resolveApi = resolve; });
  const detectApi = () => { if (window.pywebview && window.pywebview.api) resolveApi(window.pywebview.api); };
  window.addEventListener('pywebviewready', detectApi);
  detectApi();

  async function call(method, ...args) {
    const api = await apiReady;
    return api[method](...args);
  }

  // ─── Estado ────────────────────────────────────────────────────────────────
  const S = {
    version: '', status: 'disconnected', config: {}, envs: [], models: [],
    configured: false, frozen: false, stats: {}, activity: [],
    view: 'boot', step: 0, maxStep: 0, fromApp: false, page: 'overview',
    draft: {}, form: null,
    conn: 'idle', awaiting: false, connTimer: 0,
    showToken: false, showServer: false,
    support: false,   // modo suporte (Ctrl+Shift+S): mostra a escolha de servidor
    printers: null, pstatus: {},
    previews: {},     // modelo → { src } | { loading } | { failed }
    previewGen: 0,    // muda quando o logo muda (descarta prévias antigas em andamento)
    logo: { enabled: false, size: 'medium' },
    logoBusy: false,
    sample: { source: null, has_qr: false },   // formato real do ticket da conta
    previewQr: null,  // null = automático (conforme a conta); true/false = escolhido na prévia
    test: { state: 'idle' },
    logs: [], logsSeen: 0, logFilter: 'all', logTimer: 0,
  };

  const STEPS = [
    { title: 'Conexão', sub: 'Chave do totem' },
    { title: 'Impressora', sub: 'Escolha e teste' },
    { title: 'Comprovante', sub: 'Modelo do ticket' },
    { title: 'Concluir', sub: 'Revisão final' },
  ];
  const PRIMARY_ENVS = [
    { key: 'producao_br', title: 'Meu Atendimento Virtual', sub: 'Brasil' },
    { key: 'producao_us', title: 'Awaitra', sub: 'Estados Unidos' },
  ];
  const MODEL_DESC = {
    default: 'Texto simples e centralizado, com rótulos.',
    thermal_classic: 'Senha no topo e informações em blocos.',
    compact: 'Tudo em poucas linhas, sem espaços sobrando.',
    big_number: 'Senha enorme, fácil de ler de longe.',
    inverted: 'Faixas escuras no topo e no rodapé.',
    framed: 'Informações dentro de uma moldura.',
  };
  const MODEL_TAG = { compact: 'Economiza papel', big_number: 'Mais legível' };

  const envInfo = (key) => S.envs.find((e) => e.key === key) || { key, label: key, url: '' };
  const modelLabel = (key) => (S.models.find((m) => m.key === key) || {}).label || key;

  function shortEnv(key = S.config.environment) {
    const p = PRIMARY_ENVS.find((e) => e.key === key);
    if (p) return { title: p.title, sub: `Produção · ${p.sub}` };
    const info = envInfo(key);
    return { title: info.label, sub: key === 'custom' ? (S.config.server_url || 'Endereço personalizado') : 'Ambiente de testes' };
  }

  function connPill(status = S.status) {
    switch (status) {
      case 'connected': return ['success', 'Conectado'];
      case 'connecting': return ['info', 'Conectando…'];
      case 'reconnecting': return ['warning', 'Reconectando…'];
      case 'auth_failed': return ['error', 'Chave recusada'];
      case 'server_error': return ['error', 'Erro no servidor'];
      default: return ['error', 'Desconectado'];
    }
  }

  function printerPill(name) {
    if (!name) return ['warning', 'Não selecionada'];
    const st = S.pstatus[name];
    if (!st) return ['neutral', 'Verificando…'];
    return st.ready ? ['success', 'Pronta'] : ['error', st.label];
  }

  const pill = ([tone, text], attrs = '') =>
    `<span class="pill pill--${tone}" ${attrs}><i></i>${esc(text)}</span>`;

  function feedback(tone, title, msg = '', busy = false) {
    return `<div class="feedback feedback--${tone} enter" role="status">
      <span class="fb-icon">${busy ? spinner('spinner--light') : icon(TONE_ICON[tone])}</span>
      <div class="fb-text"><b>${esc(title)}</b>${msg ? `<p>${msg}</p>` : ''}</div>
    </div>`;
  }

  const fmtTime = (ts) => new Date(ts * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  function relTime(ts) {
    const d = Date.now() / 1000 - ts;
    if (d < 45) return 'agora';
    if (d < 3600) return `há ${Math.max(1, Math.round(d / 60))} min`;
    if (d < 86400) return fmtTime(ts);
    return new Date(ts * 1000).toLocaleDateString('pt-BR');
  }

  // ─── Avisos (toasts) e confirmação ─────────────────────────────────────────
  function toast(tone, title, msg = '') {
    const el = document.createElement('div');
    el.className = `toast toast--${tone}`;
    el.innerHTML = `<span class="toast-icon">${icon(TONE_ICON[tone])}</span>
      <div><b>${esc(title)}</b>${msg ? `<p>${esc(msg)}</p>` : ''}</div>`;
    $('#toasts').appendChild(el);
    setTimeout(() => { el.classList.add('leave'); setTimeout(() => el.remove(), 260); }, 4200);
  }

  function confirmDialog({ title, message, ok = 'Confirmar', danger = false }) {
    return new Promise((resolve) => {
      const wrap = document.createElement('div');
      wrap.className = 'modal-backdrop';
      wrap.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}">
        <div class="modal-icon ${danger ? 'modal-icon--danger' : ''}">${icon(danger ? 'triangle-alert' : 'help-circle')}</div>
        <h3>${esc(title)}</h3><p>${esc(message)}</p>
        <div class="modal-actions">
          <button class="btn btn--ghost" data-r="0">Cancelar</button>
          <button class="btn ${danger ? 'btn--danger' : 'btn--primary'}" data-r="1">${esc(ok)}</button>
        </div></div>`;
      document.body.appendChild(wrap);
      const done = (v) => {
        document.removeEventListener('keydown', onKey);
        wrap.classList.add('leave');
        setTimeout(() => wrap.remove(), 180);
        resolve(v);
      };
      const onKey = (e) => { if (e.key === 'Escape') done(false); };
      document.addEventListener('keydown', onKey);
      wrap.addEventListener('click', (e) => {
        const b = e.target.closest('[data-r]');
        if (b) done(b.dataset.r === '1');
        else if (e.target === wrap) done(false);
      });
      wrap.querySelector('[data-r="1"]').focus();
    });
  }

  // ─── Inicialização ─────────────────────────────────────────────────────────
  function applySnapshot(st, withStatus) {
    S.version = st.version;
    S.config = st.config;
    S.envs = st.environments;
    S.models = st.receipt_models;
    S.configured = st.configured;
    S.onboardingRequired = !!st.onboarding_required;
    S.frozen = st.frozen;
    S.stats = st.stats || {};
    S.activity = st.activity || [];
    S.logo = st.logo || { enabled: false, size: 'medium' };
    S.sample = st.ticket_sample || { source: null, has_qr: false };
    if (withStatus) S.status = st.status;
  }

  async function boot() {
    try {
      applySnapshot(await call('get_state'), true);
    } catch (e) {
      console.error('get_state falhou', e);
    }
    if (S.onboardingRequired) {
      // Instalação/atualização nova: boas-vindas do início, com a configuração mantida.
      startWizard(false, true);
    } else if (S.configured) {
      S.view = 'app';
      S.page = 'overview';
    } else {
      startWizard(false);
    }
    render();
    if (S.view === 'app' && S.config.printer_name) checkPrinter(S.config.printer_name);
    if (S.view === 'wizard' && S.step === 2) loadPrinters();

    setInterval(() => {
      if (!document.hidden && S.view === 'app' && S.config.printer_name) checkPrinter(S.config.printer_name);
    }, 15000);
    setInterval(() => $$('time[data-ts]').forEach((t) => { t.textContent = relTime(+t.dataset.ts); }), 30000);
  }

  function render() {
    const root = $('#app');
    root.dataset.view = S.view;
    if (S.view === 'wizard') root.innerHTML = renderWizard();
    else if (S.view === 'app') root.innerHTML = renderShell();
  }

  // ═══ ASSISTENTE ════════════════════════════════════════════════════════════

  function startWizard(fromApp, fromStart = false) {
    const c = S.config;
    S.draft = {
      token: c.token || '',
      environment: c.environment || 'producao_br',
      server_url: c.server_url || '',
      printer_name: c.printer_name || '',
      receipt_model: c.receipt_model || 'default',
      paper_width: c.paper_width || '80',
    };
    S.conn = c.token && S.status === 'connected' ? 'ok' : 'idle';
    S.test = { state: 'idle' };
    S.fromApp = fromApp;
    S.showToken = false;
    S.showServer = !PRIMARY_ENVS.some((e) => e.key === S.draft.environment);
    if (fromStart) { S.step = 0; S.maxStep = S.configured ? 4 : 0; }
    else if (fromApp) { S.step = 1; S.maxStep = 4; }
    else if (!c.token) { S.step = 0; S.maxStep = 0; }
    else if (!c.printer_name) { S.step = 2; S.maxStep = 2; }
    else { S.step = 1; S.maxStep = 4; }
    S.view = 'wizard';
  }

  function goStep(n) {
    S.step = n;
    S.maxStep = Math.max(S.maxStep, n);
    S.doneAnimated = false;
    if (S.test.state !== 'busy') S.test = { state: 'idle' };
    render();
    if (n === 1) setTimeout(() => { const t = $('#token-draft'); if (t && !t.value) t.focus(); }, 60);
    if (n === 2) { if (!S.printers) loadPrinters(); else refreshStatuses(); }
    if (n === 2 || n === 3) prefetchPreviews();
  }

  function renderWizard() {
    const st = S.step;
    const items = STEPS.map((s, i) => {
      const n = i + 1;
      const state = st === 0 ? 'todo' : n < st ? 'done' : n === st ? 'current' : 'todo';
      const clickable = st !== 0 && n !== st && n <= S.maxStep;
      return `<li class="vstep ${state} ${clickable ? 'clickable' : ''}" ${clickable ? `data-action="goto" data-step="${n}"` : ''}>
        <span class="vstep-dot">${state === 'done' ? icon('check') : n}</span>
        <span class="vstep-text"><b>${s.title}</b><small>${s.sub}</small></span>
      </li>`;
    }).join('');

    return `<div class="wiz">
      <aside class="wiz-side">
        <div class="wiz-brand"><img src="assets/logo-white.png" alt="SIGA"></div>
        <div class="wiz-side-head">
          <span class="eyebrow eyebrow--light">${S.fromApp ? 'Configuração guiada' : 'Primeiros passos'}</span>
          <h2>Vamos preparar a impressão deste totem</h2>
        </div>
        <ol class="vsteps">${items}</ol>
        <div class="wiz-side-foot">
          ${icon('shield-check')}
          <span>A chave fica guardada com criptografia neste computador.</span>
        </div>
        <div class="wiz-version">Agente de Impressão · versão ${esc(S.version)}</div>
      </aside>
      <main class="wiz-main">
        <div class="wiz-scroll" id="wiz-scroll">
          <div class="wiz-content enter ${S.step === 3 ? 'wiz-content--wide' : ''}" id="wiz-step">${renderStep()}</div>
        </div>
        <footer class="wiz-footer" id="wiz-footer">${wizardFooter()}</footer>
      </main>
    </div>`;
  }

  function renderStep() {
    switch (S.step) {
      case 0: return stepWelcome();
      case 1: return stepConnection();
      case 2: return stepPrinter();
      case 3: return stepReceipt();
      default: return stepDone();
    }
  }

  function rerenderStep() {
    const el = $('#wiz-step');
    if (el) el.innerHTML = renderStep();
    refreshFooter();
  }

  const stepHead = (n, title, text) => `<header class="step-head">
      <span class="eyebrow">Passo ${n} de 3</span>
      <h1>${title}</h1>
      <p class="lead">${text}</p>
    </header>`;

  function wizardFooter() {
    const st = S.step;
    const back = (to) => `<button class="btn btn--ghost" data-action="goto" data-step="${to}">${icon('arrow-left')}Voltar</button>`;
    const next = (enabled = true) => `<button class="btn btn--primary btn--lg" data-action="next" ${enabled ? '' : 'disabled'}>Continuar${icon('arrow-right')}</button>`;
    const skip = (to) => `<button class="btn btn--ghost" data-action="goto" data-step="${to}">Pular por enquanto</button>`;
    let left = '';
    let right = '';

    if (st === 0) {
      left = `<span class="footer-note">${icon('clock')}Leva menos de 2 minutos</span>`;
      right = `<button class="btn btn--primary btn--lg" data-action="goto" data-step="1">Começar configuração${icon('arrow-right')}</button>`;
    } else if (st === 1) {
      left = S.fromApp ? '<button class="btn btn--ghost" data-action="cancel-wizard">Cancelar</button>' : back(0);
      if (S.conn === 'ok') right = next();
      else if (S.conn === 'testing') right = `<button class="btn btn--primary btn--lg" disabled>${spinner('spinner--light')}Conectando…</button>`;
      else {
        const retry = S.conn === 'failed' || S.conn === 'unreachable' || S.conn === 'server_error';
        right = (retry ? skip(2) : '') +
          `<button class="btn btn--primary btn--lg" data-action="connect">${icon(retry ? 'refresh-cw' : 'plug')}${retry ? 'Tentar novamente' : 'Conectar'}</button>`;
      }
    } else if (st === 2) {
      left = back(1);
      // Sem nenhuma impressora física, permite seguir e escolher depois.
      const noPhysical = Array.isArray(S.printers) && !S.printers.some((p) => !p.virtual) && !S.draft.printer_name;
      right = (noPhysical ? skip(3) : '') + next(!!S.draft.printer_name);
    } else if (st === 3) {
      left = back(2);
      right = next();
    } else {
      left = back(3);
      right = `<button class="btn btn--success btn--lg" data-action="finish">${icon('check')}Concluir configuração</button>`;
    }
    return `<div class="footer-side">${left}</div><div class="footer-side footer-side--end">${right}</div>`;
  }

  function refreshFooter() {
    const f = $('#wiz-footer');
    if (f) f.innerHTML = wizardFooter();
  }

  // ── Passo 0: boas-vindas ──
  function stepWelcome() {
    const update = S.onboardingRequired && S.configured;
    return `<div class="welcome">
      <div class="welcome-art">${artPrinter()}</div>
      <span class="eyebrow">${update ? 'Nova versão instalada' : 'Boas-vindas'}</span>
      <h1>Bem-vindo ao Agente de Impressão</h1>
      <p class="lead">${update
        ? 'Sua configuração foi mantida e o totem continua imprimindo normalmente. Confira os três passos para revisar a conexão, a impressora e o comprovante.'
        : 'Ele recebe as senhas retiradas no totem e imprime na hora, automaticamente. Vamos deixar tudo pronto em três passos rápidos.'}</p>
      <ol class="welcome-list">
        <li><span class="wl-icon">${icon('key-round')}</span><div><b>Conectar ao servidor</b><small>Com a chave de impressão do painel</small></div><span class="wl-num">1</span></li>
        <li><span class="wl-icon">${icon('printer')}</span><div><b>Escolher a impressora</b><small>E imprimir um ticket de teste</small></div><span class="wl-num">2</span></li>
        <li><span class="wl-icon">${icon('receipt-text')}</span><div><b>Escolher o comprovante</b><small>O visual do ticket entregue ao cliente</small></div><span class="wl-num">3</span></li>
      </ol>
    </div>`;
  }

  function artPrinter() {
    return `<svg class="art" viewBox="0 0 300 210" role="img" aria-label="Impressora imprimindo uma senha">
      <defs>
        <linearGradient id="art-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#4253b3"/><stop offset="1" stop-color="#28368a"/>
        </linearGradient>
        <clipPath id="art-clip"><rect x="0" y="0" width="300" height="112"/></clipPath>
      </defs>
      <circle cx="150" cy="104" r="96" fill="#f0f2fb"/>
      <circle cx="150" cy="104" r="70" fill="#e4e8f8"/>
      <ellipse cx="150" cy="190" rx="86" ry="9" fill="#e1e5f1"/>
      <path class="art-spark" d="M244 50l3.2 8.3 8.3 3.2-8.3 3.2-3.2 8.3-3.2-8.3-8.3-3.2 8.3-3.2z" fill="#c7cff0"/>
      <path class="art-spark art-spark--2" d="M60 78l2.2 5.6 5.6 2.2-5.6 2.2-2.2 5.6-2.2-5.6-5.6-2.2 5.6-2.2z" fill="#c7cff0"/>
      <circle cx="232" cy="150" r="4" fill="#d6dcf3"/>
      <rect x="64" y="104" width="172" height="76" rx="20" fill="url(#art-body)"/>
      <rect x="96" y="100" width="108" height="16" rx="8" fill="#1d2766"/>
      <g clip-path="url(#art-clip)">
        <g class="art-ticket">
          <path d="M112 112V34l6-5 6 5 6-5 6 5 6-5 6 5 6-5 6 5 6-5 6 5 6-5 6 5v78z" fill="#fff" stroke="#e3e7f0"/>
          <text x="150" y="66" text-anchor="middle" font-family="Consolas, monospace" font-weight="700" font-size="21" fill="#334398">A001</text>
          <rect x="128" y="78" width="44" height="5" rx="2.5" fill="#e3e7f0"/>
          <rect x="135" y="89" width="30" height="5" rx="2.5" fill="#e3e7f0"/>
        </g>
      </g>
      <rect x="96" y="108" width="108" height="8" rx="4" fill="#1d2766"/>
      <rect x="88" y="138" width="78" height="16" rx="8" fill="#4a5bbb"/>
      <circle class="art-led" cx="206" cy="146" r="7" fill="#4ade80"/>
    </svg>`;
  }

  // ── Passo 1: conexão ──
  function stepConnection() {
    return `${stepHead(1, 'Conecte ao servidor', 'Cole a chave de impressão. Ela liga este computador à sua conta e garante que as senhas certas saiam nesta impressora.')}
      ${tokenField('draft')}
      <div id="server-draft">${serverBlock('draft')}</div>
      <div id="conn-feedback" class="fb-slot">${connFeedback()}</div>`;
  }

  // O cliente só informa o token: o servidor é o de produção. A escolha de
  // servidor aparece apenas no modo suporte (Ctrl+Shift+S). Se a configuração
  // já aponta para outro servidor, só informa qual é.
  function serverBlock(scope) {
    if (S.support) return serverPicker(scope);
    const env = S[scope].environment;
    if (env === 'producao_br') return '';
    const info = shortEnv(env);
    return `<p class="server-note">${icon('server')}<span>Servidor: <b>${esc(info.title)}</b> · ${esc(info.sub)}</span></p>`;
  }

  function tokenField(scope) {
    const d = S[scope];
    return `<div class="field">
      <label class="label" for="token-${scope}">Chave do Totem/Agente de Impressão</label>
      <div class="input-group">
        <span class="input-icon">${icon('key-round')}</span>
        <input id="token-${scope}" class="input input--mono" data-scope="${scope}" data-field="token"
          type="${S.showToken ? 'text' : 'password'}" value="${esc(d.token)}"
          placeholder="Cole aqui a chave de impressão" autocomplete="off" spellcheck="false">
        <button type="button" class="input-btn" data-action="toggle-token" title="${S.showToken ? 'Ocultar' : 'Mostrar'} chave">${icon(S.showToken ? 'eye-off' : 'eye')}</button>
        <button type="button" class="input-btn input-btn--label" data-action="paste-token" data-scope="${scope}">${icon('clipboard-paste')}Colar</button>
      </div>
      <p class="hint">${icon('info')}<span>No painel, abra <b>Configurações</b> e, no menu lateral, <b>Painéis &amp; Totens &gt; Impressão de Senhas</b>. Copie a chave em <b>Chaves de Impressão</b>.${d.environment === 'producao_br' ? ' <button type="button" class="inline-link" data-action="open-panel">Abrir essa tela</button>' : ''}</span></p>
    </div>`;
  }

  function serverPicker(scope) {
    const d = S[scope];
    const cards = PRIMARY_ENVS.map((e) => {
      const on = d.environment === e.key;
      return `<button type="button" class="choice ${on ? 'is-selected' : ''}" data-action="select-env" data-scope="${scope}" data-key="${e.key}" role="radio" aria-checked="${on}">
        <span class="choice-icon">${icon('globe')}</span>
        <span class="choice-text"><b>${e.title}</b><small>${e.sub}</small></span>
        <span class="radio"></span>
      </button>`;
    }).join('');
    const options = S.envs.map((e) =>
      `<option value="${e.key}" ${d.environment === e.key ? 'selected' : ''}>${esc(e.label)}</option>`).join('');
    const custom = d.environment === 'custom';
    const url = custom ? d.server_url : envInfo(d.environment).url;
    return `<div class="field">
      <span class="label">Servidor</span>
      <div class="choice-grid" role="radiogroup">${cards}</div>
      <button type="button" class="disclosure ${S.showServer ? 'open' : ''}" data-action="toggle-server">${icon('chevron-right')}Outro servidor <small>— uso do suporte técnico</small></button>
      <div class="server-adv" ${S.showServer ? '' : 'hidden'}>
        <div class="grid-2">
          <label class="mini-field"><span>Ambiente</span>
            <span class="select-wrap"><select class="input" data-scope="${scope}" data-field="environment">${options}</select>${icon('chevron-down')}</span>
          </label>
          <label class="mini-field"><span>Endereço do servidor</span>
            <input class="input input--mono" data-scope="${scope}" data-field="server_url" value="${esc(url)}" ${custom ? '' : 'disabled'} placeholder="wss://servidor/ws/printer" spellcheck="false">
          </label>
        </div>
      </div>
    </div>`;
  }

  function connFeedback() {
    switch (S.conn) {
      case 'testing': return feedback('info', 'Conectando ao servidor…', 'Validando a chave. Isso leva poucos segundos.', true);
      case 'ok': return feedback('success', 'Conectado ao servidor', 'Chave validada. Continue para escolher a impressora.');
      case 'failed': return feedback('error', 'Chave não reconhecida', 'O servidor recusou esta chave. Confira se você copiou a chave completa em Chaves de Impressão.');
      case 'server_error': return feedback('error', 'Erro no servidor ao validar a chave', 'O servidor teve uma falha interna e não concluiu a validação. Tente de novo em instantes; se continuar, avise o suporte do Meu Atendimento Virtual.');
      case 'unreachable': return feedback('warning', 'Sem resposta do servidor', 'Verifique a internet do totem e tente de novo. Se preferir, pule esta etapa e conecte depois.');
      case 'empty': return feedback('warning', 'Informe a chave de impressão', 'Cole ou digite a chave para continuar.');
      case 'no_url': return feedback('warning', 'Informe o endereço do servidor', 'Para um servidor personalizado, preencha o endereço (wss://…).');
      default: return '';
    }
  }

  // Garante que a mensagem de retorno fique visível (pode estar abaixo da dobra).
  function reveal(el) {
    if (el && el.firstElementChild) {
      setTimeout(() => el.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 30);
    }
  }

  function updateConn() {
    const el = $('#conn-feedback');
    if (el) {
      el.innerHTML = connFeedback();
      reveal(el);
    }
    refreshFooter();
  }

  function connChanged() {
    if (S.conn === 'testing') return;
    const d = S.draft;
    const c = S.config;
    const same = d.token.trim() === (c.token || '') && d.environment === c.environment &&
      (d.environment !== 'custom' || d.server_url.trim() === (c.server_url || ''));
    const next = same && S.status === 'connected' ? 'ok' : 'idle';
    if (next !== S.conn) { S.conn = next; updateConn(); }
  }

  async function connect() {
    const d = S.draft;
    const input = $('#token-draft');
    if (input) d.token = input.value;
    d.token = d.token.trim();
    if (!d.token) { S.conn = 'empty'; updateConn(); if (input) input.focus(); return; }
    if (d.environment === 'custom' && !d.server_url.trim()) {
      S.conn = 'no_url';
      S.support = true;
      S.showServer = true;
      updateServer('draft');
      updateConn();
      return;
    }
    S.conn = 'testing';
    S.awaiting = true;
    updateConn();
    clearTimeout(S.connTimer);
    S.connTimer = setTimeout(() => { if (S.conn === 'testing') { S.conn = 'unreachable'; updateConn(); } }, 20000);
    try {
      applySnapshot(await call('save_config', {
        token: d.token, environment: d.environment, server_url: d.server_url,
      }), false);
    } catch (e) {
      console.error(e);
      S.conn = 'unreachable';
      updateConn();
    }
  }

  function updateServer(scope) {
    const el = $(`#server-${scope}`);
    if (el && S[scope]) el.innerHTML = serverBlock(scope);
  }

  function toggleSupport() {
    S.support = !S.support;
    updateServer('draft');
    updateServer('form');
    toast('info', S.support ? 'Modo suporte ativado' : 'Modo suporte desativado',
      S.support ? 'A escolha de servidor está visível na conexão.' : 'A escolha de servidor foi ocultada.');
  }

  function envChanged(scope) {
    const d = S[scope];
    if (d.environment !== 'custom') d.server_url = envInfo(d.environment).url;
    updateServer(scope);
    if (scope === 'draft') connChanged();
    else updateSavebar();
  }

  // ── Passo 2: impressora ──
  function stepPrinter() {
    return `${stepHead(2, 'Escolha a impressora', 'Selecione a impressora térmica do totem. Se ela não aparecer, confira se está ligada e com o cabo conectado e atualize a lista.')}
      <div class="list-head">
        <span class="muted" id="printer-count">${printerCount()}</span>
        <button type="button" class="btn btn--ghost btn--sm" data-action="refresh-printers">${icon('refresh-cw')}Atualizar lista</button>
      </div>
      <div class="printer-list" data-printer-list="draft">${printerList('draft')}</div>
      <div data-test-card="draft">${testCard('draft')}</div>`;
  }

  function printerCount() {
    if (!Array.isArray(S.printers)) return 'Procurando impressoras…';
    const n = S.printers.length;
    return n === 1 ? '1 impressora encontrada' : `${n} impressoras encontradas`;
  }

  function printerList(scope) {
    if (!Array.isArray(S.printers)) {
      return `<div class="skeleton-list">${'<div class="skeleton"></div>'.repeat(3)}</div>`;
    }
    const sel = S[scope].printer_name;
    const list = S.printers.slice();
    if (sel && !list.some((p) => p.name === sel)) list.unshift({ name: sel, virtual: false, thermal: false, missing: true });
    if (!list.length) {
      return `<div class="empty">
        <span class="empty-icon">${icon('printer')}</span>
        <b>Nenhuma impressora encontrada</b>
        <p>Ligue a impressora, conecte o cabo USB e clique em <b>Atualizar lista</b>.</p>
      </div>`;
    }
    return list.map((p) => {
      const on = p.name === sel;
      const pl = p.virtual ? ['neutral', 'Virtual'] : printerPill(p.name);
      const sub = p.missing ? 'Configurada antes, mas não encontrada agora'
        : p.virtual ? 'Não imprime em papel'
          : p.thermal ? 'Impressora térmica de cupom' : 'Impressora';
      return `<button type="button" class="printer ${on ? 'is-selected' : ''} ${p.virtual ? 'is-virtual' : ''}"
          data-action="select-printer" data-scope="${scope}" data-name="${esc(p.name)}" role="radio" aria-checked="${on}">
        <span class="printer-icon">${icon(p.virtual ? 'file-text' : 'printer')}</span>
        <span class="printer-text"><b>${esc(p.name)}</b><small>${sub}</small></span>
        ${p.thermal ? '<span class="tag">Recomendada</span>' : ''}
        ${pill(pl, `data-pill="${esc(p.name)}"`)}
        <span class="radio"></span>
      </button>`;
    }).join('');
  }

  async function loadPrinters() {
    S.printers = null;
    updatePrinterUI();
    try {
      S.printers = await call('list_printers');
    } catch (e) {
      console.error(e);
      S.printers = [];
    }
    // No assistente, já sugere a primeira impressora física encontrada.
    if (S.view === 'wizard' && !S.draft.printer_name) {
      const first = S.printers.find((p) => !p.virtual);
      if (first) S.draft.printer_name = first.name;
    }
    updatePrinterUI();
    refreshStatuses();
  }

  function refreshStatuses() {
    const names = new Set((S.printers || []).filter((p) => !p.virtual).map((p) => p.name));
    [S.draft && S.draft.printer_name, S.form && S.form.printer_name, S.config.printer_name]
      .filter(Boolean).forEach((n) => names.add(n));
    names.forEach((n) => checkPrinter(n));
  }

  async function checkPrinter(name) {
    if (!name) return;
    try {
      S.pstatus[name] = await call('printer_status', name);
    } catch (e) {
      return;
    }
    $$('[data-pill]').forEach((el) => {
      if (el.dataset.pill === name) el.outerHTML = pill(printerPill(name), `data-pill="${esc(name)}"`);
    });
    if (S.view === 'app' && S.page === 'overview' && name === S.config.printer_name) {
      updateHero();
      const sp = $('#stat-printer');
      if (sp) sp.innerHTML = statPrinter();
    }
    if (S.view === 'wizard' && S.step === 4) rerenderStep();
  }

  function updatePrinterUI() {
    $$('[data-printer-list]').forEach((el) => { el.innerHTML = printerList(el.dataset.printerList); });
    const count = $('#printer-count');
    if (count) count.textContent = printerCount();
    $$('[data-action="refresh-printers"]').forEach((b) => b.classList.toggle('is-spinning', !Array.isArray(S.printers)));
    refreshFooter();
  }

  // variant 'model': convida a imprimir um exemplo do modelo escolhido.
  function testCard(scope, variant = 'printer') {
    const busy = S.test.state === 'busy';
    const [title, text, label] = variant === 'model'
      ? ['Veja no papel antes de decidir', `Imprime um exemplo do modelo <b>${esc(modelLabel(S[scope].receipt_model))}</b> na impressora escolhida.`, 'Imprimir exemplo']
      : ['Imprima um ticket de teste', 'Confirme que a impressora escolhida está funcionando.', 'Imprimir teste'];
    return `<div class="test-card">
        <span class="test-art">${icon('receipt-text')}</span>
        <div class="test-text"><b>${title}</b><p>${text}</p></div>
        <button type="button" class="btn btn--secondary" data-action="test-print" data-scope="${scope}" ${busy ? 'disabled' : ''}>
          ${busy ? spinner() : icon('printer')}${busy ? 'Imprimindo…' : label}
        </button>
      </div>
      <div class="fb-slot">${testFeedback()}</div>`;
  }

  function testFeedback() {
    const t = S.test;
    if (t.state === 'busy') return feedback('info', 'Enviando ticket de teste…', 'Aguarde alguns segundos.', true);
    if (t.state === 'ok') return feedback('success', 'Ticket de teste enviado!', `Confira se o ticket saiu na impressora <b>${esc(t.printer)}</b>.`);
    if (t.state === 'error') return feedback('error', 'A impressão de teste falhou', esc(t.message || '').replace(/\n/g, '<br>'));
    return '';
  }

  function updateTest() {
    $$('[data-test-card]').forEach((el) => {
      el.innerHTML = testCard(el.dataset.testCard, el.dataset.variant);
      reveal(el.querySelector('.fb-slot'));
    });
  }

  async function testPrint(scope) {
    const name = S[scope].printer_name;
    if (!name) {
      S.test = { state: 'error', message: 'Selecione uma impressora primeiro.' };
      updateTest();
      return;
    }
    S.test = { state: 'busy', printer: name };
    updateTest();
    let r;
    try {
      r = await call('test_print', name, S[scope].receipt_model, qrOn(), S[scope].paper_width);
    } catch (e) {
      r = { ok: false, message: String(e) };
    }
    S.test = { state: r.ok ? 'ok' : 'error', message: r.message, printer: name };
    updateTest();
    checkPrinter(name);
  }

  // ── Passo 3: comprovante ──
  function stepReceipt() {
    return `${stepHead(3, 'Escolha o modelo do comprovante', 'Selecione um modelo para ver, ao lado, como a senha sai impressa. Você pode trocar quando quiser.')}
      ${modelPicker('draft')}
      <div data-logo-card>${logoCard()}</div>
      <div data-test-card="draft" data-variant="model">${testCard('draft', 'model')}</div>`;
  }

  // ── Logo no topo do comprovante (vale para todos os modelos; salvo na hora) ──
  const LOGO_SIZES = [['small', 'Pequeno'], ['medium', 'Médio'], ['large', 'Grande']];

  function logoCard() {
    const l = S.logo || {};
    const busy = S.logoBusy;
    const sizes = LOGO_SIZES.map(([key, label]) =>
      `<button type="button" class="${l.size === key ? 'active' : ''}" data-action="logo-size" data-size="${key}" ${busy ? 'disabled' : ''}>${label}</button>`).join('');
    return `<div class="logo-card ${l.enabled ? 'has-logo' : ''}">
      <span class="logo-thumb">${l.enabled ? `<img src="${l.image}" alt="Logo como sai na impressão">` : icon('image')}</span>
      <div class="logo-text">
        <b>Logo no topo do comprovante</b>
        <p>${l.enabled
          ? `Sai no topo de todos os modelos, em preto e branco · ${l.width_mm} × ${l.height_mm} mm`
          : 'Opcional. Use PNG ou JPG; fundo branco ou transparente fica melhor.'}</p>
        ${l.enabled ? `<div class="seg seg--sm" role="radiogroup" aria-label="Tamanho do logo">${sizes}</div>` : ''}
      </div>
      <div class="logo-actions">
        <label class="btn btn--secondary btn--sm ${busy ? 'is-disabled' : ''}">
          ${busy ? spinner() : icon('upload')}${l.enabled ? 'Trocar' : 'Adicionar logo'}
          <input type="file" accept="image/png,image/jpeg,image/bmp,image/gif,image/webp" data-logo-input hidden ${busy ? 'disabled' : ''}>
        </label>
        ${l.enabled ? `<button type="button" class="btn btn--ghost btn--sm" data-action="remove-logo" ${busy ? 'disabled' : ''}>${icon('trash-2')}Remover</button>` : ''}
      </div>
    </div>`;
  }

  function updateLogoUI() {
    $$('[data-logo-card]').forEach((el) => { el.innerHTML = logoCard(); });
  }

  function logoChanged(r, success) {
    S.logoBusy = false;
    if (r && r.ok) {
      S.logo = r.logo;
      resetPreviews();              // as prévias precisam ser refeitas com o logo novo
      if (success) toast('success', success[0], success[1]);
    } else {
      toast('error', 'Não foi possível usar a imagem', (r && r.message) || '');
    }
    updateLogoUI();
  }

  async function logoCall(method, arg, success) {
    S.logoBusy = true;
    updateLogoUI();
    let r;
    try {
      r = arg === undefined ? await call(method) : await call(method, arg);
    } catch (e) {
      r = { ok: false, message: String(e) };
    }
    logoChanged(r, success);
  }

  // Lista de modelos + prévia grande ("Como vai sair") do modelo selecionado.
  function modelPicker(scope) {
    const sel = S[scope].receipt_model;
    const options = S.models.map((m) => {
      const on = m.key === sel;
      const tag = MODEL_TAG[m.key];
      return `<button type="button" class="model-option ${on ? 'is-selected' : ''}" data-action="select-model"
          data-scope="${scope}" data-key="${m.key}" role="radio" aria-checked="${on}">
        <span class="radio"></span>
        <span class="mo-text">
          <b>${esc(m.label)}${tag ? `<span class="tag tag--sm">${tag}</span>` : ''}</b>
          <small>${MODEL_DESC[m.key] || ''}</small>
        </span>
      </button>`;
    }).join('');
    const papers = [['80', '80 mm'], ['58', '58 mm']].map(([key, label]) =>
      `<button type="button" class="${S[scope].paper_width === key ? 'active' : ''}" data-action="select-paper" data-scope="${scope}" data-paper="${key}" role="radio" aria-checked="${S[scope].paper_width === key}">${label}</button>`).join('');
    return `<div class="paper-row">
        <span><b>Largura da bobina</b><small>Meça o papel: a maioria das impressoras de totem usa 80 mm.</small></span>
        <div class="seg" role="radiogroup" aria-label="Largura da bobina">${papers}</div>
      </div>
      <div class="model-picker">
      <div class="model-list" role="radiogroup" aria-label="Modelos de comprovante">${options}</div>
      <div class="model-preview">
        <div class="mp-head">
          <span class="mp-title">
            <span class="eyebrow">Como vai sair</span>
            <span class="mp-name" data-preview-name="${scope}">${esc(modelLabel(sel))}</span>
          </span>
          <label class="mini-switch" title="Mostrar o exemplo com ou sem QR Code">
            <input type="checkbox" data-qr-toggle ${qrOn() ? 'checked' : ''}><span></span>QR Code
          </label>
        </div>
        <button type="button" class="mp-stage" data-action="zoom-preview" data-scope="${scope}" title="Ampliar a prévia">
          <span class="mp-paper" data-preview="${scope}" data-paper="${S[scope].paper_width}">${previewInner(sel, S[scope].paper_width)}</span>
          <span class="mp-zoom">${icon('zoom-in')}Ampliar</span>
        </button>
        <p class="mp-note" data-preview-note>${previewNote()}</p>
      </div>
    </div>`;
  }

  // QR Code na prévia: automático (conforme os tickets da conta) ou escolhido.
  function qrOn() {
    return S.previewQr !== null ? S.previewQr : !!(S.sample && S.sample.has_qr);
  }

  function previewNote() {
    const s = S.sample || {};
    if (!s.source) {
      return 'Exemplo com dados fictícios. Quando chegar o primeiro ticket, a prévia passa a usar o cabeçalho, o rodapé e o QR Code da sua conta.';
    }
    const origem = s.source === 'servidor' ? 'informados pelo servidor' : 'do último ticket recebido';
    return `Com o cabeçalho e o rodapé ${origem}. Esta conta ${s.has_qr ? '<b>imprime QR Code</b>' : '<b>não imprime QR Code</b>'}.`;
  }

  function resetPreviews() {
    S.previewGen += 1;
    S.previews = {};
    refreshPreviews();
    prefetchPreviews();
    $$('[data-qr-toggle]').forEach((el) => { el.checked = qrOn(); });
    $$('[data-preview-note]').forEach((el) => { el.innerHTML = previewNote(); });
  }

  // A prévia é uma imagem gerada no Python a partir dos MESMOS comandos
  // enviados à impressora (ticket_preview.py). Sem ela (ex.: navegador de
  // desenvolvimento), cai para a ilustração em HTML.
  const previewKey = (key, paper) => `${key}@${paper || '80'}`;

  function previewInner(key, paper) {
    const p = S.previews[previewKey(key, paper)];
    if (p && p.src) return `<img class="mp-img enter" src="${p.src}" alt="Prévia do comprovante ${esc(modelLabel(key))}">`;
    if (p && p.failed) {
      const logo = S.logo && S.logo.enabled ? `<img class="paper-logo" src="${S.logo.image}" alt="">` : '';
      const qr = qrOn() ? '<span class="paper-qr"></span>' : '';
      const html = receiptPaper(key)
        .replace(/(<span class="paper[^"]*">)/, `$1${logo}`)
        .replace(/<\/span>\s*$/, `${qr}</span>`);
      return `<span class="paper-wrap mp-fallback enter">${html}</span>`;
    }
    if (!p) loadPreview(key, paper);
    return '<span class="mp-loading"></span>';
  }

  async function loadPreview(key, paper) {
    const id = previewKey(key, paper);
    if (S.previews[id]) return;
    const gen = S.previewGen;
    S.previews[id] = { loading: true };
    let r = null;
    try { r = await call('preview_ticket', key, qrOn(), paper || '80'); } catch (e) { r = null; }
    if (gen !== S.previewGen) return;         // logo/QR mudou no meio: resultado antigo
    S.previews[id] = r && r.ok ? { src: r.image } : { failed: true };
    refreshPreviews();
  }

  function prefetchPreviews() {
    const d = S.view === 'wizard' ? S.draft : S.form;
    const paper = (d && d.paper_width) || S.config.paper_width || '80';
    S.models.forEach((m) => loadPreview(m.key, paper));
  }

  function refreshPreviews() {
    $$('[data-preview]').forEach((el) => {
      const d = S[el.dataset.preview];
      if (!d) return;
      const key = d.receipt_model;
      const p = S.previews[previewKey(key, d.paper_width)] || {};
      const shown = `${previewKey(key, d.paper_width)}:${S.previewGen}:${p.src ? 'img' : p.failed ? 'html' : 'loading'}`;
      if (el.dataset.shown === shown) return;
      el.dataset.shown = shown;
      el.dataset.paper = d.paper_width;
      el.innerHTML = previewInner(key, d.paper_width);
    });
    $$('[data-preview-name]').forEach((el) => {
      const d = S[el.dataset.previewName];
      if (d) el.textContent = modelLabel(d.receipt_model);
    });
  }

  function zoomPreview(scope) {
    const key = S[scope].receipt_model;
    const paper = S[scope].paper_width;
    const p = S.previews[previewKey(key, paper)];
    if (!p || !p.src) return;
    const wrap = document.createElement('div');
    wrap.className = 'lightbox';
    wrap.innerHTML = `<div class="lightbox-inner" role="dialog" aria-modal="true" aria-label="Prévia ampliada">
        <div class="lightbox-head">
          <b>${esc(modelLabel(key))}</b><span>Prévia ampliada · bobina de ${esc(paper)} mm</span>
          <button type="button" class="lightbox-close" data-close aria-label="Fechar">${icon('x')}</button>
        </div>
        <div class="lightbox-scroll"><img src="${p.src}" alt="Prévia ampliada do comprovante"></div>
      </div>`;
    document.body.appendChild(wrap);
    const close = () => {
      document.removeEventListener('keydown', onKey);
      wrap.classList.add('leave');
      setTimeout(() => wrap.remove(), 180);
    };
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', onKey);
    wrap.addEventListener('click', (e) => { if (e.target === wrap || e.target.closest('[data-close]')) close(); });
  }

  // Ilustração em HTML de cada modelo (reserva quando a prévia real não está disponível).
  function receiptPaper(key) {
    const now = new Date();
    const date = `${now.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} ${now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
    switch (key) {
      case 'thermal_classic':
        return `<span class="paper paper--classic">
          <span class="t-xl t-b">SENHA: A001</span>
          <span class="rule rule--double"></span>
          <span class="t-md t-b">Bem-vindo!</span>
          <span class="rule rule--dashed"></span>
          <span class="t-sm t-b t-left">SERVIÇOS:</span>
          <span class="t-sm t-left t-indent">Caixa</span>
          <span class="t-sm t-i t-gap">Volte sempre!</span>
          <span class="t-sm">Data: ${date}</span>
        </span>`;
      case 'compact':
        return `<span class="paper paper--compact">
          <span class="t-sm t-b">Bem-vindo!</span>
          <span class="t-lg t-b">SENHA A001</span>
          <span class="t-sm">Caixa - ${date}</span>
          <span class="t-xs">Volte sempre!</span>
        </span>`;
      case 'big_number':
        return `<span class="paper paper--big">
          <span class="t-sm t-b">Bem-vindo!</span>
          <span class="t-xs t-gap-sm">SUA SENHA</span>
          <span class="t-huge t-b">A001</span>
          <span class="rule rule--dashed"></span>
          <span class="t-tall">Caixa</span>
          <span class="t-sm">${date}</span>
          <span class="t-sm t-gap-sm">Volte sempre!</span>
        </span>`;
      case 'inverted':
        return `<span class="paper paper--inverted">
          <span class="band t-md t-b">Bem-vindo!</span>
          <span class="t-xs t-gap">SENHA</span>
          <span class="t-xl t-b">A001</span>
          <span class="t-sm t-left t-gap"><b>Serviço:</b> Caixa</span>
          <span class="t-sm t-left"><b>Data:</b> ${date}</span>
          <span class="band band--thin t-sm t-b t-gap">Volte sempre!</span>
        </span>`;
      case 'framed':
        return `<span class="paper paper--framed">
          <span class="frame frame--strong t-sm t-b">Bem-vindo!</span>
          <span class="t-xs t-gap">SENHA</span>
          <span class="t-xl t-b">A001</span>
          <span class="frame t-sm t-left t-gap"><span>Serviço: Caixa</span><span>Data: ${date}</span></span>
          <span class="t-sm t-gap-sm">Volte sempre!</span>
        </span>`;
      default:
        return `<span class="paper paper--reduced">
          <span class="t-md">Bem-vindo!</span>
          <span class="t-md t-b">Código: A001</span>
          <span class="t-md">Serviços: Caixa</span>
          <span class="t-md">Data: ${date}</span>
          <span class="t-md">Volte sempre!</span>
        </span>`;
    }
  }

  // ── Passo 4: concluir ──
  function stepDone() {
    const d = S.draft;
    const connected = S.status === 'connected';
    const pst = d.printer_name ? S.pstatus[d.printer_name] : null;
    const allOk = connected && !!d.printer_name && !(pst && !pst.ready);
    const env = shortEnv(d.environment);
    // A animação do ✓ roda só na primeira exibição (o passo é redesenhado a cada status).
    const anim = !S.doneAnimated;
    S.doneAnimated = true;
    return `<div class="done-hero ${anim ? '' : 'no-anim'}">
        <div class="done-badge ${allOk ? 'ok' : 'warn'}">
          ${allOk
            ? '<svg class="done-check" viewBox="0 0 52 52" aria-hidden="true"><circle class="dc-circle" cx="26" cy="26" r="24"/><path class="dc-tick" d="M15.5 27.5l7 7 14-15"/></svg>'
            : icon('triangle-alert')}
        </div>
        <span class="eyebrow">Revisão final</span>
        <h1>${allOk ? 'Tudo pronto!' : 'Quase lá'}</h1>
        <p class="lead">${allOk
          ? 'Confira o resumo e conclua para começar a imprimir as senhas.'
          : 'Alguns itens precisam de atenção. Você pode concluir agora e ajustar depois pelo painel.'}</p>
      </div>
      <div class="summary">
        ${summaryRow('server', 'Servidor', env.title, connPill(), 1)}
        ${summaryRow('printer', 'Impressora', d.printer_name || 'Nenhuma selecionada', printerPill(d.printer_name), 2)}
        ${summaryRow('receipt-text', 'Comprovante', `${modelLabel(d.receipt_model)} · bobina de ${d.paper_width} mm`, null, 3)}
      </div>`;
  }

  function summaryRow(ic, label, value, pl, step) {
    return `<div class="summary-row">
      <span class="summary-icon">${icon(ic)}</span>
      <span class="summary-text"><small>${label}</small><b>${esc(value)}</b></span>
      ${pl ? pill(pl) : ''}
      <button type="button" class="link-btn" data-action="goto" data-step="${step}">Alterar</button>
    </div>`;
  }

  async function finish(btn) {
    btn.disabled = true;
    btn.innerHTML = `${spinner('spinner--light')}Salvando…`;
    const d = S.draft;
    try {
      applySnapshot(await call('save_config', {
        token: d.token, environment: d.environment, server_url: d.server_url,
        printer_name: d.printer_name, receipt_model: d.receipt_model, paper_width: d.paper_width,
        onboarding_done: true,
      }), false);
    } catch (e) {
      toast('error', 'Não foi possível salvar', String(e));
      refreshFooter();
      return;
    }
    S.view = 'app';
    S.page = 'overview';
    render();
    toast('success', 'Configuração concluída!', 'O agente já está pronto para imprimir as senhas.');
    if (S.config.printer_name) checkPrinter(S.config.printer_name);
  }

  // ═══ PAINEL ════════════════════════════════════════════════════════════════

  const NAV = [
    ['overview', 'layout-dashboard', 'Visão geral'],
    ['settings', 'settings', 'Configurações'],
    ['logs', 'file-text', 'Registros'],
  ];

  function renderShell() {
    return `<div class="shell">
      <nav class="sidebar" aria-label="Navegação">
        <div class="sb-brand"><img src="assets/logo-white.png" alt="SIGA"><span>Agente de Impressão</span></div>
        ${NAV.map(([key, ic, label]) => `<button type="button" class="sb-item ${S.page === key ? 'active' : ''}" data-action="page" data-page="${key}" title="${label}">${icon(ic)}<span>${label}</span></button>`).join('')}
        <div class="sb-spacer"></div>
        <div class="sb-status" id="sb-status">${sbStatus()}</div>
        <p class="sb-foot">Fechar esta janela não desliga o agente: ele continua ativo perto do relógio.<br>Versão ${esc(S.version)}</p>
      </nav>
      <main class="content">
        <div class="content-scroll" id="content"><div class="page enter">${renderPage()}</div></div>
        <div class="savebar" id="savebar" role="region" aria-label="Alterações não salvas">
          <span>${icon('info')}Você tem alterações não salvas</span>
          <button type="button" class="btn btn--ghost btn--sm" data-action="discard-form">Descartar</button>
          <button type="button" class="btn btn--primary btn--sm" data-action="save-form">Salvar alterações</button>
        </div>
      </main>
    </div>`;
  }

  function renderPage() {
    if (S.page === 'settings') return pageSettings();
    if (S.page === 'logs') return pageLogs();
    return pageOverview();
  }

  function sbStatus() {
    const [tone, text] = connPill();
    return `<span class="sb-dot sb-dot--${tone}"></span>
      <span class="sb-status-text"><b>${text}</b><small>${esc(shortEnv().title)}</small></span>`;
  }

  function setPage(page) {
    if (S.page === 'settings' && page !== 'settings' && isDirty()) {
      confirmDialog({
        title: 'Descartar alterações?',
        message: 'Você tem alterações não salvas nas configurações.',
        ok: 'Descartar', danger: true,
      }).then((ok) => { if (ok) { S.form = null; showPage(page); } });
      return;
    }
    showPage(page);
  }

  function showPage(page) {
    stopLogs();
    S.page = page;
    if (page === 'settings') {
      S.form = formFromConfig();
      S.test = { state: 'idle' };
      S.showServer = !PRIMARY_ENVS.some((e) => e.key === S.form.environment);
    }
    $$('.sb-item').forEach((b) => b.classList.toggle('active', b.dataset.page === page));
    const content = $('#content');
    content.innerHTML = `<div class="page enter">${renderPage()}</div>`;
    content.scrollTop = 0;
    updateSavebar();
    if (page === 'settings') {
      if (!S.printers) loadPrinters(); else refreshStatuses();
      prefetchPreviews();
    }
    if (page === 'logs') startLogs();
    if (page === 'overview' && S.config.printer_name) checkPrinter(S.config.printer_name);
  }

  // ── Visão geral ──
  function heroState() {
    const s = S.status;
    const name = S.config.printer_name;
    const ps = name ? S.pstatus[name] : null;
    if (s === 'auth_failed') {
      return { tone: 'error', icon: 'key-round', title: 'Chave recusada pelo servidor',
        text: 'A chave deste totem não foi aceita. Confira a chave nas configurações.', action: ['settings', 'Corrigir chave'] };
    }
    if (s === 'server_error') {
      return { tone: 'error', icon: 'server', title: 'Erro no servidor ao validar a chave',
        text: 'O servidor teve uma falha interna. Não é problema do totem: tente reconectar e, se continuar, avise o suporte.', action: ['reconnect', 'Reconectar agora'] };
    }
    if (s === 'connecting' || s === 'reconnecting') {
      return { tone: 'info', busy: true, title: s === 'connecting' ? 'Conectando ao servidor…' : 'Reconectando ao servidor…',
        text: 'Isso costuma levar poucos segundos. Você não precisa fazer nada.' };
    }
    if (s !== 'connected') {
      return { tone: 'error', icon: 'wifi-off', title: 'Sem conexão com o servidor',
        text: 'Verifique a internet do totem. O agente tenta reconectar sozinho, mas você pode forçar agora.', action: ['reconnect', 'Reconectar agora'] };
    }
    if (!name) {
      return { tone: 'warning', icon: 'printer', title: 'Nenhuma impressora selecionada',
        text: 'Escolha a impressora do totem para começar a imprimir as senhas.', action: ['settings', 'Escolher impressora'] };
    }
    if (ps && !ps.ready) {
      return { tone: 'warning', icon: 'printer', title: `Impressora ${ps.label.toLowerCase()}`,
        text: 'Verifique se a impressora está ligada, com papel e com o cabo conectado.', action: ['test', 'Imprimir teste'] };
    }
    return { tone: 'success', icon: 'check', title: 'Pronto para imprimir',
      text: 'As senhas retiradas no totem saem automaticamente na impressora.', action: ['test', 'Imprimir teste'] };
  }

  function heroInner(h) {
    const [kind, label] = h.action || [];
    const main = kind
      ? `<button type="button" class="btn ${h.tone === 'success' ? 'btn--ghost' : 'btn--primary'}" data-action="hero" data-kind="${kind}">${icon(kind === 'test' ? 'printer' : kind === 'reconnect' ? 'refresh-cw' : 'settings')}${label}</button>`
      : '';
    const extra = kind !== 'reconnect' && !h.busy
      ? `<button type="button" class="btn btn--ghost" data-action="hero" data-kind="reconnect" title="Reconectar ao servidor">${icon('refresh-cw')}<span class="hide-sm">Reconectar</span></button>`
      : '';
    return `<span class="hero-badge">${h.busy ? spinner('spinner--lg spinner--light') : icon(h.icon)}</span>
      <div class="hero-text">
        <span class="hero-eyebrow">Status do agente</span>
        <h2>${esc(h.title)}</h2>
        <p>${esc(h.text)}</p>
      </div>
      <div class="hero-actions">${extra}${main}</div>`;
  }

  function updateHero() {
    const el = $('#hero');
    if (!el) return;
    const h = heroState();
    el.className = `hero hero--${h.tone}`;
    el.innerHTML = heroInner(h);
  }

  function statServer() {
    const env = shortEnv();
    return `<div class="stat-top"><span class="stat-icon">${icon('server')}</span>${pill(connPill())}</div>
      <span class="stat-label">Servidor</span>
      <b class="stat-value">${esc(env.title)}</b>
      <small class="stat-sub">${esc(env.sub)}</small>`;
  }

  function statPrinter() {
    const name = S.config.printer_name;
    const ps = name ? S.pstatus[name] : null;
    return `<div class="stat-top"><span class="stat-icon">${icon('printer')}</span>${pill(printerPill(name), `data-pill="${esc(name)}"`)}</div>
      <span class="stat-label">Impressora</span>
      <b class="stat-value" title="${esc(name)}">${esc(name || 'Nenhuma selecionada')}</b>
      <small class="stat-sub">${ps ? `Verificada às ${fmtTime(Date.now() / 1000)}` : 'Verificando status…'}</small>`;
  }

  function statPrints() {
    const st = S.stats || {};
    const last = st.last_print_at ? `Último às ${fmtTime(st.last_print_at)}` : 'Nenhum ticket ainda hoje';
    const failed = st.failed ? ` · ${st.failed} falha${st.failed > 1 ? 's' : ''}` : '';
    return `<div class="stat-top"><span class="stat-icon">${icon('receipt-text')}</span></div>
      <span class="stat-label">Impressos hoje</span>
      <b class="stat-value stat-value--big">${st.printed || 0}</b>
      <small class="stat-sub">${last}${failed}</small>`;
  }

  const ACT_ICON = { success: 'check', error: 'x', warning: 'triangle-alert', info: 'info' };

  function activityList() {
    if (!S.activity.length) {
      return `<li class="activity-empty"><span class="empty-icon">${icon('activity')}</span>
        <div><b>Nenhuma atividade ainda</b><p>Os tickets impressos e os eventos de conexão aparecem aqui.</p></div></li>`;
    }
    return S.activity.slice(0, 7).map((a) => `<li class="act act--${a.tone}">
        <span class="act-dot">${icon(ACT_ICON[a.tone] || 'info')}</span>
        <span class="act-text"><b>${esc(a.title)}</b>${a.detail ? `<small>${esc(a.detail)}</small>` : ''}</span>
        <time data-ts="${a.ts}">${relTime(a.ts)}</time>
      </li>`).join('');
  }

  function pageOverview() {
    const h = heroState();
    return `<header class="page-head">
        <div><h1>Visão geral</h1><p>Acompanhe o funcionamento do agente neste totem.</p></div>
        <button type="button" class="btn btn--ghost" data-action="open-wizard">${icon('list-checks')}Configuração guiada</button>
      </header>
      <section class="hero hero--${h.tone}" id="hero">${heroInner(h)}</section>
      <section class="stats">
        <article class="stat" id="stat-server">${statServer()}</article>
        <article class="stat" id="stat-printer">${statPrinter()}</article>
        <article class="stat" id="stat-prints">${statPrints()}</article>
      </section>
      <section class="card">
        <div class="card-head"><h3>Atividade recente</h3>
          <button type="button" class="link-btn" data-action="page" data-page="logs">Ver registros${icon('chevron-right')}</button>
        </div>
        <ul class="activity" id="activity">${activityList()}</ul>
      </section>`;
  }

  async function heroAction(btn) {
    const kind = btn.dataset.kind;
    if (kind === 'settings') return setPage('settings');
    if (kind === 'reconnect') return reconnect();
    const name = S.config.printer_name;
    btn.disabled = true;
    btn.innerHTML = `${spinner()}Imprimindo…`;
    let r;
    try {
      r = await call('test_print', name);
    } catch (e) {
      r = { ok: false, message: String(e) };
    }
    if (r.ok) toast('success', 'Ticket de teste enviado', `Confira a impressora ${name}.`);
    else toast('error', 'A impressão de teste falhou', r.message);
    await checkPrinter(name);
    updateHero();
  }

  async function reconnect() {
    S.status = 'connecting';
    onStatusUi();
    try { await call('reconnect'); } catch (e) { console.error(e); }
  }

  // ── Configurações ──
  function formFromConfig() {
    const c = S.config;
    return {
      token: c.token || '', environment: c.environment, server_url: c.server_url || '',
      printer_name: c.printer_name || '', receipt_model: c.receipt_model, paper_width: c.paper_width || '80',
      auto_connect: !!c.auto_connect, start_with_windows: !!c.start_with_windows,
    };
  }

  function isDirty() {
    if (!S.form) return false;
    const base = formFromConfig();
    return Object.keys(base).some((k) => {
      if (k === 'server_url' && S.form.environment !== 'custom') return false;
      return String(S.form[k]).trim() !== String(base[k]).trim();
    });
  }

  function updateSavebar() {
    const bar = $('#savebar');
    if (bar) bar.classList.toggle('show', S.page === 'settings' && isDirty());
  }

  const sectionHead = (ic, title, text, extra = '') => `<div class="section-head">
      <span class="section-icon">${icon(ic)}</span>
      <div class="section-head-text"><h3>${title}</h3><p>${text}</p></div>
      ${extra ? `<div class="section-head-extra">${extra}</div>` : ''}
    </div>`;

  function toggleRow(field, title, text, disabled = false) {
    return `<label class="toggle-row ${disabled ? 'is-disabled' : ''}">
      <span class="toggle-text"><b>${title}</b><small>${text}</small></span>
      <span class="switch"><input type="checkbox" data-scope="form" data-field="${field}" ${S.form[field] ? 'checked' : ''} ${disabled ? 'disabled' : ''}><span></span></span>
    </label>`;
  }

  function pageSettings() {
    return `<header class="page-head">
        <div><h1>Configurações</h1><p>Ajuste a conexão, a impressora e o comprovante deste totem.</p></div>
      </header>
      <section class="card section">
        ${sectionHead('key-round', 'Conexão', 'Chave que liga este totem à sua conta.', `<span id="settings-conn">${pill(connPill())}</span>`)}
        ${tokenField('form')}
        <div id="server-form">${serverBlock('form')}</div>
        <div class="section-foot">
          <button type="button" class="btn btn--ghost btn--sm" data-action="reconnect">${icon('refresh-cw')}Reconectar agora</button>
        </div>
      </section>
      <section class="card section">
        ${sectionHead('printer', 'Impressora', 'Onde as senhas são impressas.', `<button type="button" class="btn btn--ghost btn--sm" data-action="refresh-printers">${icon('refresh-cw')}Atualizar lista</button>`)}
        <div class="printer-list" data-printer-list="form">${printerList('form')}</div>
        <div data-test-card="form">${testCard('form')}</div>
      </section>
      <section class="card section">
        ${sectionHead('receipt-text', 'Comprovante', 'Modelo do ticket entregue ao cliente.')}
        ${modelPicker('form')}
        <div data-logo-card>${logoCard()}</div>
      </section>
      <section class="card section">
        ${sectionHead('settings', 'Sistema', 'Como o agente se comporta no Windows.')}
        ${toggleRow('start_with_windows', 'Iniciar junto com o Windows',
          S.frozen ? 'Abre automaticamente, em segundo plano, quando o computador liga.' : 'Disponível apenas na versão instalada do agente.', !S.frozen)}
        ${toggleRow('auto_connect', 'Conectar automaticamente', 'Conecta ao servidor assim que o agente inicia.')}
      </section>
      <div class="savebar-space"></div>`;
  }

  async function saveForm(btn) {
    btn.disabled = true;
    btn.innerHTML = `${spinner('spinner--light')}Salvando…`;
    try {
      applySnapshot(await call('save_config', { ...S.form }), false);
      S.form = formFromConfig();
      toast('success', 'Alterações salvas', 'O agente está aplicando as novas configurações.');
    } catch (e) {
      toast('error', 'Não foi possível salvar', String(e));
    }
    btn.disabled = false;
    btn.textContent = 'Salvar alterações';
    updateSavebar();
    const sb = $('#sb-status');
    if (sb) sb.innerHTML = sbStatus();
  }

  // ── Registros ──
  const LEVEL_PT = { INFO: 'INFO', WARNING: 'AVISO', ERROR: 'ERRO', CRITICAL: 'CRÍTICO', DEBUG: 'DEBUG' };
  const LOG_RE = /^\d{4}-\d\d-\d\d (\d\d:\d\d:\d\d) \[(\w+)\s*\] ([^:]+): ([\s\S]*)$/;

  function levelOf(line) {
    if (/\[(ERROR|CRITICAL)/.test(line)) return 'error';
    if (/\[WARNING/.test(line)) return 'warn';
    if (/\[DEBUG/.test(line)) return 'debug';
    return 'info';
  }

  function passesFilter(level) {
    if (S.logFilter === 'error') return level === 'error';
    if (S.logFilter === 'warn') return level === 'error' || level === 'warn';
    return true;
  }

  function logLineHtml(line) {
    const lvl = levelOf(line);
    const m = line.match(LOG_RE);
    if (!m) return `<div class="log log--${lvl}"><span class="log-time"></span><span class="log-lvl"></span><span class="log-msg">${esc(line)}</span><span class="log-src"></span></div>`;
    return `<div class="log log--${lvl}"><span class="log-time">${m[1]}</span><span class="log-lvl">${LEVEL_PT[m[2]] || m[2]}</span><span class="log-msg">${esc(m[4])}</span><span class="log-src">${esc(m[3])}</span></div>`;
  }

  function pageLogs() {
    const seg = [['all', 'Todos'], ['warn', 'Avisos'], ['error', 'Erros']]
      .map(([k, l]) => `<button type="button" class="${S.logFilter === k ? 'active' : ''}" data-action="log-filter" data-filter="${k}">${l}</button>`).join('');
    return `<header class="page-head">
        <div><h1>Registros</h1><p>Eventos do agente em tempo real — útil para o suporte técnico.</p></div>
        <div class="head-actions">
          <div class="seg" role="tablist">${seg}</div>
        </div>
      </header>
      <div class="logbox">
        <div class="logbox-bar">
          <span class="live-dot"></span><span>Ao vivo</span><span class="logbox-count" id="log-count"></span>
          <span class="logbox-actions">
            <button type="button" class="btn btn--dark btn--sm" data-action="copy-logs">${icon('copy')}Copiar</button>
            <button type="button" class="btn btn--dark btn--sm" data-action="open-folder">${icon('folder-open')}Abrir pasta</button>
            <button type="button" class="btn btn--dark btn--sm btn--dark-danger" data-action="clear-logs">${icon('trash-2')}Limpar</button>
          </span>
        </div>
        <div class="logview" id="logview"></div>
      </div>`;
  }

  function renderLogs() {
    const view = $('#logview');
    if (!view) return;
    const lines = S.logs.filter((l) => passesFilter(levelOf(l)));
    view.innerHTML = lines.length
      ? lines.map(logLineHtml).join('')
      : `<div class="log-empty">${S.logs.length ? 'Nenhum registro com este filtro.' : 'Nenhum registro ainda.'}</div>`;
    view.scrollTop = view.scrollHeight;
    const count = $('#log-count');
    if (count) count.textContent = `${S.logs.length} ${S.logs.length === 1 ? 'linha' : 'linhas'}`;
  }

  function appendLogs(lines) {
    const view = $('#logview');
    if (!view) return;
    const atBottom = view.scrollHeight - view.scrollTop - view.clientHeight < 40;
    const visible = lines.filter((l) => passesFilter(levelOf(l)));
    if (visible.length) {
      const empty = view.querySelector('.log-empty');
      if (empty) empty.remove();
      view.insertAdjacentHTML('beforeend', visible.map(logLineHtml).join(''));
      while (view.children.length > 3000) view.firstElementChild.remove();
      if (atBottom) view.scrollTop = view.scrollHeight;
    }
    const count = $('#log-count');
    if (count) count.textContent = `${S.logs.length} ${S.logs.length === 1 ? 'linha' : 'linhas'}`;
  }

  async function pollLogs(initial) {
    let r;
    try { r = await call('get_logs', S.logsSeen); } catch (e) { return; }
    S.logsSeen = r.total;
    if (r.lines.length) {
      S.logs.push(...r.lines);
      if (S.logs.length > 3000) S.logs.splice(0, S.logs.length - 3000);
    }
    if (initial) renderLogs();
    else if (r.lines.length) appendLogs(r.lines);
  }

  function startLogs() {
    S.logs = [];
    S.logsSeen = 0;
    pollLogs(true);
    S.logTimer = setInterval(() => pollLogs(false), 800);
  }

  function stopLogs() {
    clearInterval(S.logTimer);
    S.logTimer = 0;
  }

  async function clearLogs() {
    const ok = await confirmDialog({
      title: 'Limpar os registros?',
      message: 'Os registros desta sessão serão apagados da tela. O arquivo de log no computador é mantido.',
      ok: 'Limpar', danger: true,
    });
    if (!ok) return;
    const r = await call('clear_logs');
    S.logs = [];
    S.logsSeen = r.total;
    renderLogs();
  }

  async function copyLogs() {
    const r = await call('copy_text', S.logs.join('\n'));
    if (r && r.ok) toast('success', 'Registros copiados', 'Cole na conversa com o suporte técnico.');
    else toast('error', 'Não foi possível copiar', (r && r.message) || '');
  }

  // ═══ EVENTOS DO PYTHON ═════════════════════════════════════════════════════

  function onStatusUi() {
    if (S.view !== 'app') return;
    const sb = $('#sb-status');
    if (sb) sb.innerHTML = sbStatus();
    if (S.page === 'overview') {
      updateHero();
      const ss = $('#stat-server');
      if (ss) ss.innerHTML = statServer();
    }
    if (S.page === 'settings') {
      const c = $('#settings-conn');
      if (c) c.innerHTML = pill(connPill());
    }
  }

  function onStatus(status) {
    S.status = status;
    if (S.view === 'wizard') {
      if (S.conn === 'testing') {
        // Ignora estados antigos até o agente começar a nova tentativa.
        if (S.awaiting) {
          if (status === 'connecting') { S.awaiting = false; return; }
          if (status !== 'auth_failed' && status !== 'server_error') return;
        }
        const next = status === 'connected' ? 'ok'
          : status === 'auth_failed' ? 'failed'
            : status === 'server_error' ? 'server_error'
              : (status === 'reconnecting' || status === 'disconnected') ? 'unreachable' : null;
        if (next) {
          S.conn = next;
          clearTimeout(S.connTimer);
          if (S.step === 1) updateConn();
        }
      } else if (S.conn === 'unreachable' && status === 'connected') {
        S.conn = 'ok';      // o agente conseguiu sozinho numa nova tentativa
        if (S.step === 1) updateConn();
      } else if (S.conn === 'idle' && S.draft.token && S.draft.token.trim() === (S.config.token || '')) {
        // Token já salvo (ex.: após atualização): reflete a conexão que o agente faz sozinho.
        const auto = { connected: 'ok', auth_failed: 'failed', server_error: 'server_error' }[status];
        if (auto) { S.conn = auto; if (S.step === 1) updateConn(); }
      }
      if (S.step === 4) rerenderStep();
      return;
    }
    onStatusUi();
  }

  function onActivity(item) {
    S.activity.unshift(item);
    S.activity = S.activity.slice(0, 60);
    const list = $('#activity');
    if (list) list.innerHTML = activityList();
  }

  function onStats(stats) {
    S.stats = stats;
    const el = $('#stat-prints');
    if (el) el.innerHTML = statPrints();
  }

  async function onShown() {
    try {
      const st = await call('get_state');
      applySnapshot(st, true);
    } catch (e) {
      return;
    }
    if (S.view === 'app') {
      onStatusUi();
      const act = $('#activity');
      if (act) act.innerHTML = activityList();
      onStats(S.stats);
      if (S.config.printer_name) checkPrinter(S.config.printer_name);
    }
  }

  window.agent = {
    receive(msg) {
      const handlers = {
        status: (d) => onStatus(d.status),
        activity: onActivity,
        stats: onStats,
        shown: onShown,
        // Chegou o formato real da conta: a prévia volta ao automático (QR conforme a conta).
        sample: (d) => { S.sample = d; S.previewQr = null; resetPreviews(); },
      };
      const h = handlers[msg && msg.type];
      if (!h) return;
      try { h(msg.data); } catch (e) { console.error(e); }
    },
  };

  // ═══ INTERAÇÕES ════════════════════════════════════════════════════════════

  const actions = {
    goto: (el) => goStep(Number(el.dataset.step)),
    next: () => goStep(S.step + 1),
    connect: () => connect(),
    finish: (el) => finish(el),
    'cancel-wizard': () => { S.view = 'app'; S.page = 'overview'; render(); },

    'toggle-token': () => {
      S.showToken = !S.showToken;
      $$('[data-field="token"]').forEach((i) => { i.type = S.showToken ? 'text' : 'password'; });
      $$('[data-action="toggle-token"]').forEach((b) => {
        b.innerHTML = icon(S.showToken ? 'eye-off' : 'eye');
        b.title = `${S.showToken ? 'Ocultar' : 'Mostrar'} chave`;
      });
    },
    'paste-token': async (el) => {
      const text = String((await call('read_clipboard')) || '').trim();
      if (!text) {
        toast('warning', 'Nada para colar', 'Copie a chave no painel do Meu Atendimento Virtual e tente de novo.');
        return;
      }
      const scope = el.dataset.scope;
      S[scope].token = text;
      const input = $(`#token-${scope}`);
      if (input) input.value = text;
      if (scope === 'draft') connChanged(); else updateSavebar();
    },
    'open-panel': () => call('open_panel'),
    'toggle-server': () => {
      S.showServer = !S.showServer;
      $$('.server-adv').forEach((x) => { x.hidden = !S.showServer; });
      $$('.disclosure').forEach((x) => x.classList.toggle('open', S.showServer));
    },
    'select-env': (el) => {
      S[el.dataset.scope].environment = el.dataset.key;
      envChanged(el.dataset.scope);
    },
    'select-printer': (el) => {
      const scope = el.dataset.scope;
      S[scope].printer_name = el.dataset.name;
      if (S.test.printer !== el.dataset.name) S.test = { state: 'idle' };
      updatePrinterUI();
      updateTest();
      if (scope === 'form') updateSavebar();
    },
    'refresh-printers': () => loadPrinters(),
    'test-print': (el) => testPrint(el.dataset.scope),
    'select-model': (el) => {
      const scope = el.dataset.scope;
      S[scope].receipt_model = el.dataset.key;
      $$(`[data-action="select-model"][data-scope="${scope}"]`).forEach((c) => {
        const on = c.dataset.key === el.dataset.key;
        c.classList.toggle('is-selected', on);
        c.setAttribute('aria-checked', String(on));
      });
      refreshPreviews();
      if (S.test.state !== 'busy') S.test = { state: 'idle' };
      updateTest();
      if (scope === 'form') updateSavebar();
    },
    'select-paper': (el) => {
      const scope = el.dataset.scope;
      S[scope].paper_width = el.dataset.paper;
      $$(`[data-action="select-paper"][data-scope="${scope}"]`).forEach((b) => {
        const on = b.dataset.paper === el.dataset.paper;
        b.classList.toggle('active', on);
        b.setAttribute('aria-checked', String(on));
      });
      refreshPreviews();
      prefetchPreviews();
      if (scope === 'form') updateSavebar();
    },
    'zoom-preview': (el) => zoomPreview(el.dataset.scope),
    'logo-size': (el) => {
      if (S.logo.size !== el.dataset.size) logoCall('set_logo_size', el.dataset.size);
    },
    'remove-logo': async () => {
      const ok = await confirmDialog({
        title: 'Remover o logo?', message: 'Os comprovantes voltam a sair sem logo.', ok: 'Remover', danger: true,
      });
      if (ok) logoCall('remove_logo', undefined, ['Logo removido', 'Os comprovantes saem sem logo.']);
    },

    page: (el) => setPage(el.dataset.page),
    'open-wizard': () => { startWizard(true); render(); },
    hero: (el) => heroAction(el),
    reconnect: () => reconnect(),
    'save-form': (el) => saveForm(el),
    'discard-form': () => { S.form = formFromConfig(); showPage('settings'); },
    'log-filter': (el) => {
      S.logFilter = el.dataset.filter;
      $$('[data-action="log-filter"]').forEach((b) => b.classList.toggle('active', b === el));
      renderLogs();
    },
    'copy-logs': () => copyLogs(),
    'open-folder': () => call('open_logs_folder'),
    'clear-logs': () => clearLogs(),
  };

  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el || el.disabled) return;
    const fn = actions[el.dataset.action];
    if (fn) { e.preventDefault(); fn(el, e); }
  });

  document.addEventListener('input', (e) => {
    const el = e.target.closest('[data-field]');
    if (!el) return;
    const scope = el.dataset.scope;
    const d = S[scope];
    if (!d) return;
    const field = el.dataset.field;
    d[field] = el.type === 'checkbox' ? el.checked : el.value;
    if (field === 'environment') { envChanged(scope); return; }
    if (scope === 'draft' && (field === 'token' || field === 'server_url')) connChanged();
    if (scope === 'form') updateSavebar();
  });

  // Liga/desliga o QR Code no exemplo da prévia.
  document.addEventListener('change', (e) => {
    const t = e.target.closest('[data-qr-toggle]');
    if (!t) return;
    S.previewQr = t.checked;
    resetPreviews();
  });

  // Escolha do arquivo do logo (lido como data URL e enviado ao Python).
  document.addEventListener('change', (e) => {
    const input = e.target.closest('[data-logo-input]');
    if (!input || !input.files || !input.files[0]) return;
    const file = input.files[0];
    input.value = '';
    if (file.size > 8 * 1024 * 1024) {
      toast('error', 'Imagem muito grande', 'Use uma imagem de até 8 MB.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => logoCall('set_logo', reader.result,
      [S.logo.enabled ? 'Logo trocado' : 'Logo adicionado', 'Veja na prévia como ele sai no papel.']);
    reader.onerror = () => toast('error', 'Não foi possível ler o arquivo', file.name);
    reader.readAsDataURL(file);
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.id === 'token-draft') { e.preventDefault(); connect(); }
    if (e.ctrlKey && e.shiftKey && e.code === 'KeyS') { e.preventDefault(); toggleSupport(); }
  });

  boot();
})();
