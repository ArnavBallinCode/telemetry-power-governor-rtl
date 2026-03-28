const connDot = document.getElementById('connDot');
const connText = document.getElementById('connText');
const ack = document.getElementById('ack');
const themeToggle = document.getElementById('themeToggle');
const themeIcon = document.getElementById('themeIcon');

const fields = {
  stateA: document.getElementById('stateA'),
  stateB: document.getElementById('stateB'),
  grantA: document.getElementById('grantA'),
  grantB: document.getElementById('grantB'),
  clkEnA: document.getElementById('clkEnA'),
  clkEnB: document.getElementById('clkEnB'),
  eff: document.getElementById('eff'),
  budget: document.getElementById('budget'),
  headroom: document.getElementById('headroom'),
  frame: document.getElementById('frame'),
  tempA: document.getElementById('tempA'),
  tempB: document.getElementById('tempB'),
  actA: document.getElementById('actA'),
  actB: document.getElementById('actB'),
  stallA: document.getElementById('stallA'),
  stallB: document.getElementById('stallB'),
  reqA: document.getElementById('reqA'),
  reqB: document.getElementById('reqB'),
  phase: document.getElementById('phase'),
  mode: document.getElementById('mode'),
  alarmA: document.getElementById('alarmA'),
  alarmB: document.getElementById('alarmB'),
  eff2: document.getElementById('eff2'),
  budget2: document.getElementById('budget2'),
  headroom2: document.getElementById('headroom2'),
};

const stateNames = ['SLEEP', 'LOW_POWER', 'ACTIVE', 'TURBO'];

function decodeState(v) {
  return stateNames[v] || `S${v}`;
}

function stateFromGrant(grant) {
  return decodeState(grant);
}

const stateClassMap = { SLEEP: 'sleep', LOW_POWER: 'low', ACTIVE: 'active', TURBO: 'turbo' };

const chartCtx = document.getElementById('trendChart');
const trendChart = new Chart(chartCtx, {
  type: 'line',
  data: {
    labels: [],
    datasets: [
      { label: 'Efficiency', data: [], borderColor: '#00c9a7', tension: 0.22 },
      { label: 'Temp A', data: [], borderColor: '#ffa94d', tension: 0.22 },
      { label: 'Temp B', data: [], borderColor: '#ff6f61', tension: 0.22 },
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: { ticks: { color: '#8fb0bd' }, grid: { color: 'rgba(255,255,255,0.07)' } },
      y: { ticks: { color: '#8fb0bd' }, grid: { color: 'rgba(255,255,255,0.07)' } },
    },
    plugins: {
      legend: { labels: { color: '#cfe5ee' } }
    }
  }
});

// apply simple gradient fills for a more modern look
try {
  const ctx = chartCtx.getContext('2d');
  const g0 = ctx.createLinearGradient(0, 0, 0, 300);
  g0.addColorStop(0, 'rgba(0,201,167,0.26)');
  g0.addColorStop(1, 'rgba(0,201,167,0.02)');
  const g1 = ctx.createLinearGradient(0, 0, 0, 300);
  g1.addColorStop(0, 'rgba(255,169,77,0.20)');
  g1.addColorStop(1, 'rgba(255,169,77,0.02)');
  const g2 = ctx.createLinearGradient(0, 0, 0, 300);
  g2.addColorStop(0, 'rgba(255,111,97,0.18)');
  g2.addColorStop(1, 'rgba(255,111,97,0.02)');
  trendChart.data.datasets[0].backgroundColor = g0;
  trendChart.data.datasets[0].borderWidth = 2;
  trendChart.data.datasets[0].fill = true;
  trendChart.data.datasets[1].backgroundColor = g1;
  trendChart.data.datasets[1].borderWidth = 2;
  trendChart.data.datasets[1].fill = true;
  trendChart.data.datasets[2].backgroundColor = g2;
  trendChart.data.datasets[2].borderWidth = 2;
  trendChart.data.datasets[2].fill = true;
  trendChart.update();
} catch (e) {
  // ignore if gradients fail
}

function pushPoint(state) {
  const t = new Date().toLocaleTimeString();
  const labels = trendChart.data.labels;
  labels.push(t);
  trendChart.data.datasets[0].data.push(state.efficiency || 0);
  trendChart.data.datasets[1].data.push(state.temp_a || 0);
  trendChart.data.datasets[2].data.push(state.temp_b || 0);
  while (labels.length > 60) {
    labels.shift();
    trendChart.data.datasets.forEach(ds => ds.data.shift());
  }
  trendChart.update();
}

