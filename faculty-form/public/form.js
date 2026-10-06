/* ============================================================
   FACULTY FORM — page logic
   States: sign-in -> (closed | form) -> done.  The server decides everything;
   this file only displays state and sends the student's choice.
   ============================================================ */
(() => {
  const APP = window.APP || {};
  const root = document.getElementById('app');
  const timerEl = document.getElementById('timer');
  const timerText = document.getElementById('timerText');

  let me = null;            // /api/me payload
  let faculty = [];         // latest availability
  let selectedId = null;    // faculty the student ticked
  let expiresMs = 0;        // server-time deadline of the current attempt
  let offset = 0;           // serverNow - Date.now(), so a wrong phone clock can't cheat the timer
  let expired = false;
  let submitting = false;
  let pollTimer = null, tickTimer = null, openTimer = null;


  // ---------- inline icons (no icon-font download needed) ----------
  const ICONS = {
    account_circle: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zM7.07 18.28c.43-.9 3.05-1.78 4.93-1.78s4.51.88 4.93 1.78C15.57 19.36 13.86 20 12 20s-3.57-.64-4.93-1.72zm11.29-1.45c-1.43-1.74-4.9-2.33-6.36-2.33s-4.93.59-6.36 2.33C4.62 15.49 4 13.82 4 12c0-4.41 3.59-8 8-8s8 3.59 8 8c0 1.82-.62 3.49-1.64 4.83zM12 6c-1.94 0-3.5 1.56-3.5 3.5S10.06 13 12 13s3.5-1.56 3.5-3.5S13.94 6 12 6zm0 5c-.83 0-1.5-.67-1.5-1.5S11.17 8 12 8s1.5.67 1.5 1.5S12.83 11 12 11z',
    check_circle: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z',
    error: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z',
    error_outline: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z',
    hourglass_bottom: 'M6 2v6h.01L6 8.01 10 12l-4 4 .01.01H6V22h12v-5.99h-.01L18 16l-4-4 4-3.99-.01-.01H18V2H6zm10 14.5V20H8v-3.5l4-4 4 4zm-4-5l-4-4V4h8v3.5l-4 4z',
  };
  const ico = (name) => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[name] || ICONS.error}"/></svg>`;

  // ---------- helpers ----------
  const esc = (s) => { const d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; };
  const $ = (sel) => root.querySelector(sel);
  const serverNow = () => Date.now() + offset;

  async function api(method, path, body) {
    try {
      const res = await fetch(path, {
        method,
        headers: method === 'POST' ? { 'Content-Type': 'application/json' } : {},
        body: method === 'POST' ? JSON.stringify(body || {}) : undefined,
        credentials: 'same-origin',
      });
      let data = {};
      try { data = await res.json(); } catch (_) { /* non-JSON error page */ }
      return { status: res.status, ok: res.ok && data.ok !== false, data };
    } catch (_) {
      return { status: 0, ok: false, data: { code: 'network', message: 'Network problem. Check your connection and try again.' } };
    }
  }

  let toastTimer;
  function toast(msg) {
    const t = document.getElementById('toast');
    document.getElementById('toastMsg').textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 3500);
  }

  function stopTimers() {
    clearInterval(pollTimer); clearInterval(tickTimer); clearInterval(openTimer);
    pollTimer = tickTimer = openTimer = null;
    timerEl.classList.add('hidden');
    timerEl.classList.remove('warn');
  }

  function titleCard({ required = false, extra = '' } = {}) {
    return `
      <div class="title-card">
        <div class="accent"></div>
        <div class="title-body">
          <h1>${esc(APP.title)}</h1>
          ${APP.description ? `<p class="muted">${esc(APP.description)}</p>` : ''}
          ${extra}
          ${required ? '<p class="required-note">* Indicates required question</p>' : ''}
        </div>
        ${me && me.signed_in ? accountBar() : ''}
      </div>`;
  }

  function accountBar() {
    return `
      <div class="account-bar">
        ${ico('account_circle')}
        <div class="who"><b>${esc(me.email)}</b><small>Your email will be recorded when you submit this form.</small></div>
        <button class="link-btn" id="switchBtn" type="button">Switch account</button>
      </div>`;
  }

  function bindSwitch() {
    const b = $('#switchBtn');
    if (!b) return;
    b.addEventListener('click', async () => {
      stopTimers();
      await api('POST', '/api/logout');
      try { window.google && google.accounts.id.disableAutoSelect(); } catch (_) {}
      boot();
    });
  }

  function fatal(message) {
    stopTimers();
    root.innerHTML = titleCard() + `<div class="banner">${ico('error')}<div>${esc(message)}</div></div>
      <div class="submit-area"><button class="btn-text" id="retryBtn" type="button">Try again</button></div>`;
    bindSwitch();
    $('#retryBtn').addEventListener('click', boot);
  }

  // ---------- boot ----------
  async function boot() {
    stopTimers();
    expired = false; submitting = false; selectedId = null;
    const r = await api('GET', '/api/me');
    if (!r.ok) return fatal(r.data.message || 'Could not load the form. Please refresh.');
    me = r.data;
    offset = me.server_now - Date.now();
    if (!me.signed_in) return showSignin();
    if (me.selection) return showDone(me.selection, false);
    if (!me.is_open) return showClosed();
    return showForm();
  }

  // ---------- sign in ----------
  function showSignin(error) {
    stopTimers();
    root.innerHTML = titleCard() + `
      <div class="card">
        <div class="q-title">Sign in to continue</div>
        <div class="signin-box">
          <div id="gbtn"></div>
          <div class="hint">Use your college Google account (<b>name.mb25@${esc(APP.domain)}</b>).
            Your selection is saved against the account you sign in with.</div>
          <div class="banner ${error ? '' : 'hidden'}" id="signinError">${ico('error')}<div id="signinErrorText">${esc(error || '')}</div></div>
          ${APP.devLogin ? `
          <div class="dev-box">
            <div class="hint">Local testing only (DEV_LOGIN is on)</div>
            <input class="text-input" id="devEmail" placeholder="student email" />
            <button class="btn-text" id="devBtn" type="button">Dev sign in</button>
          </div>` : ''}
        </div>
      </div>`;

    if (APP.devLogin) {
      $('#devBtn').addEventListener('click', async () => {
        const r = await api('POST', '/api/dev-login', { email: $('#devEmail').value });
        r.ok ? boot() : signinError(r.data.message);
      });
    }
    if (!APP.clientId) {
      signinError('Google Sign-In is not set up yet (GOOGLE_CLIENT_ID is missing on the server).');
      return;
    }
    let tries = 0;
    const wait = setInterval(() => {
      if (window.google && google.accounts && google.accounts.id) {
        clearInterval(wait);
        google.accounts.id.initialize({ client_id: APP.clientId, callback: onCredential, auto_select: false });
        const w = Math.min(300, Math.max(220, root.clientWidth - 80));
        google.accounts.id.renderButton($('#gbtn'), { theme: 'outline', size: 'large', text: 'signin_with', shape: 'rectangular', width: w });
      } else if (++tries > 100) {
        clearInterval(wait);
        signinError('Could not load Google Sign-In. Check your connection and refresh.');
      }
    }, 100);
  }

  function signinError(msg) {
    const box = $('#signinError');
    if (!box) return;
    $('#signinErrorText').textContent = msg || 'Sign-in failed.';
    box.classList.remove('hidden');
  }

  async function onCredential(resp) {
    const r = await api('POST', '/api/auth/google', { credential: resp.credential });
    if (r.ok) return boot();
    signinError(r.data.message || 'Sign-in failed. Please try again.');
  }

  // ---------- closed / not yet open ----------
  function showClosed() {
    stopTimers();
    const notYet = me.reason === 'not_open';
    root.innerHTML = titleCard() + `
      <div class="card">
        <div class="q-title">${notYet ? 'This form is not open yet' : 'This form is closed'}</div>
        ${notYet ? `<div>Opens at <b>${esc(me.opens_at)} IST</b></div><div class="big-clock" id="countdown"></div>
        <div class="hint" style="color:#5f6368">Keep this page open. The form starts automatically.</div>` :
        '<div>It is no longer accepting responses.</div>'}
      </div>`;
    bindSwitch();
    if (!notYet) return;
    const tick = () => {
      const s = Math.max(0, Math.round((me.opens_at_ms - serverNow()) / 1000));
      const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
      const el = $('#countdown');
      if (el) el.textContent = (h ? h + 'h ' : '') + (h || m ? m + 'm ' : '') + sec + 's';
    };
    tick();
    tickTimer = setInterval(tick, 500);
    openTimer = setInterval(async () => {
      if (serverNow() < me.opens_at_ms - 1500) return;       // don't poll the server until it's nearly time
      const r = await api('GET', '/api/me');
      if (r.ok && r.data.is_open) { clearInterval(openTimer); boot(); }
    }, 1000);
  }

  // ---------- the form ----------
  async function showForm() {
    stopTimers();
    const [av, st] = await Promise.all([api('GET', '/api/availability'), api('POST', '/api/start')]);
    if (!st.ok) return handleStartError(st);
    if (!av.ok) return fatal(av.data.message || 'Could not load faculty availability.');
    faculty = av.data.faculty;
    beginAttempt(st.data);

    const strict = me.register_no != null;
    const regCard = strict
      ? `<input class="text-input" value="${esc(me.register_no)}" readonly />`
      : `<select class="text-input" id="regSelect"><option value="">Choose</option>
           ${(me.roster || []).map(r => `<option value="${esc(r.register_no)}">${esc(r.register_no)} - ${esc(r.name)}</option>`).join('')}
         </select>`;

    root.innerHTML = titleCard({ required: true }) + `
      <div id="formBanner"></div>
      <div class="card"><div class="q-title">Email <span class="req">*</span></div>
        <input class="text-input" value="${esc(me.email)}" readonly /></div>
      <div class="card"><div class="q-title">Name <span class="req">*</span></div>
        <input class="text-input" id="nameField" value="${strict ? esc(me.name) : ''}" placeholder="${strict ? '' : 'Filled in from your register number'}" readonly /></div>
      <div class="card" id="regCard"><div class="q-title">Register Number <span class="req">*</span></div>
        ${regCard}
        <div class="q-error">${ico('error_outline')}This is a required question</div></div>
      <div class="card" id="facCard"><div class="q-title">Select your faculty <span class="req">*</span></div>
        <div class="options" id="options" role="radiogroup" aria-label="Faculty"></div>
        <div class="q-error">${ico('error_outline')}<span id="facErrorText">This is a required question</span></div></div>
      <div class="submit-area">
        <button class="btn-primary" id="submitBtn" type="button">Submit</button>
        <button class="btn-text" id="clearBtn" type="button">Clear form</button>
      </div>
      <div class="form-note">Seats update live. Once a faculty is full it can't be selected. You can't change your choice after submitting.</div>`;

    bindSwitch();
    renderOptions();
    $('#submitBtn').addEventListener('click', submit);
    $('#clearBtn').addEventListener('click', clearForm);
    const regSel = $('#regSelect');
    if (regSel) regSel.addEventListener('change', () => {
      const hit = (me.roster || []).find(r => r.register_no === regSel.value);
      $('#nameField').value = hit ? hit.name : '';
      markError('regCard', false);
    });
    pollTimer = setInterval(refreshAvailability, 3000);
  }

  function handleStartError(st) {
    const d = st.data || {};
    if (st.status === 401) return showSignin(d.message);
    if (d.code === 'already_submitted' && d.selection) return showDone(d.selection, true);
    if (d.code === 'not_open' || d.code === 'closed') {
      me.is_open = false; me.reason = d.code; me.opens_at_ms = d.opens_at_ms || me.opens_at_ms;
      return showClosed();
    }
    return fatal(d.message || 'Could not start the form.');
  }

  function beginAttempt(d) {
    offset = d.server_now - Date.now();
    expiresMs = d.expires_ms;
    expired = false;
    timerEl.classList.remove('hidden');
    clearInterval(tickTimer);
    tickTimer = setInterval(tick, 250);
    tick();
  }

  function tick() {
    const left = Math.max(0, Math.ceil((expiresMs - serverNow()) / 1000));
    timerText.textContent = Math.floor(left / 60) + ':' + String(left % 60).padStart(2, '0');
    timerEl.classList.toggle('warn', left <= 10);
    if (left <= 0 && !expired) onExpired();
  }

  function setLocked(locked) {
    root.querySelectorAll('#options input, #regSelect, #submitBtn, #clearBtn').forEach(el => { el.disabled = locked; });
    if (!locked) updateOptions();            // full faculty stay disabled even when the form unlocks
  }

  function onExpired() {
    expired = true;
    clearInterval(tickTimer);
    setLocked(true);
    const b = $('#formBanner');
    if (!b) return;
    b.innerHTML = `<div class="banner">${ico('hourglass_bottom')}
      <div>Time's up. The 1-minute limit has passed, so this attempt can't be submitted.</div>
      <button class="link-btn banner-action" id="restartBtn" type="button">Start again</button></div>`;
    $('#restartBtn').addEventListener('click', restart);
  }

  async function restart() {
    const r = await api('POST', '/api/start');
    if (!r.ok) return handleStartError(r);
    const b = $('#formBanner'); if (b) b.innerHTML = '';
    beginAttempt(r.data);
    setLocked(false);
    refreshAvailability();
  }

  // ---------- faculty options ----------
  function renderOptions() {
    const box = $('#options');
    box.innerHTML = faculty.map(f => `
      <label class="option" data-id="${f.id}">
        <input type="radio" name="faculty" value="${f.id}" />
        <span class="radio"></span>
        <span class="name">${esc(f.name)}</span>
        <span class="seats"></span>
      </label>`).join('');
    box.addEventListener('change', (e) => {
      if (e.target.name === 'faculty') { selectedId = Number(e.target.value); markError('facCard', false); }
    });
    updateOptions();
  }

  function updateOptions() {
    let lostChoice = null;
    faculty.forEach(f => {
      const row = root.querySelector(`.option[data-id="${f.id}"]`);
      if (!row) return;
      const full = f.remaining <= 0;
      const input = row.querySelector('input');
      const seats = row.querySelector('.seats');
      row.classList.toggle('disabled', full);
      input.disabled = full || expired || submitting;
      seats.textContent = full ? 'Full' : f.remaining + (f.remaining === 1 ? ' seat left' : ' seats left');
      seats.classList.toggle('low', !full && f.remaining <= 2);
      if (full && selectedId === f.id) { lostChoice = f; }
    });
    if (lostChoice) {
      selectedId = null;
      root.querySelectorAll('#options input').forEach(i => { i.checked = false; });
      markError('facCard', true, `${lostChoice.name} just filled up. Please choose another.`);
    }
  }

  async function refreshAvailability() {
    if (submitting || !$('#options')) return;
    const r = await api('GET', '/api/availability');
    if (r.ok) { faculty = r.data.faculty; updateOptions(); }
  }

  function markError(cardId, on, msg) {
    const card = $('#' + cardId);
    if (!card) return;
    card.classList.toggle('has-error', on);
    if (on && msg) { const t = card.querySelector('.q-error span:last-child'); if (t) t.textContent = msg; }
  }

  function clearForm() {
    selectedId = null;
    root.querySelectorAll('#options input').forEach(i => { i.checked = false; });
    const reg = $('#regSelect'); if (reg) { reg.value = ''; $('#nameField').value = ''; }
    markError('facCard', false); markError('regCard', false);
  }

  // ---------- submit ----------
  async function submit() {
    if (submitting || expired) return;
    const reg = $('#regSelect');
    let bad = false;
    if (reg && !reg.value) { markError('regCard', true, 'This is a required question'); bad = true; }
    if (!selectedId) { markError('facCard', true, 'This is a required question'); bad = true; }
    if (bad) return;

    submitting = true;
    const btn = $('#submitBtn');
    btn.disabled = true; btn.textContent = 'Submitting…';
    setLocked(true); btn.disabled = true;

    const r = await api('POST', '/api/submit', { faculty_id: selectedId, register_no: reg ? reg.value : undefined });
    submitting = false;
    const d = r.data || {};
    if (r.ok) return showDone(d.selection, d.already);

    // failed: unlock (unless the timer ran out meanwhile) and explain
    btn.textContent = 'Submit';
    if (d.code === 'already_submitted' && d.selection) return showDone(d.selection, true);
    if (r.status === 401) return showSignin('Your session ended. Please sign in again.');
    if (d.code === 'not_open' || d.code === 'closed') { me.is_open = false; me.reason = d.code; return showClosed(); }
    if (d.code === 'timer_expired') { setLocked(false); onExpired(); return; }
    if (d.code === 'faculty_full') {
      if (d.faculty) faculty = d.faculty;
      selectedId = null;
      root.querySelectorAll('#options input').forEach(i => { i.checked = false; });
      setLocked(expired); btn.disabled = expired;
      updateOptions();
      markError('facCard', true, d.message);
      toast(d.message);
      return;
    }
    setLocked(expired); btn.disabled = expired;
    updateOptions();
    const msg = d.message || 'Something went wrong. Please try again.';
    toast(msg);
    const b = $('#formBanner');
    if (b) b.innerHTML = `<div class="banner">${ico('error')}<div>${esc(msg)}</div></div>`;
  }

  // ---------- confirmation ----------
  function showDone(sel, already) {
    stopTimers();
    me.selection = sel;
    root.innerHTML = `
      <div class="title-card">
        <div class="accent"></div>
        <div class="title-body">
          <h1>${esc(APP.title)}</h1>
          <p class="done-note">Your response has been recorded.</p>
        </div>
        ${accountBar()}
      </div>
      <div class="card">
        <div class="done-tick">${ico('check_circle')}${already ? 'You have already submitted' : 'Selection confirmed'}</div>
        <div class="detail-row"><div class="k">Faculty</div><div class="v"><b>${esc(sel.faculty)}</b></div></div>
        <div class="detail-row"><div class="k">Name</div><div class="v">${esc(sel.name)}</div></div>
        <div class="detail-row"><div class="k">Register number</div><div class="v">${esc(sel.register_no)}</div></div>
        <div class="detail-row"><div class="k">Submitted at</div><div class="v">${esc(sel.time)} IST</div></div>
        <div class="detail-row"><div class="k">Response no.</div><div class="v">#${esc(sel.seq)}</div></div>
      </div>
      <div class="form-note">Selections can't be changed. Contact your coordinator if something is wrong.</div>`;
    bindSwitch();
  }

  boot();
})();
