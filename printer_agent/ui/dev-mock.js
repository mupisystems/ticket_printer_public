/*
 * Simulador da ponte Python — SÓ para desenvolver a interface no navegador.
 *
 * Abra ui/index.html com ?mock na URL (ex.: via `python -m http.server`):
 *   ?mock               primeiro uso (assistente desde as boas-vindas)
 *   ?mock=configured    agente já configurado (abre o painel)
 *
 * Tokens especiais no assistente: "erro" → token recusado; "offline" → servidor sem resposta.
 * No app real (pywebview) este arquivo não faz nada.
 */
(function () {
  const params = new URLSearchParams(location.search);
  if (!params.has('mock') || window.pywebview) return;

  const configured = params.get('mock') === 'configured';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const emit = (type, data) => window.agent && window.agent.receive({ type, data });
  const now = () => Date.now() / 1000;

  const envs = {
    localhost: 'ws://localhost:8000/ws/printer',
    homologacao: 'wss://testes.meuatendimentovirtual.com.br/ws/printer',
    producao_br: 'wss://painel.meuatendimentovirtual.com.br/ws/printer',
    producao_us: 'wss://dash.awaitra.com/ws/printer',
    custom: '',
  };
  const envLabels = {
    localhost: 'Localhost', homologacao: 'Homologação', producao_br: 'Produção - Meu Atendimento Virtual',
    producao_us: 'Produção - Awaitra.com', custom: 'Personalizado',
  };

  const state = {
    status: configured ? 'connected' : 'disconnected',
    config: {
      environment: 'producao_br', server_url: envs.producao_br,
      token: configured ? '123e4567-e89b-12d3-a456-426614174000' : '',
      printer_name: configured ? 'EPSON TM-T20II Receipt' : '',
      receipt_model: 'default', paper_width: '80', auto_connect: true, start_with_windows: true,
    },
    stats: { date: '', printed: configured ? 37 : 0, failed: configured ? 1 : 0, last_print_at: configured ? now() - 240 : null },
    activity: configured ? [
      { ts: now() - 240, tone: 'success', title: 'Ticket impresso', detail: 'Job 8f2c1a' },
      { ts: now() - 900, tone: 'success', title: 'Ticket impresso', detail: 'Job 8f2b77' },
      { ts: now() - 1900, tone: 'warning', title: 'Conexão perdida', detail: 'Tentando reconectar automaticamente.' },
      { ts: now() - 1880, tone: 'success', title: 'Conectado ao servidor', detail: '' },
      { ts: now() - 5400, tone: 'error', title: 'Falha na impressão', detail: 'Impressora não respondeu. Verifique se está ligada e conectada.' },
    ] : [],
    logo: { enabled: false, size: 'medium' },
  };

  const printers = [
    { name: 'EPSON TM-T20II Receipt', virtual: false, thermal: true },
    { name: 'ELGIN i9', virtual: false, thermal: true },
    { name: 'HP LaserJet Pro M404', virtual: false, thermal: false },
    { name: 'Microsoft Print to PDF', virtual: true, thermal: false },
  ];
  const pstatus = {
    'EPSON TM-T20II Receipt': { ready: true, reason: '', label: 'Pronta' },
    'ELGIN i9': { ready: false, reason: 'impressora offline', label: 'Offline' },
    'HP LaserJet Pro M404': { ready: true, reason: '', label: 'Pronta' },
  };

  const logs = [];
  const log = (level, name, msg) => {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    logs.push(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())} [${level.padEnd(8)}] ${name}: ${msg}`);
  };
  log('INFO', 'printer_agent', 'Aplicativo desconectado do servidor.');
  log('INFO', 'printer_agent', 'Conectando ao servidor...');
  log('INFO', 'websocket_client', 'Conectado e autenticado em wss://painel.meuatendimentovirtual.com.br/ws/printer');
  log('INFO', 'printer_agent', 'Aplicativo conectado ao servidor. Pronto para imprimir.');
  log('WARNING', 'websocket_client', 'Conexão WebSocket encerrada (código 1006): no close frame received');
  log('INFO', 'websocket_client', 'Reconectando em 1s...');
  log('ERROR', 'printer_service', 'Impressão bloqueada (ELGIN i9): impressora offline');
  log('INFO', 'printer_service', 'Ticket impresso com sucesso (código: A001)');

  function setStatus(s) {
    state.status = s;
    emit('status', { status: s });
  }

  async function simulateConnect() {
    await sleep(150);
    setStatus('connecting');
    log('INFO', 'printer_agent', 'Conectando ao servidor...');
    await sleep(1400);
    const t = state.config.token.toLowerCase();
    if (t === 'erro') { setStatus('auth_failed'); log('ERROR', 'printer_agent', 'Autenticação falhou: Token inválido'); return; }
    if (t === 'offline') { setStatus('reconnecting'); log('WARNING', 'websocket_client', 'Conexão perdida: timed out'); return; }
    setStatus('connected');
    log('INFO', 'printer_agent', 'Aplicativo conectado ao servidor. Pronto para imprimir.');
  }

  const snapshot = () => JSON.parse(JSON.stringify({
    version: '2.3.0', status: state.status,
    configured: !!(state.config.token && state.config.printer_name), frozen: true,
    onboarding_required: params.get('mock') === 'update',
    config: state.config,
    environments: Object.keys(envs).map((k) => ({ key: k, label: envLabels[k], url: envs[k] })),
    receipt_models: [
      { key: 'default', label: 'Reduzido' }, { key: 'thermal_classic', label: 'Destaque' },
      { key: 'compact', label: 'Compacto' }, { key: 'big_number', label: 'Senha gigante' },
      { key: 'inverted', label: 'Faixa escura' }, { key: 'framed', label: 'Moldura' },
    ],
    stats: state.stats, activity: state.activity, logo: state.logo,
    ticket_sample: { source: null, has_qr: false },
  }));

  const api = {
    async get_state() { await sleep(120); return snapshot(); },
    async save_config(changes) {
      Object.assign(state.config, changes);
      if (state.config.environment !== 'custom') state.config.server_url = envs[state.config.environment];
      log('INFO', 'printer_agent', 'Configurações salvas pelo usuário. Aplicando e reconectando...');
      simulateConnect();
      await sleep(80);
      return snapshot();
    },
    async reconnect() { simulateConnect(); return { ok: true }; },
    async list_printers() { await sleep(700); return printers; },
    async printer_status(name) {
      await sleep(300 + Math.random() * 500);
      return { name, ...(pstatus[name] || { ready: false, reason: 'impressora não encontrada', label: 'Não encontrada' }) };
    },
    async test_print(name) {
      await sleep(1600);
      const st = pstatus[name];
      const ok = !!(st && st.ready);
      const item = { ts: now(), tone: ok ? 'success' : 'error', title: `Impressão de teste ${ok ? 'enviada' : 'falhou'}`, detail: ok ? name : 'A impressora não processou o teste.' };
      state.activity.unshift(item);
      emit('activity', item);
      return ok ? { ok: true, message: 'Impressão de teste realizada com sucesso!' }
        : { ok: false, message: 'A impressora não processou o teste.\nVerifique se está ligada, conectada e com papel.' };
    },
    async preview_ticket() { return { ok: false }; },   // no navegador usa a ilustração em HTML
    async set_logo(dataUrl) {
      await sleep(400);
      state.logo = { enabled: true, size: state.logo.size, image: dataUrl, width_mm: 36, height_mm: 13 };
      return { ok: true, logo: state.logo };
    },
    async set_logo_size(size) { state.logo = { ...state.logo, size }; return { ok: true, logo: state.logo }; },
    async remove_logo() { state.logo = { enabled: false, size: state.logo.size }; return { ok: true, logo: state.logo }; },
    async get_logs(since) { return { total: logs.length, lines: logs.slice(since) }; },
    async clear_logs() { logs.length = 0; return { total: 0 }; },
    async copy_text() { return { ok: true }; },
    async read_clipboard() { return '123e4567-e89b-12d3-a456-426614174000'; },
    async open_panel() { return { ok: true }; },
    async open_logs_folder() { return { ok: true }; },
    async hide_window() { return { ok: true }; },
  };

  // Simula tickets chegando enquanto o painel está aberto.
  setInterval(() => {
    if (state.status !== 'connected' || !state.config.printer_name) return;
    const id = Math.random().toString(16).slice(2, 8);
    state.stats.printed += 1;
    state.stats.last_print_at = now();
    log('INFO', 'printer_service', `Ticket impresso com sucesso (código: A0${state.stats.printed})`);
    const item = { ts: now(), tone: 'success', title: 'Ticket impresso', detail: `Job ${id}` };
    state.activity.unshift(item);
    emit('activity', item);
    emit('stats', state.stats);
  }, 20000);

  window.__mock = { state, setStatus, emit, pstatus };
  window.pywebview = { api };
  setTimeout(() => window.dispatchEvent(new Event('pywebviewready')), 0);
})();