function updateAlarm(el, on, title) {
  el.classList.toggle('on', !!on);
  el.textContent = `${title}: ${on ? 'ON' : 'OFF'}`;
}

function setConnection(online) {
  connDot.classList.toggle('online', online);
  connDot.classList.toggle('offline', !online);
  connText.textContent = online ? 'Connected' : 'Disconnected';
}

function render(state) {
  setConnection(!!state.connected);

  fields.stateA.textContent = stateFromGrant(state.grant_a || 0);
  fields.stateB.textContent = stateFromGrant(state.grant_b || 0);

  // add nice class to the pill to visually show state
  try {
    const sA = fields.stateA.textContent || 'SLEEP';
    const sB = fields.stateB.textContent || 'SLEEP';
    Object.values(stateClassMap).forEach(c => fields.stateA.classList.remove(c));
    Object.values(stateClassMap).forEach(c => fields.stateB.classList.remove(c));
    fields.stateA.classList.add(stateClassMap[sA] || 'sleep');
    fields.stateB.classList.add(stateClassMap[sB] || 'sleep');
  } catch (e) {}

  fields.grantA.textContent = state.grant_a ?? 0;
  fields.grantB.textContent = state.grant_b ?? 0;
  fields.clkEnA.textContent = state.clk_en_a ?? 0;
  fields.clkEnB.textContent = state.clk_en_b ?? 0;

  fields.eff.textContent = state.efficiency ?? 0;
  fields.budget.textContent = state.current_budget ?? 0;
  fields.headroom.textContent = state.budget_headroom ?? 0;
  // mirror metrics into right column
  if (fields.eff2) fields.eff2.textContent = state.efficiency ?? 0;
  if (fields.budget2) fields.budget2.textContent = state.current_budget ?? 0;
  if (fields.headroom2) fields.headroom2.textContent = state.budget_headroom ?? 0;
  fields.frame.textContent = state.frame_counter ?? 0;

  fields.tempA.textContent = state.temp_a ?? 0;
  fields.tempB.textContent = state.temp_b ?? 0;
  fields.actA.textContent = state.act_a ?? 0;
  fields.actB.textContent = state.act_b ?? 0;
  fields.stallA.textContent = state.stall_a ?? 0;
  fields.stallB.textContent = state.stall_b ?? 0;
  fields.reqA.textContent = state.req_a ?? 0;
  fields.reqB.textContent = state.req_b ?? 0;
  fields.phase.textContent = state.phase ?? 0;
  fields.mode.textContent = state.host_mode ? 'host' : 'internal';

  updateAlarm(fields.alarmA, state.alarm_a, 'Alarm A');
  updateAlarm(fields.alarmB, state.alarm_b, 'Alarm B');

  // populate control form values with incoming telemetry (unless user edited the form)
  try { populateControlFormFromState(state); } catch (e) {}

  pushPoint(state);

  // small highlight animation for metrics
  try {
    const els = [fields.eff, fields.budget, fields.headroom];
    els.forEach(el => { if (!el) return; el.animate([{ transform: 'translateY(-6px)' }, { transform: 'translateY(0)' }], { duration: 260, easing: 'cubic-bezier(.2,.9,.2,1)' }); });
  } catch (e) {}
}

/* THEME HANDLING */
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem('pwrgov-theme', t); } catch (e) {}
  if (themeIcon) themeIcon.textContent = t === 'light' ? '☀️' : '🌙';
}

// initialize theme from localStorage or system
try {
  const saved = localStorage.getItem('pwrgov-theme');
  const preferLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
  applyTheme(saved || (preferLight ? 'light' : 'dark'));
} catch (e) { applyTheme('dark'); }

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const cur = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    applyTheme(cur);
  });
}

/* 3D tilt for cards */
function initTilt() {
  const cards = document.querySelectorAll('.card');
  cards.forEach(card => {
    let raf = null;
    let last = null;

    function onFrame() {
      if (!last) { raf = null; return; }
      const e = last; last = null; raf = null;
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const px = (x / rect.width) - 0.5;
      const py = (y / rect.height) - 0.5;
      const rotY = (px * 18).toFixed(2);
      const rotX = (-py * 10).toFixed(2);
      const s = 1.02;
      card.style.transform = `perspective(900px) rotateX(${rotX}deg) rotateY(${rotY}deg) scale(${s})`;
      card.style.boxShadow = `${-rotY/2}px ${rotX/2}px 34px rgba(6,20,26,0.48), 0 12px 40px rgba(2,6,10,0.35)`;
    }

    card.addEventListener('pointermove', (ev) => { last = ev; if (!raf) raf = requestAnimationFrame(onFrame); }, { passive: true });
    card.addEventListener('pointerleave', () => { if (raf) { cancelAnimationFrame(raf); raf = null; } card.style.transform = ''; card.style.boxShadow = ''; });
  });
}

// small staggered entrance
function entranceAnimate() {
  const cards = Array.from(document.querySelectorAll('.card'));
  cards.forEach((c, i) => { c.style.opacity = 0; c.style.transform += ' translateY(8px)'; setTimeout(()=>{ c.style.transition = 'opacity .45s ease, transform .55s cubic-bezier(.2,.9,.2,1)'; c.style.opacity = 1; c.style.transform = c.style.transform.replace(' translateY(8px)',''); }, 60 * i); });
}

let ws;
function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    setConnection(true);
  };

  ws.onmessage = (ev) => {
    try {
      const state = JSON.parse(ev.data);
      render(state);
    } catch (e) {
      console.error(e);
    }
  };

  ws.onclose = () => {
    setConnection(false);
    setTimeout(connectWs, 1500);
  };
}

async function pollFallback() {
  try {
    const res = await fetch('/api/state');
    if (res.ok) {
      const state = await res.json();
      setConnection(true);
      render(state);
    }
  } catch (_e) {
    setConnection(false);
  }
}

setInterval(() => {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    pollFallback();
  }
}, 1200);

const form = document.getElementById('ctrlForm');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const submitBtn = form.querySelector('button[type="submit"]');
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Sending...'; }
  const payload = {
    mode: document.getElementById('modeSelect').value,
    host_use_ext_budget: document.getElementById('extBudgetSelect').value === 'true',
    budget: Number(document.getElementById('budgetInput').value),
    req_a: Number(document.getElementById('reqAInput').value),
    req_b: Number(document.getElementById('reqBInput').value),
    temp_a: Number(document.getElementById('tempAInput').value),
    temp_b: Number(document.getElementById('tempBInput').value),
    act_a: document.getElementById('actAToggle').checked,
    stall_a: document.getElementById('stallAToggle').checked,
    act_b: document.getElementById('actBToggle').checked,
    stall_b: document.getElementById('stallBToggle').checked,
  };

  try {
    const res = await fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const out = await res.json();
    ack.textContent = JSON.stringify(out, null, 2);
  } catch (err) {
    ack.textContent = `control send failed: ${err}`;
  }
  if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Send Control Command'; }
});

connectWs();
pollFallback();
initTilt();
entranceAnimate();
// NAV / VIEW handling
const navBtns = document.querySelectorAll('.nav-btn');
const leftCol = document.querySelector('.left-col');
const rightCol = document.querySelector('.right-col');
function showView(v) {
  navBtns.forEach(b => b.classList.toggle('active', b.dataset.view === v));
  if (v === 'dashboard') {
    if (leftCol) leftCol.style.display = '';
    if (rightCol) rightCol.style.display = '';
  } else if (v === 'telemetry') {
    if (leftCol) leftCol.style.display = '';
    if (rightCol) rightCol.style.display = 'none';
  } else if (v === 'controls') {
    if (leftCol) leftCol.style.display = 'none';
    if (rightCol) rightCol.style.display = '';
  }
}
navBtns.forEach(b => { b.addEventListener('click', (e)=>{ const v = b.dataset.view || 'dashboard'; showView(v); }); });
// default
showView('dashboard');

// reconnect on click of connection dot
connDot && connDot.addEventListener('click', () => {
  try {
    if (ws && ws.readyState === WebSocket.OPEN) { ws.close(); setTimeout(connectWs, 400); }
    else connectWs();
  } catch (e) { connectWs(); }
});

// form dirty tracking - avoid clobbering user edits
let formDirty = false;
const ctrlIds = ['modeSelect','extBudgetSelect','budgetInput','reqAInput','reqBInput','tempAInput','tempBInput','actAToggle','stallAToggle','actBToggle','stallBToggle'];
ctrlIds.forEach(id => {
  const el = document.getElementById(id);
  if (!el) return;
  el.addEventListener('input', ()=> { formDirty = true; });
  el.addEventListener('change', ()=> { formDirty = true; });
});

// helper to populate control form from state (if not dirty)
function populateControlFormFromState(state) {
  if (formDirty) return;
  try {
    const modeEl = document.getElementById('modeSelect');
    if (modeEl) modeEl.value = state.host_mode ? 'host' : 'internal';
    const budgetEl = document.getElementById('budgetInput');
    if (budgetEl) budgetEl.value = state.current_budget ?? budgetEl.value;
    const reqAEl = document.getElementById('reqAInput');
    if (reqAEl) reqAEl.value = state.req_a ?? reqAEl.value;
    const reqBEl = document.getElementById('reqBInput');
    if (reqBEl) reqBEl.value = state.req_b ?? reqBEl.value;
    const tempAEl = document.getElementById('tempAInput');
    if (tempAEl) tempAEl.value = state.temp_a ?? tempAEl.value;
    const tempBEl = document.getElementById('tempBInput');
    if (tempBEl) tempBEl.value = state.temp_b ?? tempBEl.value;
    const actAEl = document.getElementById('actAToggle');
    if (actAEl) actAEl.checked = !!state.act_a;
    const stallAEl = document.getElementById('stallAToggle');
    if (stallAEl) stallAEl.checked = !!state.stall_a;
    const actBEl = document.getElementById('actBToggle');
    if (actBEl) actBEl.checked = !!state.act_b;
    const stallBEl = document.getElementById('stallBToggle');
    if (stallBEl) stallBEl.checked = !!state.stall_b;
    // extBudgetSelect may not be present in state; skip
  } catch (e) {}
}

// expose a small reset-dirty button on double-click of the controls area
const controlsCard = document.querySelector('.controls-card');
if (controlsCard) {
  controlsCard.addEventListener('dblclick', () => { formDirty = false; controlsCard.animate([{ transform: 'scale(1.02)' }, { transform: 'scale(1)' }], { duration: 200 }); });
}

// Helper to POST control payloads and update UI/ack
async function sendControlPayload(payload) {
  const submitBtn = form.querySelector('button[type="submit"]');
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Sending...'; }
  try {
    // demo mode: simulate locally
    if (window.demoMode) {
      // update demoState from payload
      try {
        Object.keys(payload).forEach(k => {
          const v = payload[k];
          if (k === 'mode') demoState.host_mode = (v === 'host') ? 1 : 0;
          else if (k === 'host_use_ext_budget') demoState.use_ext_budget = !!v;
          else if (k === 'budget') demoState.current_budget = Number(v);
          else if (k === 'req_a') demoState.req_a = Number(v);
          else if (k === 'req_b') demoState.req_b = Number(v);
          else if (k === 'temp_a') demoState.temp_a = Number(v);
          else if (k === 'temp_b') demoState.temp_b = Number(v);
          else if (k === 'act_a') demoState.act_a = v ? 1 : 0;
          else if (k === 'act_b') demoState.act_b = v ? 1 : 0;
          else if (k === 'stall_a') demoState.stall_a = v ? 1 : 0;
          else if (k === 'stall_b') demoState.stall_b = v ? 1 : 0;
        });
      } catch (e) {}
      demoState.frame_counter = (demoState.frame_counter || 0) + 1;
      render(demoState);
      const out = { ok: true, sent: Object.keys(payload).length };
      ack.textContent = JSON.stringify(out, null, 2);
      formDirty = false;
      return out;
    }

    const res = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const out = await res.json();
    ack.textContent = JSON.stringify(out, null, 2);
    // refresh state snapshot
    try {
      const s = await fetch('/api/state');
      if (s.ok) {
        const st = await s.json();
        render(st);
      }
    } catch (e) {}
    formDirty = false;
    return out;
  } catch (err) {
    ack.textContent = `control send failed: ${err}`;
    throw err;
  } finally {
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Send Control Command'; }
  }
}

// Demo mode client-side telemetry generator
window.demoMode = false;
let demoTimer = null;
let demoState = null;
function startDemo() {
  window.demoMode = true;
  demoState = {
    ts: Date.now()/1000, connected: true, frame_counter: 0, host_mode: 0,
    alarm_a:0, alarm_b:0, clk_en_a:1, clk_en_b:1, grant_a:0, grant_b:0,
    current_budget:4, budget_headroom:3, efficiency:0, temp_a:30, temp_b:30,
    act_a:0, stall_a:0, act_b:0, stall_b:0, req_a:0, req_b:0, phase:0
  };
  if (connDot) connDot.classList.add('online');
  if (connText) connText.textContent = 'Demo';
  demoTimer = setInterval(()=>{
    demoState.frame_counter += 1;
    demoState.efficiency = Math.round( (Math.sin(demoState.frame_counter/6) + 1) * 50 );
    demoState.temp_a = clamp(30 + Math.round(6*Math.sin(demoState.frame_counter/8)), 20, 80);
    demoState.temp_b = clamp(30 + Math.round(6*Math.cos(demoState.frame_counter/10)), 20, 80);
    // toggle random activity
    demoState.act_a = (demoState.frame_counter % 7 < 4) ? 1 : 0;
    demoState.act_b = (demoState.frame_counter % 11 < 6) ? 1 : 0;
    demoState.grant_a = demoState.act_a ? 2 : 0;
    demoState.grant_b = demoState.act_b ? 1 : 0;
    render(demoState);
  }, 600);
}

function stopDemo() {
  window.demoMode = false;
  if (demoTimer) { clearInterval(demoTimer); demoTimer = null; }
  if (connDot) connDot.classList.remove('online');
  if (connText) connText.textContent = 'Disconnected';
}

// Demo toggle binding
const demoToggle = el('demoToggle');
if (demoToggle) {
  demoToggle.addEventListener('change', (e)=>{
    if (e.target.checked) startDemo(); else stopDemo();
  });
}

// Quick-action bindings
function el(id) { return document.getElementById(id); }

el('btnToggleMode') && el('btnToggleMode').addEventListener('click', async () => {
  const modeEl = el('modeSelect'); if (!modeEl) return;
  const next = modeEl.value === 'internal' ? 'host' : 'internal'; modeEl.value = next; await sendControlPayload({ mode: next });
});

el('btnToggleExtBudget') && el('btnToggleExtBudget').addEventListener('click', async () => {
  const e = el('extBudgetSelect'); if (!e) return; const next = e.value === 'true' ? false : true; e.value = next ? 'true' : 'false'; await sendControlPayload({ host_use_ext_budget: next });
});

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

el('btnReqAPlus') && el('btnReqAPlus').addEventListener('click', async () => { const inp = el('reqAInput'); if (!inp) return; const v = clamp(Number(inp.value || 0) + 1, 0, 3); inp.value = v; await sendControlPayload({ req_a: v }); });
el('btnReqAMinus') && el('btnReqAMinus').addEventListener('click', async () => { const inp = el('reqAInput'); if (!inp) return; const v = clamp(Number(inp.value || 0) - 1, 0, 3); inp.value = v; await sendControlPayload({ req_a: v }); });
el('btnReqBPlus') && el('btnReqBPlus').addEventListener('click', async () => { const inp = el('reqBInput'); if (!inp) return; const v = clamp(Number(inp.value || 0) + 1, 0, 3); inp.value = v; await sendControlPayload({ req_b: v }); });
el('btnReqBMinus') && el('btnReqBMinus').addEventListener('click', async () => { const inp = el('reqBInput'); if (!inp) return; const v = clamp(Number(inp.value || 0) - 1, 0, 3); inp.value = v; await sendControlPayload({ req_b: v }); });

el('btnBudgetPlus') && el('btnBudgetPlus').addEventListener('click', async () => { const inp = el('budgetInput'); if (!inp) return; const v = clamp(Number(inp.value || 0) + 1, 0, 7); inp.value = v; await sendControlPayload({ budget: v }); });
el('btnBudgetMinus') && el('btnBudgetMinus').addEventListener('click', async () => { const inp = el('budgetInput'); if (!inp) return; const v = clamp(Number(inp.value || 0) - 1, 0, 7); inp.value = v; await sendControlPayload({ budget: v }); });

el('btnTempAPlus') && el('btnTempAPlus').addEventListener('click', async () => { const inp = el('tempAInput'); if (!inp) return; const v = clamp(Number(inp.value || 0) + 1, 0, 127); inp.value = v; await sendControlPayload({ temp_a: v }); });
el('btnTempAMinus') && el('btnTempAMinus').addEventListener('click', async () => { const inp = el('tempAInput'); if (!inp) return; const v = clamp(Number(inp.value || 0) - 1, 0, 127); inp.value = v; await sendControlPayload({ temp_a: v }); });
el('btnTempBPlus') && el('btnTempBPlus').addEventListener('click', async () => { const inp = el('tempBInput'); if (!inp) return; const v = clamp(Number(inp.value || 0) + 1, 0, 127); inp.value = v; await sendControlPayload({ temp_b: v }); });
el('btnTempBMinus') && el('btnTempBMinus').addEventListener('click', async () => { const inp = el('tempBInput'); if (!inp) return; const v = clamp(Number(inp.value || 0) - 1, 0, 127); inp.value = v; await sendControlPayload({ temp_b: v }); });

el('btnSyncState') && el('btnSyncState').addEventListener('click', async () => { try { const res = await fetch('/api/state'); if (res.ok) { const st = await res.json(); render(st); ack.textContent = 'State synced'; } } catch (e) { ack.textContent = `sync failed: ${e}`; } });

el('btnResetDirty') && el('btnResetDirty').addEventListener('click', () => { formDirty = false; ack.textContent = 'Form unlocked'; });
