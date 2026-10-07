/* ============================================================
   FACULTY FORM — High-Performance Client Logic
   - Responsive respondent form for students (atomic FCFS)
   - Real-time Faculty Portal with student allocation table
   - Google Forms-style Preview Mode (Select Students & Test Mode)
   - ETag conditional polling & zero-flicker transitions
   ============================================================ */
(() => {
  const APP = window.APP || {};
  const root = document.getElementById('app');
  const timerEl = document.getElementById('timer');
  const timerText = document.getElementById('timerText');

  let me = null;            // user session & state
  let faculty = [];         // latest availability
  let selectedId = null;    // faculty the student ticked
  let expiresMs = 0;        // server-time deadline of the current attempt
  let offset = 0;           // serverNow - Date.now()
  let submitting = false;
  let pollTimer = null, tickTimer = null, openTimer = null;
  let currentEtag = '';

  // ---------- inline icons ----------
  const ICONS = {
    account_circle: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zM7.07 18.28c.43-.9 3.05-1.78 4.93-1.78s4.51.88 4.93 1.78C15.57 19.36 13.86 20 12 20s-3.57-.64-4.93-1.72zm11.29-1.45c-1.43-1.74-4.9-2.33-6.36-2.33s-4.93.59-6.36 2.33C4.62 15.49 4 13.82 4 12c0-4.41 3.59-8 8-8s8 3.59 8 8c0 1.82-.62 3.49-1.64 4.83zM12 6c-1.94 0-3.5 1.56-3.5 3.5S10.06 13 12 13s3.5-1.56 3.5-3.5S13.94 6 12 6zm0 5c-.83 0-1.5-.67-1.5-1.5S11.17 8 12 8s1.5.67 1.5 1.5S12.83 11 12 11z',
    check_circle: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z',
    error: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z',
    error_outline: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z',
    hourglass_bottom: 'M6 2v6h.01L6 8.01 10 12l-4 4 .01.01H6V22h12v-5.99h-.01L18 16l-4-4 4-3.99-.01-.01H18V2H6zm10 14.5V20H8v-3.5l4-4 4 4zm-4-5l-4-4V4h8v3.5l-4 4z',
    search: 'M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z',
    preview: 'M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z',
    arrow_back: 'M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z',
    science: 'M19 19.5v-.5l-4.5-6V5h.5c.55 0 1-.45 1-1s-.45-1-1-1H9c-.55 0-1 .45-1 1s.45 1 1 1h.5v8L5 19v.5c0 .83.67 1.5 1.5 1.5h11c.83 0 1.5-.67 1.5-1.5z',
    list_alt: 'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z',
    refresh: 'M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z',
    delete: 'M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z',
  };
  const ico = (name) => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[name] || ICONS.error}"/></svg>`;

  // ---------- helpers ----------
  const esc = (s) => { const d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; };
  const $ = (sel) => root.querySelector(sel);
  const serverNow = () => Date.now() + offset;

  async function api(method, path, body, extraHeaders = {}) {
    try {
      const headers = { ...extraHeaders };
      if (method === 'POST') headers['Content-Type'] = 'application/json';
      const res = await fetch(path, {
        method,
        headers,
        body: method === 'POST' ? JSON.stringify(body || {}) : undefined,
        credentials: 'same-origin',
      });
      if (res.status === 304) {
        return { status: 304, ok: true, notModified: true, data: {} };
      }
      let data = {};
      try { data = await res.json(); } catch (_) { /* non-JSON response */ }
      const etag = (res.headers && typeof res.headers.get === 'function') ? (res.headers.get('ETag') || '') : '';
      return { status: res.status, ok: res.ok && data.ok !== false, data, etag };
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
    if (timerEl) {
      timerEl.classList.add('hidden');
      timerEl.classList.remove('warn');
    }
  }

  function titleCard({ required = false, extra = '', title = APP.title, subtitle = APP.description } = {}) {
    return `
      <div class="title-card">
        <div class="accent"></div>
        <div class="title-body">
          <h1>${esc(title)}</h1>
          ${subtitle ? `<p class="muted">${esc(subtitle)}</p>` : ''}
          ${extra}
          ${required ? '<p class="required-note">* Indicates required question</p>' : ''}
        </div>
        ${me && me.signed_in ? accountBar() : ''}
      </div>`;
  }

  function accountBar() {
    const isDirector = me && me.role === 'director';
    const isFac = me && me.role === 'faculty';
    const isAdmin = me && Boolean(me.is_admin);

    let subtitle = ' · Responses recorded to class roster';
    if (isDirector) subtitle = ' · Director Portal';
    else if (isFac) subtitle = ' · Faculty Portal' + (isAdmin ? ' (Coordinator)' : '');
    else if (isAdmin) subtitle = ' · Administrator';

    return `
      <div class="account-bar">
        ${ico('account_circle')}
        <div class="who">
          <b>${esc(me.name || me.email)}</b>
          <small>${esc(me.email)}${subtitle}</small>
        </div>
        ${isAdmin ? `<button class="preview-icon-btn" id="openAdminDashboardBtn" type="button" title="Open Admin Portal">${ico('list_alt')} Admin Portal</button>` : ''}
        <button class="link-btn" id="switchBtn" type="button">Switch account</button>
      </div>`;
  }

  function bindSwitch() {
    const b = $('#switchBtn');
    if (b) {
      b.addEventListener('click', async () => {
        stopTimers();
        window.INITIAL_STATE = null;
        await api('POST', '/api/logout');
        try { window.google && google.accounts.id.disableAutoSelect(); } catch (_) {}
        boot();
      });
    }
    const adminBtn = $('#openAdminDashboardBtn');
    if (adminBtn) {
      adminBtn.addEventListener('click', () => showDirectorDashboard('master'));
    }
  }

  function fatal(message) {
    stopTimers();
    root.innerHTML = titleCard() + `<div class="banner">${ico('error')}<div>${esc(message)}</div></div>
      <div class="submit-area"><button class="btn-text" id="retryBtn" type="button">Try again</button></div>`;
    bindSwitch();
    $('#retryBtn').addEventListener('click', () => { window.INITIAL_STATE = null; boot(); });
  }

  function applyStateAndRender(state) {
    stopTimers();
    submitting = false; selectedId = null;
    me = state;
    offset = me.server_now - Date.now();
    if (me.faculty && me.faculty.length) {
      faculty = me.faculty;
      if (me.etag) currentEtag = me.etag;
    }
    if (!me.signed_in) return showSignin();

    // 1. Director & Coordinator Faculty (Suganesh Sir): land straight on Admin Portal (Master Overview table)
    if (me.role === 'director' || (me.role === 'faculty' && me.is_admin)) {
      return showDirectorDashboard('master');
    }

    // 2. Regular Faculty: land on Faculty Dashboard (ref second image)
    if (me.role === 'faculty') {
      return showFacultyDashboard('my_students');
    }

    // 3. Students (including Student Admin Suganesan S, who gets the form + [Admin Portal] button in account bar):
    if (me.selection) return showDone(me.selection, false);
    if (!me.is_open) return showClosed();
    return showForm(me.attempt);
  }

  // ---------- boot ----------
  async function boot() {
    stopTimers();
    submitting = false; selectedId = null;

    const init = window.INITIAL_STATE;
    if (init && typeof init === 'object' && init.server_now) {
      window.INITIAL_STATE = null;
      return applyStateAndRender(init);
    }

    const r = await api('GET', '/api/me');
    if (!r.ok) return fatal(r.data.message || 'Could not load the form. Please refresh.');
    return applyStateAndRender(r.data);
  }

  // ---------- sign in ----------
  const G_SKELETON = `
    <div class="g-btn-skeleton" id="gbtnSkeleton" style="display:inline-flex;align-items:center;justify-content:center;gap:10px;padding:9px 16px;border:1px solid #dadce0;border-radius:4px;background:#fff;color:#3c4043;font-size:14px;font-weight:500;cursor:pointer;box-shadow:0 1px 2px rgba(60,64,67,0.08);">
      <svg width="18" height="18" viewBox="0 0 18 18"><path fill="#4285F4" d="M17.64 9.2c0-.63-.06-1.25-.16-1.84H9v3.49h4.84a4.14 4.14 0 0 1-1.8 2.71v2.26h2.92c1.71-1.57 2.68-3.89 2.68-6.62z"/><path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.71H.96v2.33C2.44 15.98 5.48 18 9 18z"/><path fill="#FBBC05" d="M3.97 10.71c-.18-.54-.28-1.12-.28-1.71s.1-1.17.28-1.71V4.96H.96A8.996 8.996 0 0 0 0 9c0 1.45.35 2.82.96 4.04l3.01-2.33z"/><path fill="#EA4335" d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.58-2.59C13.46.89 11.43 0 9 0 5.48 0 2.44 2.02.96 4.96l3.01 2.33c.71-2.13 2.69-3.71 5.03-3.71z"/></svg>
      <span>Sign in with Google</span>
    </div>`;

  function showSignin(error) {
    stopTimers();
    root.classList.remove('wide-view');
    root.innerHTML = titleCard() + `
      <div class="card">
        <div class="q-title">Sign in to continue</div>
        <div class="signin-box">
          <div id="gbtn">${G_SKELETON}</div>
          <div class="hint">Use your college Google account (<b>@${esc(APP.domain)}</b>).
            Students will be routed to selection; faculties will access their student allocation dashboard.</div>
          <div class="banner ${error ? '' : 'hidden'}" id="signinError">${ico('error')}<div id="signinErrorText">${esc(error || '')}</div></div>
          ${APP.devLogin ? `
          <div class="dev-box">
            <div class="hint">Local testing only (DEV_LOGIN is enabled)</div>
            <input class="text-input" id="devEmail" placeholder="student or faculty email (e.g. suganeshs@bitsathy.ac.in)" />
            <button class="btn-text" id="devBtn" type="button">Dev sign in</button>
          </div>` : ''}
        </div>
      </div>`;

    if (APP.devLogin) {
      $('#devBtn').addEventListener('click', async () => {
        const r = await api('POST', '/api/dev-login', { email: $('#devEmail').value.trim() });
        if (!r.ok) return signinError(r.data.message);
        if (r.data && r.data.state) return applyStateAndRender(r.data.state);
        boot();
      });
    }
    if (!APP.clientId) {
      signinError('Google Sign-In is not set up yet (GOOGLE_CLIENT_ID is missing on the server).');
      return;
    }

    function initGsi() {
      if (window.google && google.accounts && google.accounts.id) {
        try {
          google.accounts.id.initialize({ client_id: APP.clientId, callback: onCredential, auto_select: false });
          const gb = $('#gbtn');
          if (gb) {
            const w = Math.min(300, Math.max(220, root.clientWidth - 80));
            google.accounts.id.renderButton(gb, { theme: 'outline', size: 'large', text: 'signin_with', shape: 'rectangular', width: w });
          }
          return true;
        } catch (_) {
          return false;
        }
      }
      return false;
    }

    window.onGsiLoaded = initGsi;
    if (initGsi()) return;

    let tries = 0;
    const wait = setInterval(() => {
      if (initGsi()) {
        clearInterval(wait);
      } else if (++tries > 80) {
        clearInterval(wait);
        signinError('Could not load Google Sign-In. Check your connection and refresh.');
      }
    }, 60);
  }

  function signinError(msg) {
    const box = $('#signinError');
    if (!box) return;
    $('#signinErrorText').textContent = msg || 'Sign-in failed.';
    box.classList.remove('hidden');
  }

  async function onCredential(resp) {
    const box = $('#signinError');
    if (box) box.classList.add('hidden');
    const gbtn = $('#gbtn');
    if (gbtn) {
      gbtn.style.opacity = '0.5';
      gbtn.style.pointerEvents = 'none';
    }

    const signinBox = $('.signin-box');
    let loadingEl = $('#signinLoading');
    if (!loadingEl && signinBox) {
      loadingEl = document.createElement('div');
      loadingEl.id = 'signinLoading';
      loadingEl.className = 'hint';
      loadingEl.style.cssText = 'color: var(--primary); font-weight: 500; display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 14px;';
      loadingEl.innerHTML = '<span class="spinner-sm"></span> Signing in…';
      signinBox.appendChild(loadingEl);
    }

    const r = await api('POST', '/api/auth/google', { credential: resp.credential });
    if (!r.ok) {
      if (loadingEl) loadingEl.remove();
      if (gbtn) {
        gbtn.style.opacity = '1';
        gbtn.style.pointerEvents = '';
      }
      return signinError(r.data.message || 'Sign-in failed. Please try again.');
    }
    if (r.data && r.data.state) {
      return applyStateAndRender(r.data.state);
    }
    boot();
  }

  // ============================================================
  // MASTER OVERVIEW & CAPACITY MANAGEMENT HELPERS
  // ============================================================
  // FACULTY SPECIALIZATIONS & MASTER OVERVIEW HELPERS
  // ============================================================
  const FACULTY_SPECS = {
    2: 'HR, Marketing',
    3: 'Analytics, Marketing, HR',
    4: 'Finance & Marketing',
    5: 'Analytics, HR, Marketing',
    6: 'Marketing, HR',
    7: 'Finance, Marketing',
    8: 'Finance, Marketing',
    9: 'Finance, Marketing',
    10: 'Analytics, Marketing',
    11: 'HR & Marketing',
  };

  function facSpec(f) {
    if (!f) return '';
    if (typeof f === 'string') {
      const q = f.trim().toLowerCase();
      const found = (faculty || []).find(x => x && x.name && x.name.trim().toLowerCase() === q);
      if (found) return found.specialization || FACULTY_SPECS[found.id] || '';
      const overview = (typeof me !== 'undefined' && me && me.master_overview) || [];
      const foundOv = overview.find(x => x && x.name && x.name.trim().toLowerCase() === q);
      if (foundOv) return foundOv.specialization || FACULTY_SPECS[foundOv.id] || '';
      return '';
    }
    if (f.specialization) return f.specialization;
    if (f.id && FACULTY_SPECS[f.id]) return FACULTY_SPECS[f.id];
    if (f.id) {
      const found = (faculty || []).find(x => x && x.id === f.id);
      if (found && found.specialization) return found.specialization;
    }
    if (f.name) {
      const q = f.name.trim().toLowerCase();
      const found = (faculty || []).find(x => x && x.name && x.name.trim().toLowerCase() === q);
      if (found && found.specialization) return found.specialization;
    }
    return '';
  }

  function renderMasterOverviewTable(overview) {
    if (!overview || !overview.length) {
      return `
        <div class="empty-table">
          ${ico('account_circle')}
          <div style="font-size: 15px; font-weight: 500; margin-bottom: 4px;">No faculty allocation data available</div>
        </div>`;
    }

    let rowsHtml = '';
    overview.forEach((f) => {
      const stus = f.students || [];
      const isFull = f.remaining <= 0;
      const spec = facSpec(f);
      const statusBadge = isFull
        ? `<span class="badge-full">Full (${f.capacity}/${f.capacity})</span>`
        : `<span class="badge-avail">${f.selected_count}/${f.capacity} filled (${f.remaining} left)</span>`;

      if (stus.length > 0) {
        const span = stus.length;
        rowsHtml += `
          <tr>
            <td rowspan="${span}" class="merged-cell s-no-cell">${f.s_no}</td>
            <td rowspan="${span}" class="merged-cell fac-name-cell">
              <b>${esc(f.name)}</b>
              ${spec ? `<div class="fac-spec-sub">(${esc(spec)})</div>` : ''}
              <div class="fac-meta-sub">${statusBadge}</div>
            </td>
            <td><b>${esc(stus[0].name)}</b></td>
            <td><span class="reg-chip">${esc(stus[0].register_no)}</span></td>
            <td><span style="color: var(--text-secondary);">${esc(stus[0].email)}</span></td>
          </tr>`;

        for (let i = 1; i < stus.length; i++) {
          rowsHtml += `
            <tr>
              <td><b>${esc(stus[i].name)}</b></td>
              <td><span class="reg-chip">${esc(stus[i].register_no)}</span></td>
              <td><span style="color: var(--text-secondary);">${esc(stus[i].email)}</span></td>
            </tr>`;
        }
      } else {
        rowsHtml += `
          <tr>
            <td class="merged-cell s-no-cell">${f.s_no}</td>
            <td class="merged-cell fac-name-cell">
              <b>${esc(f.name)}</b>
              ${spec ? `<div class="fac-spec-sub">(${esc(spec)})</div>` : ''}
              <div class="fac-meta-sub">${statusBadge}</div>
            </td>
            <td colspan="3" class="empty-muted">No students selected yet</td>
          </tr>`;
      }
    });

    return `
      <div class="table-responsive">
        <table class="master-fac-table">
          <thead>
            <tr>
              <th style="width: 55px; text-align: center;">S.No</th>
              <th style="width: 220px; text-align: center;">Faculty</th>
              <th>Students</th>
              <th>Register No</th>
              <th>Mail ID</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>`;
  }

  function renderSeatAllocationCard(overview) {
    if (!overview || !overview.length) return '';
    const totalCap = overview.reduce((acc, f) => acc + (f.capacity || 0), 0);
    const isBalanced = totalCap >= 44;

    return `
      <div class="seat-alloc-card">
        <div class="seat-alloc-header">
          <div>
            <div class="q-title" style="margin-bottom: 4px;">⚙️ Manage Faculty Seat Capacities</div>
            <div class="hint">Dynamically assign seat limits to guides. Changes take effect instantly on the live form.</div>
          </div>
          <div class="total-badge ${isBalanced ? 'ok' : 'warn'}" id="allocBadge">
            Total Seats: <span id="allocTotalNum">${totalCap}</span> / 44
          </div>
        </div>

        <div class="table-responsive" style="margin-bottom: 16px;">
          <table class="alloc-table">
            <thead>
              <tr>
                <th style="width: 45px;">#</th>
                <th>Faculty Name</th>
                <th>Current Status</th>
                <th style="text-align: right;">Allotted Seats</th>
              </tr>
            </thead>
            <tbody>
              ${overview.map(f => {
                const opts = [];
                for (let c = 1; c <= 10; c++) {
                  const dis = c < f.selected_count ? 'disabled' : '';
                  const disNote = c < f.selected_count ? ` (min ${f.selected_count})` : '';
                  opts.push(`<option value="${c}" ${f.capacity === c ? 'selected' : ''} ${dis}>${c} seats${disNote}</option>`);
                }
                return `
                  <tr>
                    <td><b>${f.s_no}</b></td>
                    <td><b>${esc(f.name)}</b>${facSpec(f) ? ` <span class="fac-spec-sub" style="display:inline-block; margin-left:6px; font-weight:normal;">(${esc(facSpec(f))})</span>` : ''}</td>
                    <td><span style="color: var(--text-secondary);">${f.selected_count} filled (${f.capacity - f.selected_count} left)</span></td>
                    <td style="text-align: right;">
                      <select class="cap-select" data-fid="${f.id}" data-min="${f.selected_count}">
                        ${opts.join('')}
                      </select>
                    </td>
                  </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>

        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
          <button class="btn-primary" id="saveCapBtn" type="button" style="padding: 10px 20px;">
            Save Seat Capacities
          </button>
          <div class="hint" id="allocNote" style="font-size: 12px; font-weight: 500; color: ${isBalanced ? 'var(--ok)' : 'var(--error)'};">
            ${isBalanced ? '✓ Total capacity accommodates all 44 students.' : '⚠️ Warning: Total seats (' + totalCap + ') less than 44 students.'}
          </div>
        </div>

        <div class="reset-box" style="margin-top: 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; background: var(--hover); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px;">
          <div>
            <div style="font-weight: 600; font-size: 13px; color: var(--text);">🔄 Google Sheets & Database Reconciliation</div>
            <div class="hint" style="font-size: 12px; margin-top: 2px;">Sync allocations between PostgreSQL/SQLite and Google Sheets, resolving any sync discrepancies.</div>
          </div>
          <button class="btn-text" id="reconcileSheetsBtn" type="button" style="border: 1px solid var(--border); border-radius: 6px; padding: 7px 14px; font-weight: 500; display: inline-flex; align-items: center; gap: 6px; background: var(--card-bg, #fff); cursor: pointer;">
            🔄 Reconcile Sheets & DB
          </button>
        </div>
      </div>`;
  }

  function setupSeatAllocationHandlers(onRefresh) {
    const selects = root.querySelectorAll('.cap-select');
    const badge = $('#allocBadge');
    const totalEl = $('#allocTotalNum');
    const noteEl = $('#allocNote');

    const updateSum = () => {
      let sum = 0;
      selects.forEach(s => sum += Number(s.value));
      if (totalEl) totalEl.textContent = sum;
      if (badge && noteEl) {
        const ok = sum >= 44;
        badge.className = 'total-badge ' + (ok ? 'ok' : 'warn');
        noteEl.textContent = ok ? '✓ Total capacity accommodates all 44 students.' : '⚠️ Warning: Total seats (' + sum + ') less than 44 students.';
        noteEl.style.color = ok ? 'var(--ok)' : 'var(--error)';
      }
      return sum;
    };

    selects.forEach(s => s.addEventListener('change', updateSum));

    const saveBtn = $('#saveCapBtn');
    if (saveBtn) {
      saveBtn.addEventListener('click', async () => {
        const sum = updateSum();
        if (sum < 44) {
          if (!confirm(`Warning: Total seats (${sum}) is less than the 44 students in class roster. Continue anyway?`)) {
            return;
          }
        }
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving…';
        const caps = {};
        selects.forEach(s => { caps[s.dataset.fid] = Number(s.value); });
        const r = await api('POST', '/api/admin/update-capacities', { capacities: caps });
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Seat Capacities';
        if (!r.ok) return toast(r.data.message || 'Failed to update capacities.');
        toast('Seat capacities updated dynamically & synced to Google Sheets!');
        me.master_overview = r.data.master_overview;
        if (r.data.faculty) faculty = r.data.faculty;
        if (r.data.faculties) {
          dbFacultiesCache = r.data.faculties;
          const fCnt = $('#dbFacultyBadgeCount');
          if (fCnt) fCnt.textContent = dbFacultiesCache.length;
        } else {
          dbFacultiesCache = null;
        }
        if (onRefresh) onRefresh();
      });
    }

    const recBtn = $('#reconcileSheetsBtn');
    if (recBtn) {
      recBtn.addEventListener('click', async () => {
        recBtn.disabled = true;
        const orig = recBtn.innerHTML;
        recBtn.innerHTML = '⏳ Reconciling…';
        try {
          const r = await api('POST', '/api/admin/reconcile-sheets');
          if (!r.ok) {
            toast(r.data?.message || 'Reconciliation failed.');
          } else {
            toast('✓ Sheets and database reconciled successfully!');
            const rMe = await api('GET', '/api/director/overview');
            if (rMe.ok) me.master_overview = rMe.data.master_overview;
            if (onRefresh) onRefresh();
          }
        } catch (e) {
          toast('Reconciliation error: ' + (e.message || e));
        } finally {
          recBtn.disabled = false;
          recBtn.innerHTML = orig;
        }
      });
    }

    /*
    const resetBtn = $('#resetTesterBtn');
    if (resetBtn) {
      resetBtn.addEventListener('click', async () => {
        resetBtn.disabled = true;
        resetBtn.textContent = 'Resetting…';
        const r = await api('POST', '/api/admin/reset-user', { register_no: '7376257MB144', email: 'suganesans.mb25@bitsathy.ac.in' });
        resetBtn.disabled = false;
        resetBtn.textContent = 'Reset Suganesan S (7376257MB144)';
        if (!r.ok) return toast(r.data.message || 'Failed to reset.');
        toast('Cleared test data for Suganesan S (7376257MB144)!');
        const rMe = await api('GET', '/api/director/overview');
        if (rMe.ok) {
          me.master_overview = rMe.data.master_overview;
          if (onRefresh) onRefresh();
        }
      });
    }
    */
  }

  // ============================================================
  // ADMIN & DIRECTOR DASHBOARD (Clean Master Table, No Preview)
  // ============================================================
  async function showDirectorDashboard(activeTab = 'master') {
    stopTimers();
    root.classList.add('wide-view');
    let overview = me.master_overview;
    if (!overview) {
      const r = await api('GET', '/api/director/overview');
      if (r.ok) {
        overview = r.data.master_overview;
        me.master_overview = overview;
      }
    }
    overview = overview || [];

    const isDirector = me && me.role === 'director';
    const isAdmin = Boolean(me && me.is_admin);
    const isFacultyAdmin = me && me.role === 'faculty' && isAdmin;
    const isStudentAdmin = me && me.role === 'student' && isAdmin;

    // If faculty member doesn't have personal dashboard data loaded yet, fetch it
    if (me && me.role === 'faculty' && !me.faculty_dashboard) {
      const rF = await api('GET', '/api/faculty/dashboard');
      if (rF.ok) me.faculty_dashboard = rF.data;
    }

    const totalStudents = 44;
    const totalFilled = overview.reduce((acc, f) => acc + (f.selected_count || 0), 0);
    const totalCap = overview.reduce((acc, f) => acc + (f.capacity || 0), 0);
    const remainingStudents = Math.max(0, totalStudents - totalFilled);

    let portalTitle = 'Admin Portal';
    if (isDirector) portalTitle = 'Director Portal';
    else if (isFacultyAdmin) portalTitle = 'Coordinator Portal';
    else if (me && me.role === 'faculty') portalTitle = 'Faculty Portal';

    let portalSub = `Master guide selection overview for <b>${esc(isDirector ? 'Dr Murugappan S (Director)' : (me.name || me.email))}</b>. All faculty allocations and student choices in real-time.`;

    root.innerHTML = `
      <div class="title-card">
        <div class="accent"></div>
        <div class="title-body">
          <h1>${portalTitle}</h1>
          <p class="muted">${portalSub}</p>
        </div>
        ${accountBar()}
      </div>

      <div class="card">
        <div class="q-title" style="margin-bottom: 14px;">Class Allocation Overview (II MBA)</div>
        <div class="fac-stat-grid">
          <div class="fac-stat-card">
            <div class="val">${totalStudents}</div>
            <div class="lbl">Class Strength</div>
          </div>
          <div class="fac-stat-card">
            <div class="val" style="color: var(--ok);">${totalFilled}</div>
            <div class="lbl">Students Allocated</div>
          </div>
          <div class="fac-stat-card">
            <div class="val" style="color: ${remainingStudents === 0 ? 'var(--ok)' : 'var(--primary)'};">${remainingStudents}</div>
            <div class="lbl">Pending Choices</div>
          </div>
        </div>
        <div class="meter-bar" style="height: 10px; margin-bottom: 4px;">
          <div class="meter-fill" style="width: ${Math.round((totalFilled / totalStudents) * 100)}%;"></div>
        </div>
        <div class="hint" style="text-align: right; font-size: 12px; margin-top: 6px;">
          ${totalFilled} of ${totalStudents} students selected (${totalCap} total faculty seats configured)
        </div>
      </div>

      <div class="portal-tabs">
        <button class="portal-tab ${activeTab === 'master' ? 'active' : ''}" id="tabDirectorMaster" type="button">
          ${ico('list_alt')} Master Department Overview
        </button>
        ${(isDirector || isAdmin) ? `
        <button class="portal-tab ${activeTab === 'seats' ? 'active' : ''}" id="tabDirectorSeats" type="button">
          ⚙️ Seat Allocation & Quotas
        </button>
        <button class="portal-tab ${activeTab === 'database' ? 'active' : ''}" id="tabDirectorDatabase" type="button">
          🗄️ Database
        </button>` : ''}
        ${(me && me.role === 'faculty') ? `
        <button class="portal-tab ${activeTab === 'my_students' ? 'active' : ''}" id="tabDirectorMyStudents" type="button">
          👤 My Allocated Students (${(me.faculty_dashboard && me.faculty_dashboard.students_selected) ? me.faculty_dashboard.students_selected.length : 0})
        </button>` : ''}
        ${me && me.selection ? `
        <button class="portal-tab" id="tabDirectorMySubmission" type="button">
          ${ico('check_circle')} My Submission
        </button>` : (isStudentAdmin ? `
        <button class="portal-tab" id="tabDirectorSelectionForm" type="button">
          ${ico('assignment')} Selection Form
        </button>` : '')}
      </div>

      <div id="directorTabContent"></div>
    `;

    bindSwitch();
    const tabContent = $('#directorTabContent');

    if (activeTab === 'master') {
      tabContent.innerHTML = `
        <div class="card">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
            <div class="q-title" style="margin-bottom: 0;">Faculty-Wise Student Selections</div>
            <button class="btn-text" id="refreshDirectorBtn" type="button" style="padding: 4px 10px; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;">
              ${ico('refresh')} Refresh Live
            </button>
          </div>
          ${renderMasterOverviewTable(overview)}
        </div>
      `;

      const refBtn = $('#refreshDirectorBtn');
      if (refBtn) {
        refBtn.addEventListener('click', async () => {
          refBtn.textContent = 'Refreshing…';
          const r = await api('GET', '/api/director/overview');
          if (r.ok) {
            me.master_overview = r.data.master_overview;
            showDirectorDashboard('master');
          }
        });
      }

      // Auto-poll director overview every 4 seconds
      pollTimer = setInterval(async () => {
        if (document.hidden) return;
        const r = await api('GET', '/api/director/overview');
        if (r.ok) {
          me.master_overview = r.data.master_overview;
          const container = $('#directorTabContent');
          if (container && $('#tabDirectorMaster') && $('#tabDirectorMaster').classList.contains('active')) {
            const tableWrap = container.querySelector('.table-responsive');
            if (tableWrap) {
              tableWrap.outerHTML = renderMasterOverviewTable(r.data.master_overview);
            }
          }
        }
      }, 4000);
    } else if (activeTab === 'seats') {
      tabContent.innerHTML = renderSeatAllocationCard(overview);
      setupSeatAllocationHandlers(() => showDirectorDashboard('seats'));
    } else if (activeTab === 'database') {
      renderDatabaseManagementTab(tabContent);
    } else if (activeTab === 'my_students') {
      renderMyAllocatedStudentsTab(tabContent);
    }

    const tMaster = $('#tabDirectorMaster');
    if (tMaster) tMaster.addEventListener('click', () => showDirectorDashboard('master'));
    const tSeats = $('#tabDirectorSeats');
    if (tSeats) tSeats.addEventListener('click', () => showDirectorDashboard('seats'));
    const tDatabase = $('#tabDirectorDatabase');
    if (tDatabase) tDatabase.addEventListener('click', () => {
      dbFacultiesCache = null;
      showDirectorDashboard('database');
    });
    const tStudents = $('#tabDirectorMyStudents');
    if (tStudents) tStudents.addEventListener('click', () => showDirectorDashboard('my_students'));
    const mySubBtn = $('#tabDirectorMySubmission');
    if (mySubBtn) mySubBtn.addEventListener('click', () => {
      stopTimers();
      root.classList.remove('wide-view');
      showDone(me.selection, true);
    });
    const selFormBtn = $('#tabDirectorSelectionForm');
    if (selFormBtn) {
      selFormBtn.addEventListener('click', () => {
        stopTimers();
        root.classList.remove('wide-view');
        if (me.selection) return showDone(me.selection, true);
        if (!me.is_open) return showClosed();
        return showForm(me.attempt);
      });
    }
  }

  // ============================================================
  // DATABASE MANAGEMENT TAB (Students & Faculties CRUD)
  // ============================================================
  let currentDbSubTab = 'students';
  let dbStudentsCache = null;
  let dbFacultiesCache = null;
  let dbSearchQuery = '';

  function showModal({ title, bodyHtml, confirmText = 'Save', confirmBtnClass = 'btn-primary', onConfirm }) {
    const old = document.querySelector('.modal-backdrop');
    if (old) old.remove();

    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal-card">
        <div class="modal-header">
          <h3>${title}</h3>
          <button class="modal-close" type="button" aria-label="Close">&times;</button>
        </div>
        <div class="modal-body">
          ${bodyHtml}
        </div>
        <div class="modal-footer">
          <button class="btn-text" type="button" id="modalCancelBtn">Cancel</button>
          <button class="${confirmBtnClass}" type="button" id="modalConfirmBtn">${confirmText}</button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);

    const close = () => backdrop.remove();
    backdrop.querySelector('.modal-close').addEventListener('click', close);
    backdrop.querySelector('#modalCancelBtn').addEventListener('click', close);
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) close();
    });

    const confirmBtn = backdrop.querySelector('#modalConfirmBtn');
    confirmBtn.addEventListener('click', async () => {
      confirmBtn.disabled = true;
      const originalText = confirmBtn.textContent;
      confirmBtn.textContent = 'Saving…';
      try {
        const ok = await onConfirm(backdrop);
        if (ok) close();
        else {
          confirmBtn.disabled = false;
          confirmBtn.textContent = originalText;
        }
      } catch (err) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = originalText;
        toast(err.message || 'Operation failed');
      }
    });

    backdrop.querySelectorAll('input').forEach(inp => {
      inp.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          confirmBtn.click();
        }
      });
    });

    const firstInput = backdrop.querySelector('input');
    if (firstInput) setTimeout(() => firstInput.focus(), 50);

    return backdrop;
  }

  function renderDatabaseManagementTab(container) {
    container.innerHTML = `
      <div class="card" style="padding-top: 18px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; border-bottom: 1px solid var(--border); padding-bottom: 14px;">
          <div class="db-subtabs">
            <button class="btn-subtab ${currentDbSubTab === 'students' ? 'active' : ''}" id="dbSubtabStudents" type="button">
              👨‍🎓 Students (<span id="dbStudentBadgeCount">${dbStudentsCache ? dbStudentsCache.length : '…'}</span>)
            </button>
            <button class="btn-subtab ${currentDbSubTab === 'faculties' ? 'active' : ''}" id="dbSubtabFaculties" type="button">
              👨‍🏫 Faculties (<span id="dbFacultyBadgeCount">${dbFacultiesCache ? dbFacultiesCache.length : '…'}</span>)
            </button>
          </div>

          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <div class="db-search-wrap">
              <input type="text" id="dbSearchInput" class="db-search-input" placeholder="Search ${currentDbSubTab}…" value="${esc(dbSearchQuery)}" autocomplete="off">
              <span class="db-search-icon" style="position: absolute; right: 12px; top: 50%; transform: translateY(-50%); opacity: 0.5; pointer-events: none; font-size: 13px;">🔍</span>
            </div>
            <button class="btn-primary" id="dbAddBtn" type="button" style="padding: 7px 14px; font-size: 13px; font-weight: 600; border-radius: 6px; display: inline-flex; align-items: center; gap: 6px;">
              ${currentDbSubTab === 'students' ? '➕ Add Student' : '➕ Add Faculty'}
            </button>
            <button class="btn-text" id="dbReconcileBtn" type="button" style="padding: 6px 10px; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;" title="Reconcile Sheets & DB">
              🔄 Reconcile Sheets
            </button>
            <button class="btn-text" id="dbRefreshBtn" type="button" style="padding: 6px 10px; font-size: 13px;" title="Refresh Data">
              ${ico('refresh')} Refresh
            </button>
          </div>
        </div>

        <div id="dbTableWrapper">
          <div style="text-align: center; padding: 30px; color: var(--text-hint);">Loading database records…</div>
        </div>
      </div>
    `;

    const subStudents = $('#dbSubtabStudents');
    const subFaculties = $('#dbSubtabFaculties');
    const searchInput = $('#dbSearchInput');
    const addBtn = $('#dbAddBtn');
    const refreshBtn = $('#dbRefreshBtn');
    const dbRecBtn = $('#dbReconcileBtn');

    if (dbRecBtn) {
      dbRecBtn.addEventListener('click', async () => {
        dbRecBtn.disabled = true;
        const orig = dbRecBtn.innerHTML;
        dbRecBtn.innerHTML = '⏳ Reconciling…';
        try {
          const r = await api('POST', '/api/admin/reconcile-sheets');
          if (!r.ok) {
            toast(r.data?.message || 'Reconciliation failed.');
          } else {
            toast('✓ Sheets and database reconciled successfully!');
            dbStudentsCache = null;
            dbFacultiesCache = null;
            await loadDatabaseData();
            const rMe = await api('GET', '/api/director/overview');
            if (rMe.ok) me.master_overview = rMe.data.master_overview;
          }
        } catch (e) {
          toast('Reconciliation error: ' + (e.message || e));
        } finally {
          dbRecBtn.disabled = false;
          dbRecBtn.innerHTML = orig;
        }
      });
    }

    if (subStudents) {
      subStudents.addEventListener('click', () => {
        if (currentDbSubTab !== 'students') {
          currentDbSubTab = 'students';
          dbSearchQuery = '';
          dbStudentsCache = null;
          renderDatabaseManagementTab(container);
        }
      });
    }

    if (subFaculties) {
      subFaculties.addEventListener('click', () => {
        if (currentDbSubTab !== 'faculties') {
          currentDbSubTab = 'faculties';
          dbSearchQuery = '';
          dbFacultiesCache = null;
          renderDatabaseManagementTab(container);
        }
      });
    }

    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        dbSearchQuery = e.target.value.trim().toLowerCase();
        renderCurrentDbTable();
      });
    }

    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        if (currentDbSubTab === 'students') dbStudentsCache = null;
        else dbFacultiesCache = null;
        loadDatabaseData();
      });
    }

    if (addBtn) {
      addBtn.addEventListener('click', () => {
        if (currentDbSubTab === 'students') openStudentModal(null);
        else openFacultyModal(null);
      });
    }

    loadDatabaseData();
  }

  async function loadDatabaseData() {
    const wrapper = $('#dbTableWrapper');
    if (!wrapper) return;

    if (currentDbSubTab === 'students') {
      if (!dbStudentsCache) {
        wrapper.innerHTML = `<div style="text-align: center; padding: 30px; color: var(--text-hint);">Loading students from database…</div>`;
        const r = await api('GET', '/api/admin/database/students');
        if (!r.ok) {
          wrapper.innerHTML = `<div style="text-align: center; padding: 30px; color: var(--error);">${esc(r.data.message || 'Failed to load students.')}</div>`;
          return;
        }
        dbStudentsCache = r.data.students || [];
      }
      const cntEl = $('#dbStudentBadgeCount');
      if (cntEl) cntEl.textContent = dbStudentsCache.length;
      renderCurrentDbTable();

      if (!dbFacultiesCache) {
        api('GET', '/api/admin/database/faculties').then(rF => {
          if (rF.ok) {
            dbFacultiesCache = rF.data.faculties || [];
            const fCnt = $('#dbFacultyBadgeCount');
            if (fCnt) fCnt.textContent = dbFacultiesCache.length;
          }
        });
      }
    } else {
      if (!dbFacultiesCache) {
        wrapper.innerHTML = `<div style="text-align: center; padding: 30px; color: var(--text-hint);">Loading faculties from database…</div>`;
        const r = await api('GET', '/api/admin/database/faculties');
        if (!r.ok) {
          wrapper.innerHTML = `<div style="text-align: center; padding: 30px; color: var(--error);">${esc(r.data.message || 'Failed to load faculties.')}</div>`;
          return;
        }
        dbFacultiesCache = r.data.faculties || [];
      }
      const cntEl = $('#dbFacultyBadgeCount');
      if (cntEl) cntEl.textContent = dbFacultiesCache.length;
      renderCurrentDbTable();
    }
  }

  function renderCurrentDbTable() {
    const wrapper = $('#dbTableWrapper');
    if (!wrapper) return;

    if (currentDbSubTab === 'students') {
      const list = (dbStudentsCache || []).filter(s => {
        if (!dbSearchQuery) return true;
        const q = dbSearchQuery;
        return (
          (s.register_no && s.register_no.toLowerCase().includes(q)) ||
          (s.name && s.name.toLowerCase().includes(q)) ||
          (s.email && s.email.toLowerCase().includes(q)) ||
          (s.allocation && s.allocation.faculty_name && s.allocation.faculty_name.toLowerCase().includes(q))
        );
      });

      if (!list.length) {
        wrapper.innerHTML = `
          <div style="text-align: center; padding: 35px 20px; color: var(--text-hint);">
            ${dbSearchQuery ? `No students found matching "<b>${esc(dbSearchQuery)}</b>"` : 'No student records in the database.'}
          </div>
        `;
        return;
      }

      wrapper.innerHTML = `
        <div class="table-responsive">
          <table class="alloc-table" style="margin-bottom: 0;">
            <thead>
              <tr>
                <th style="width: 50px; text-align: center;">#</th>
                <th style="width: 140px;">Register No</th>
                <th>Student Name</th>
                <th>Email ID</th>
                <th>Guide Allocation Status</th>
                <th style="width: 125px; text-align: center;">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${list.map((s, idx) => `
                <tr>
                  <td style="text-align: center; font-weight: 600; color: var(--text-hint);">${idx + 1}</td>
                  <td><span class="reg-chip">${esc(s.register_no)}</span></td>
                  <td><b>${esc(s.name)}</b></td>
                  <td><span style="font-size: 12.5px; color: var(--text-secondary);">${esc(s.email || '—')}</span></td>
                  <td>
                    ${s.allocation ? `
                      <span class="badge-allocated" title="Seq #${s.allocation.seq_id} allocated at ${s.allocation.time}">
                        ✓ ${esc(s.allocation.faculty_name)}
                      </span>
                    ` : `
                      <span class="badge-pending">⏳ Pending Choice</span>
                    `}
                  </td>
                  <td style="text-align: center; vertical-align: middle;">
                    <div class="action-btn-group">
                      <button class="icon-btn edit-student-btn" data-reg="${esc(s.register_no)}" title="Edit Student">✏️</button>
                      ${s.allocation ? `
                        <button class="icon-btn reset-student-btn" data-reg="${esc(s.register_no)}" title="Reset Guide Choice (Keep on roster)">🔄</button>
                      ` : `
                        <span class="icon-btn-placeholder" aria-hidden="true"></span>
                      `}
                      <button class="icon-btn icon-btn-delete delete-student-btn" data-reg="${esc(s.register_no)}" title="Manage / Delete Student">🗑️</button>
                    </div>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
        <div class="hint" style="text-align: right; margin-top: 10px; font-size: 12px;">
          Showing ${list.length} of ${dbStudentsCache.length} students
        </div>
      `;

      wrapper.querySelectorAll('.edit-student-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const reg = btn.dataset.reg;
          const stu = dbStudentsCache.find(x => x.register_no === reg);
          if (stu) openStudentModal(stu);
        });
      });

      wrapper.querySelectorAll('.reset-student-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const reg = btn.dataset.reg;
          const stu = dbStudentsCache.find(x => x.register_no === reg);
          if (stu) confirmResetStudentChoice(stu);
        });
      });

      wrapper.querySelectorAll('.delete-student-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const reg = btn.dataset.reg;
          const stu = dbStudentsCache.find(x => x.register_no === reg);
          if (stu) confirmDeleteStudent(stu);
        });
      });
    } else {
      const list = (dbFacultiesCache || []).filter(f => {
        if (!dbSearchQuery) return true;
        const q = dbSearchQuery;
        return (
          (f.name && f.name.toLowerCase().includes(q)) ||
          (f.email && f.email.toLowerCase().includes(q)) ||
          (f.specialization && f.specialization.toLowerCase().includes(q)) ||
          String(f.id).includes(q)
        );
      });

      if (!list.length) {
        wrapper.innerHTML = `
          <div style="text-align: center; padding: 35px 20px; color: var(--text-hint);">
            ${dbSearchQuery ? `No faculties found matching "<b>${esc(dbSearchQuery)}</b>"` : 'No faculty records in the database.'}
          </div>
        `;
        return;
      }

      wrapper.innerHTML = `
        <div class="table-responsive">
          <table class="alloc-table" style="margin-bottom: 0;">
            <thead>
              <tr>
                <th style="width: 50px; text-align: center;">#</th>
                <th>Faculty Name</th>
                <th>Institutional Email</th>
                <th>Domain / Specialization</th>
                <th style="width: 90px; text-align: center;">Capacity</th>
                <th style="width: 130px; text-align: center;">Allocated / Left</th>
                <th style="width: 100px; text-align: center;">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${list.map((f, idx) => `
                <tr>
                  <td style="text-align: center; font-weight: 600; color: var(--text-hint);">${idx + 1}</td>
                  <td><b>${esc(f.name)}</b></td>
                  <td><span style="font-size: 12.5px; color: var(--text-secondary);">${esc(f.email || '—')}</span></td>
                  <td><span class="domain-chip">${esc(f.specialization || 'General')}</span></td>
                  <td style="text-align: center;"><b>${f.capacity}</b> seats</td>
                  <td style="text-align: center;">
                    <span style="font-weight: 600; font-size: 12.5px; color: ${f.remaining === 0 ? 'var(--error)' : 'var(--ok)'};">
                      ${f.selected_count} / ${f.remaining} left
                    </span>
                  </td>
                  <td style="text-align: center; vertical-align: middle;">
                    <div class="action-btn-group-fac">
                      <button class="icon-btn edit-faculty-btn" data-fid="${f.id}" title="Edit Faculty">✏️</button>
                      <button class="icon-btn icon-btn-delete delete-faculty-btn" data-fid="${f.id}" data-name="${esc(f.name)}" data-count="${f.selected_count}" title="Delete Faculty">🗑️</button>
                    </div>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
        <div class="hint" style="text-align: right; margin-top: 10px; font-size: 12px;">
          Showing ${list.length} of ${dbFacultiesCache.length} faculties (${list.reduce((acc, x) => acc + x.capacity, 0)} total seats)
        </div>
      `;

      wrapper.querySelectorAll('.edit-faculty-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const fid = Number(btn.dataset.fid);
          const fac = dbFacultiesCache.find(x => x.id === fid);
          if (fac) openFacultyModal(fac);
        });
      });

      wrapper.querySelectorAll('.delete-faculty-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const fid = Number(btn.dataset.fid);
          const name = btn.dataset.name;
          const count = Number(btn.dataset.count || 0);
          confirmDeleteFaculty(fid, name, count);
        });
      });
    }
  }

  function openStudentModal(student) {
    const isEdit = Boolean(student);
    const title = isEdit ? `✏️ Edit Student (${esc(student.register_no)})` : `➕ Add New Student`;
    const bodyHtml = `
      <div class="modal-field">
        <label for="mStuRegNo">Register Number *</label>
        <input type="text" id="mStuRegNo" placeholder="e.g. 7376257MB144" value="${esc(student ? student.register_no : '')}" style="text-transform: uppercase;">
      </div>
      <div class="modal-field">
        <label for="mStuName">Full Name *</label>
        <input type="text" id="mStuName" placeholder="e.g. Suganesan S" value="${esc(student ? student.name : '')}">
      </div>
      <div class="modal-field">
        <label for="mStuEmail">Institutional Email</label>
        <input type="email" id="mStuEmail" placeholder="e.g. suganesans.mb25@bitsathy.ac.in" value="${esc(student ? student.email : '')}">
      </div>
      ${isEdit ? `
        <div class="modal-note">
          <b>Note:</b> If you update the register number or name, any active guide selection will be automatically updated in real time.
        </div>
      ` : `
        <div class="modal-note">
          The student will be instantly authorized to sign in using their institutional email ID.
        </div>
      `}
    `;

    showModal({
      title,
      bodyHtml,
      confirmText: isEdit ? 'Save Changes' : 'Add Student',
      onConfirm: async (backdrop) => {
        const reg = backdrop.querySelector('#mStuRegNo').value.trim().toUpperCase();
        const name = backdrop.querySelector('#mStuName').value.trim();
        const email = backdrop.querySelector('#mStuEmail').value.trim().toLowerCase();

        if (!reg) {
          toast('Please enter a register number.');
          return false;
        }
        if (!name) {
          toast('Please enter the student name.');
          return false;
        }

        const payload = {
          old_register_no: isEdit ? student.register_no : null,
          register_no: reg,
          name: name,
          email: email || null,
        };

        const res = await api('POST', '/api/admin/database/students/save', payload);
        if (!res.ok) {
          toast(res.data.message || 'Failed to save student.');
          return false;
        }

        toast(isEdit ? 'Student updated successfully!' : 'New student added!');
        dbStudentsCache = null;
        await loadDatabaseData();
        return true;
      }
    });
  }

  function confirmResetStudentChoice(stu) {
    const reg = stu.register_no;
    const name = stu.name;
    const facName = stu.allocation ? stu.allocation.faculty_name : 'their selected guide';

    showModal({
      title: `🔄 Reset Guide Selection`,
      bodyHtml: `
        <p style="margin: 0; color: var(--text-primary); line-height: 1.5; font-size: 14px;">
          Reset guide choice for <b>${esc(name)} (${esc(reg)})</b>?
        </p>
        <div style="background: #f8f9fa; border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-top: 12px;">
          <div style="font-size: 11.5px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase;">Allocated Guide to Free</div>
          <div style="font-weight: 600; color: var(--primary); font-size: 14px; margin-top: 3px;">✓ ${esc(facName)}</div>
        </div>
        <div class="modal-note" style="border-left-color: var(--primary); margin-top: 12px;">
          This frees 1 seat with ${esc(facName)}. <b>${esc(name)} will remain on the class roster</b> and can log back in with their college account to choose again.
        </div>
      `,
      confirmText: 'Reset Choice',
      confirmBtnClass: 'btn-primary',
      onConfirm: async () => {
        const res = await api('POST', '/api/admin/database/students/reset', { register_no: reg });
        if (!res.ok) {
          toast(res.data.message || 'Failed to reset selection.');
          return false;
        }
        toast(`Selection reset for ${name}. Student can now choose again.`);
        dbStudentsCache = null;
        await loadDatabaseData();
        const rMe = await api('GET', '/api/director/overview');
        if (rMe.ok) me.master_overview = rMe.data.master_overview;
        return true;
      }
    });
  }

  function confirmDeleteStudent(stu) {
    const reg = stu.register_no;
    const name = stu.name;
    const alloc = stu.allocation;

    if (alloc) {
      const modal = showModal({
        title: `⚙️ Manage Student Allocation`,
        bodyHtml: `
          <p style="margin: 0; color: var(--text-primary); font-size: 13.5px; line-height: 1.5;">
            Action for <b>${esc(name)} (${esc(reg)})</b>:
          </p>
          <div style="background: #f8f9fa; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; margin-top: 10px;">
            <div style="font-size: 11px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase;">Currently Allocated Guide</div>
            <div style="font-weight: 600; color: var(--primary); font-size: 13.5px; margin-top: 2px;">✓ ${esc(alloc.faculty_name)}</div>
            <div style="font-size: 11.5px; color: var(--text-hint); margin-top: 1px;">Selected at ${alloc.time} (Seq #${alloc.seq_id})</div>
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px; margin-top: 14px;">
            <!-- Option 1: Reset Selection Only -->
            <div style="border: 1.5px solid #d1c4e9; background: #faf8fd; border-radius: 8px; padding: 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px;">
              <div>
                <div style="font-weight: 600; font-size: 13px; color: var(--primary);">🔄 Reset Selection Only</div>
                <div style="font-size: 11.5px; color: var(--text-secondary); margin-top: 2px; line-height: 1.35;">
                  Frees this seat so the student can re-choose. <b>Keeps student on class roster.</b>
                </div>
              </div>
              <button class="btn-primary" type="button" id="btnOptResetOnly" style="white-space: nowrap; padding: 7px 12px; font-size: 12px;">
                Reset Selection
              </button>
            </div>

            <!-- Option 2: Delete from Class Roster -->
            <div style="border: 1.5px solid #fad2cf; background: #fef7f6; border-radius: 8px; padding: 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px;">
              <div>
                <div style="font-weight: 600; font-size: 13px; color: var(--error);">🗑️ Delete from Roster</div>
                <div style="font-size: 11.5px; color: var(--text-secondary); margin-top: 2px; line-height: 1.35;">
                  Permanently deletes student from the roster and frees their allocated seat.
                </div>
              </div>
              <button class="btn-text" type="button" id="btnOptDeleteRoster" style="white-space: nowrap; padding: 7px 12px; font-size: 12px; color: var(--error); border: 1px solid #fad2cf; border-radius: 6px;">
                Delete Student
              </button>
            </div>
          </div>
        `,
        confirmText: 'Cancel',
        confirmBtnClass: 'btn-text',
        onConfirm: async () => true,
      });

      if (modal) {
        const footer = modal.querySelector('.modal-footer');
        if (footer) footer.style.display = 'none';

        const resetBtn = modal.querySelector('#btnOptResetOnly');
        if (resetBtn) {
          resetBtn.addEventListener('click', async () => {
            resetBtn.disabled = true;
            resetBtn.textContent = 'Resetting…';
            const res = await api('POST', '/api/admin/database/students/reset', { register_no: reg });
            if (!res.ok) {
              resetBtn.disabled = false;
              resetBtn.textContent = 'Reset Selection';
              return toast(res.data.message || 'Failed to reset selection.');
            }
            toast(`Selection reset for ${name}. Student can now choose again.`);
            modal.remove();
            dbStudentsCache = null;
            await loadDatabaseData();
            const rMe = await api('GET', '/api/director/overview');
            if (rMe.ok) me.master_overview = rMe.data.master_overview;
          });
        }

        const deleteBtn = modal.querySelector('#btnOptDeleteRoster');
        if (deleteBtn) {
          deleteBtn.addEventListener('click', async () => {
            if (!confirm(`Are you sure you want to completely remove ${name} (${reg}) from the class roster?`)) {
              return;
            }
            deleteBtn.disabled = true;
            deleteBtn.textContent = 'Deleting…';
            const res = await api('POST', '/api/admin/database/students/delete', { register_no: reg });
            if (!res.ok) {
              deleteBtn.disabled = false;
              deleteBtn.textContent = 'Delete Student';
              return toast(res.data.message || 'Failed to delete student.');
            }
            toast(`Student ${reg} removed from class roster.`);
            modal.remove();
            dbStudentsCache = null;
            await loadDatabaseData();
            const rMe = await api('GET', '/api/director/overview');
            if (rMe.ok) me.master_overview = rMe.data.master_overview;
          });
        }
      }
    } else {
      showModal({
        title: `🗑️ Delete Student from Roster`,
        bodyHtml: `
          <p style="margin: 0; color: var(--text-primary); line-height: 1.5;">
            Are you sure you want to remove <b>${esc(name)} (${esc(reg)})</b> from the class roster?
          </p>
          <div class="modal-note" style="border-left-color: var(--error); margin-top: 14px;">
            This student has not yet selected a guide. Removing them will delete their record from the roster database.
          </div>
        `,
        confirmText: 'Delete Student',
        confirmBtnClass: 'btn-primary',
        onConfirm: async () => {
          const res = await api('POST', '/api/admin/database/students/delete', { register_no: reg });
          if (!res.ok) {
            toast(res.data.message || 'Failed to delete student.');
            return false;
          }
          toast(`Student ${reg} deleted.`);
          dbStudentsCache = null;
          await loadDatabaseData();
          return true;
        }
      });
    }
  }

  function openFacultyModal(fac) {
    const isEdit = Boolean(fac);
    const title = isEdit ? `✏️ Edit Faculty (${esc(fac.name)})` : `➕ Add New Faculty Guide`;
    const minCap = (fac && fac.selected_count) ? fac.selected_count : 1;
    const bodyHtml = `
      <div class="modal-field">
        <label for="mFacName">Faculty Name *</label>
        <input type="text" id="mFacName" placeholder="e.g. Dr Saraswathi C" value="${esc(fac ? fac.name : '')}">
      </div>
      <div class="modal-field">
        <label for="mFacEmail">Institutional Email</label>
        <input type="email" id="mFacEmail" placeholder="e.g. saraswathic@bitsathy.ac.in" value="${esc(fac ? fac.email : '')}">
      </div>
      <div class="modal-field">
        <label for="mFacSpec">Domain / Specialization *</label>
        <input type="text" id="mFacSpec" placeholder="e.g. HR & Marketing" value="${esc(fac ? fac.specialization : '')}">
      </div>
      <div class="modal-field">
        <label for="mFacCap">Seat Capacity *</label>
        <input type="number" id="mFacCap" min="${minCap}" max="20" value="${fac ? fac.capacity : 5}">
        ${isEdit ? `
          <div style="font-size: 11.5px; color: var(--text-hint); margin-top: 2px;">
            Currently allocated: ${fac.selected_count} student(s). Capacity cannot be below ${minCap}.
          </div>
        ` : ''}
      </div>
    `;

    showModal({
      title,
      bodyHtml,
      confirmText: isEdit ? 'Save Faculty' : 'Add Faculty',
      onConfirm: async (backdrop) => {
        const name = backdrop.querySelector('#mFacName').value.trim();
        const email = backdrop.querySelector('#mFacEmail').value.trim().toLowerCase();
        const spec = backdrop.querySelector('#mFacSpec').value.trim();
        const cap = Number(backdrop.querySelector('#mFacCap').value);

        if (!name) {
          toast('Please enter the faculty name.');
          return false;
        }
        if (!cap || cap < minCap) {
          toast(`Capacity must be at least ${minCap}.`);
          return false;
        }

        const payload = {
          id: isEdit ? fac.id : null,
          name: name,
          email: email || null,
          specialization: spec,
          capacity: cap,
        };

        const res = await api('POST', '/api/admin/database/faculties/save', payload);
        if (!res.ok) {
          toast(res.data.message || 'Failed to save faculty.');
          return false;
        }

        toast(isEdit ? 'Faculty details updated!' : 'New faculty added!');
        dbFacultiesCache = null;
        await loadDatabaseData();
        const rMe = await api('GET', '/api/director/overview');
        if (rMe.ok) me.master_overview = rMe.data.master_overview;
        return true;
      }
    });
  }

  function confirmDeleteFaculty(fid, name, count = 0) {
    showModal({
      title: `🗑️ Delete Faculty`,
      bodyHtml: `
        <p style="margin: 0; color: var(--text-primary); line-height: 1.5;">
          Are you sure you want to remove <b>${esc(name)}</b> from the faculty list?
        </p>
        ${count > 0 ? `
          <div class="modal-note" style="border-left-color: var(--error); margin-top: 14px;">
            ⚠️ <b>${count} student(s)</b> are currently allocated to this faculty. Deleting this faculty will unassign their seats and allow them to choose another guide.
          </div>
        ` : `
          <div class="modal-note" style="border-left-color: var(--ok); margin-top: 14px;">
            This faculty currently has 0 allocated students and will be cleanly removed.
          </div>
        `}
      `,
      confirmText: 'Delete Faculty',
      confirmBtnClass: 'btn-primary',
      onConfirm: async () => {
        const res = await api('POST', '/api/admin/database/faculties/delete', { id: fid });
        if (!res.ok) {
          toast(res.data.message || 'Failed to delete faculty.');
          return false;
        }
        toast(`Faculty ${name} removed.`);
        dbFacultiesCache = null;
        await loadDatabaseData();
        const rMe = await api('GET', '/api/director/overview');
        if (rMe.ok) me.master_overview = rMe.data.master_overview;
        return true;
      }
    });
  }


  function renderMyAllocatedStudentsTab(container) {
    const dash = me.faculty_dashboard;
    const fac = (dash && dash.faculty) || { name: me.name, capacity: 5, selected_count: 0, remaining: 5 };
    const spec = facSpec(fac);
    const students = (dash && dash.students_selected) || [];
    const pct = fac.capacity > 0 ? Math.round((Math.max(0, fac.selected_count) / fac.capacity) * 100) : 0;

    container.innerHTML = `
      <div class="card">
        <div class="q-title" style="margin-bottom: 14px;">Your Allocation Status (${esc(fac.name)}${spec ? ` - ${esc(spec)}` : ''})</div>
        <div class="fac-stat-grid">
          <div class="fac-stat-card">
            <div class="val">${esc(fac.capacity)}</div>
            <div class="lbl">Total Seat Capacity</div>
          </div>
          <div class="fac-stat-card">
            <div class="val">${esc(fac.selected_count)}</div>
            <div class="lbl">Students Allocated</div>
          </div>
          <div class="fac-stat-card">
            <div class="val" style="color: ${fac.remaining > 0 ? 'var(--ok)' : 'var(--error)'};">${esc(fac.remaining)}</div>
            <div class="lbl">Remaining Seats</div>
          </div>
        </div>
        <div class="meter-bar" style="height: 10px; margin-bottom: 4px;">
          <div class="meter-fill ${fac.remaining <= 0 ? 'full' : ''}" style="width: ${pct}%;"></div>
        </div>
        <div class="hint" style="text-align: right; font-size: 12px; margin-top: 6px;">${pct}% capacity filled</div>
      </div>

      <div class="card">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <div class="q-title" style="margin-bottom: 0;">Students Who Selected You (${students.length})</div>
          <button class="btn-text" id="refreshMyStudentsBtn" type="button" style="padding: 4px 10px; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;">
            ${ico('refresh')} Refresh
          </button>
        </div>

        ${students.length ? `
        <div class="table-responsive">
          <table class="fac-table">
            <thead>
              <tr>
                <th style="width: 40px; text-align: center;">#</th>
                <th style="width: 140px;">Register No</th>
                <th>Student Name</th>
                <th>Student Email</th>
                <th style="width: 140px;">Selection Time</th>
              </tr>
            </thead>
            <tbody>
              ${students.map((s, idx) => `
                <tr>
                  <td style="text-align: center;"><b>${idx + 1}</b></td>
                  <td><span class="reg-chip">${esc(s.register_no)}</span></td>
                  <td><b>${esc(s.name)}</b></td>
                  <td><span style="color: var(--text-secondary);">${esc(s.email)}</span></td>
                  <td style="color: var(--text-secondary); font-size: 12px;">${esc(s.time)} IST</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>` : `
        <div class="empty-table">
          ${ico('account_circle')}
          <div style="font-size: 15px; font-weight: 500; margin-bottom: 4px;">No students have selected you yet</div>
          <div style="font-size: 13px;">When students submit their choices on the live form, they will appear here in real-time.</div>
        </div>`}
      </div>
    `;

    const refBtn = $('#refreshMyStudentsBtn');
    if (refBtn) {
      refBtn.addEventListener('click', async () => {
        refBtn.textContent = 'Refreshing…';
        const r = await api('GET', '/api/faculty/dashboard');
        if (r.ok) {
          me.faculty_dashboard = r.data;
          showDirectorDashboard('my_students');
        }
      });
    }
  }

  // ============================================================
  // REGULAR FACULTY PORTAL & DASHBOARD (Ref Second Image)
  // ============================================================
  async function showFacultyDashboard(activeTab = 'my_students') {
    stopTimers();
    root.classList.add('wide-view');

    let dash = me.faculty_dashboard;
    if (!dash) {
      const r = await api('GET', '/api/faculty/dashboard');
      if (r.ok) {
        dash = r.data;
        me.faculty_dashboard = dash;
      }
    }

    const fac = (dash && dash.faculty) || { name: me.name, capacity: 5, selected_count: 0, remaining: 5 };
    const spec = facSpec(fac);
    const students = (dash && dash.students_selected) || [];
    const pct = fac.capacity > 0 ? Math.round((Math.max(0, fac.selected_count) / fac.capacity) * 100) : 0;
    const overview = me.master_overview || [];
    const isAdmin = Boolean(me.is_admin);

    root.innerHTML = `
      <div class="title-card">
        <div class="accent"></div>
        <div class="title-body">
          <h1>Faculty Portal</h1>
          <p class="muted">Guide allocation dashboard for <b>${esc(fac.name)}</b>${spec ? ` (${esc(spec)})` : ''}. Monitor student selections in real-time.</p>
        </div>
        ${accountBar()}
      </div>

      <div class="portal-tabs">
        <button class="portal-tab ${activeTab === 'my_students' ? 'active' : ''}" id="tabFacMyStudents" type="button">
          👤 My Allocated Students (${students.length})
        </button>
        <button class="portal-tab ${activeTab === 'dept_overview' ? 'active' : ''}" id="tabFacDeptOverview" type="button">
          ${ico('list_alt')} Department Master Overview
        </button>
        ${isAdmin ? `
          <button class="portal-tab ${activeTab === 'manage_seats' ? 'active' : ''}" id="tabFacManageSeats" type="button">
            ⚙️ Manage Faculty Seats
          </button>` : ''}
      </div>

      <div id="facTabContent">
        ${activeTab === 'my_students' ? `
          <div class="card">
            <div class="q-title" style="margin-bottom: 14px;">Your Allocation Status</div>
            <div class="fac-stat-grid">
              <div class="fac-stat-card">
                <div class="val">${esc(fac.capacity)}</div>
                <div class="lbl">Total Seat Capacity</div>
              </div>
              <div class="fac-stat-card">
                <div class="val">${esc(fac.selected_count)}</div>
                <div class="lbl">Students Allocated</div>
              </div>
              <div class="fac-stat-card">
                <div class="val" style="color: ${fac.remaining > 0 ? 'var(--ok)' : 'var(--error)'};">${esc(fac.remaining)}</div>
                <div class="lbl">Remaining Seats</div>
              </div>
            </div>
            <div class="meter-bar" style="height: 10px; margin-bottom: 4px;">
              <div class="meter-fill ${fac.remaining <= 0 ? 'full' : ''}" style="width: ${pct}%;"></div>
            </div>
            <div class="hint" style="text-align: right; font-size: 12px; margin-top: 6px;">${pct}% capacity filled</div>
          </div>

          <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
              <div class="q-title" style="margin-bottom: 0;">Students Who Selected You (${students.length})</div>
              <button class="btn-text" id="refreshDashBtn" type="button" style="padding: 4px 10px; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;">
                ${ico('refresh')} Refresh
              </button>
            </div>

            ${students.length ? `
            <div class="table-responsive">
              <table class="fac-table">
                <thead>
                  <tr>
                    <th style="width: 40px; text-align: center;">#</th>
                    <th style="width: 140px;">Register No</th>
                    <th>Student Name</th>
                    <th>Student Email</th>
                    <th style="width: 140px;">Selection Time</th>
                  </tr>
                </thead>
                <tbody>
                  ${students.map((s, idx) => `
                    <tr>
                      <td style="text-align: center;"><b>${idx + 1}</b></td>
                      <td><span class="reg-chip">${esc(s.register_no)}</span></td>
                      <td><b>${esc(s.name)}</b></td>
                      <td><span style="color: var(--text-secondary);">${esc(s.email)}</span></td>
                      <td style="color: var(--text-secondary); font-size: 12px;">${esc(s.time)} IST</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>` : `
            <div class="empty-table">
              ${ico('account_circle')}
              <div style="font-size: 15px; font-weight: 500; margin-bottom: 4px;">No students have selected you yet</div>
              <div style="font-size: 13px;">When students submit their choices on the live form, they will appear here in real-time.</div>
            </div>`}
          </div>

          <div class="card" style="text-align: center; padding: 22px;">
            <div style="font-size: 14px; color: var(--text-secondary); margin-bottom: 14px;">
              Need to test the form flow or submit faculty student selections?
            </div>
            <button class="btn-primary" id="openFacultyPreviewBtn" type="button" style="display: inline-flex; align-items: center; gap: 6px; margin: 0 auto;">
              ${ico('preview')} Open Google Form Preview & Test Mode
            </button>
          </div>
        ` : activeTab === 'dept_overview' ? `
          <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
              <div class="q-title" style="margin-bottom: 0;">Department Master Overview (All Faculty)</div>
              <button class="btn-text" id="refreshMasterBtn" type="button" style="padding: 4px 10px; font-size: 13px; display: inline-flex; align-items: center; gap: 4px;">
                ${ico('refresh')} Refresh Live
              </button>
            </div>
            ${renderMasterOverviewTable(overview)}
          </div>
        ` : renderSeatAllocationCard(overview)}
      </div>
    `;

    bindSwitch();

    const cta = $('#openFacultyPreviewBtn');
    if (cta) cta.addEventListener('click', () => showFacultyPreview('select_students'));

    const tabStudents = $('#tabFacMyStudents');
    if (tabStudents) tabStudents.addEventListener('click', () => showFacultyDashboard('my_students'));

    const tabDept = $('#tabFacDeptOverview');
    if (tabDept) tabDept.addEventListener('click', async () => {
      if (!me.master_overview) {
        const r = await api('GET', '/api/director/overview');
        if (r.ok) me.master_overview = r.data.master_overview;
      }
      showFacultyDashboard('dept_overview');
    });

    const tabSeats = $('#tabFacManageSeats');
    if (tabSeats) tabSeats.addEventListener('click', async () => {
      if (!me.master_overview) {
        const r = await api('GET', '/api/director/overview');
        if (r.ok) me.master_overview = r.data.master_overview;
      }
      showFacultyDashboard('manage_seats');
    });

    if (activeTab === 'my_students') {
      const refBtn = $('#refreshDashBtn');
      if (refBtn) {
        refBtn.addEventListener('click', async () => {
          refBtn.textContent = 'Refreshing…';
          const r = await api('GET', '/api/faculty/dashboard');
          if (r.ok) {
            me.faculty_dashboard = r.data;
            showFacultyDashboard('my_students');
          }
        });
      }

      // Auto-poll dashboard every 3.5 seconds
      pollTimer = setInterval(async () => {
        if (document.hidden) return;
        const r = await api('GET', '/api/faculty/dashboard');
        if (r.ok) {
          const newCount = (r.data.students_selected || []).length;
          const oldCount = (students || []).length;
          if (newCount !== oldCount) {
            me.faculty_dashboard = r.data;
            showFacultyDashboard('my_students');
          }
        }
      }, 3500);
    } else if (activeTab === 'dept_overview') {
      const refMasterBtn = $('#refreshMasterBtn');
      if (refMasterBtn) {
        refMasterBtn.addEventListener('click', async () => {
          refMasterBtn.textContent = 'Refreshing…';
          const r = await api('GET', '/api/director/overview');
          if (r.ok) {
            me.master_overview = r.data.master_overview;
            showFacultyDashboard('dept_overview');
          }
        });
      }
    } else if (activeTab === 'manage_seats') {
      setupSeatAllocationHandlers(() => showFacultyDashboard('manage_seats'));
    }
  }

  // ============================================================
  // FACULTY PREVIEW & TEST MODES (Ref First Image)
  // ============================================================
  async function showFacultyPreview(subMode = 'select_students') {
    stopTimers();
    root.classList.add('wide-view');

    let dash = me.faculty_dashboard;
    if (!dash) {
      const r = await api('GET', '/api/faculty/dashboard');
      if (r.ok) {
        dash = r.data;
        me.faculty_dashboard = dash;
      }
    }

    root.innerHTML = `
      <div class="preview-toolbar">
        <div class="preview-toolbar-left">
          <button class="btn-text" id="exitPreviewBtn" type="button" style="display: inline-flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 500;">
            ${ico('arrow_back')} Back to Dashboard
          </button>
        </div>
        <div class="mode-tabs">
          <button class="portal-tab ${subMode === 'select_students' ? 'active' : ''}" id="tabFacultySelect" type="button">
            ${ico('list_alt')} Select Students (Faculty Data)
          </button>
          <button class="portal-tab ${subMode === 'test_mode' ? 'active' : ''}" id="tabTestMode" type="button">
            ${ico('science')} Test Mode (Student Flow)
          </button>
        </div>
      </div>
      <div id="previewContent"></div>
    `;

    $('#exitPreviewBtn').addEventListener('click', () => showFacultyDashboard('my_students'));
    $('#tabFacultySelect').addEventListener('click', () => showFacultyPreview('select_students'));
    $('#tabTestMode').addEventListener('click', () => showFacultyPreview('test_mode'));

    const container = $('#previewContent');
    if (subMode === 'select_students') {
      renderFacultyStudentSelection(container, (dash && dash.all_students) || [], (dash && dash.faculty_selections) || []);
    } else {
      renderFacultyTestMode(container);
    }
  }

  function renderFacultyStudentSelection(container, allStudents, facPicks) {
    container.innerHTML = `
      <div class="title-card">
        <div class="accent"></div>
        <div class="title-body">
          <h1>Faculty Student Selection</h1>
          <p class="muted">As a faculty guide, select the students you wish to mentor. These choices are recorded as faculty selection data in the <b>Faculty Selections</b> Google Sheet tab.</p>
        </div>
        ${accountBar()}
      </div>

      <div class="card">
        <div class="q-title">Select Student to Guide <span class="req">*</span></div>
        <div style="margin-bottom: 14px;">
          <select class="text-input" id="facStudentSelect">
            <option value="">-- Choose a student from roster --</option>
            ${allStudents.map(s => `<option value="${esc(s.register_no)}">${esc(s.register_no)} - ${esc(s.name)} (${esc(s.email)})</option>`).join('')}
          </select>
        </div>
        <button class="btn-primary" id="saveStudentChoiceBtn" type="button" style="margin-top: 8px;">
          Record Student Selection
        </button>
      </div>

      <div class="card">
        <div class="q-title">Students You Have Selected (${facPicks.length})</div>
        ${facPicks.length ? `
          <div style="margin-top: 12px;">
            ${facPicks.map(p => `
              <div class="fac-selection-item">
                <div class="info">
                  <span class="reg-chip">${esc(p.student_register_no)}</span>
                  <b>${esc(p.student_name)}</b>
                  <small style="color: var(--text-secondary); margin-left: 8px;">${esc(p.time)} IST</small>
                </div>
                <button class="btn-danger-sm delete-pick-btn" data-id="${p.id}" type="button">Remove</button>
              </div>
            `).join('')}
          </div>
        ` : `
          <div class="hint" style="margin-top: 8px;">You haven't recorded any student selections yet. Choose a student above to record your preference.</div>
        `}
      </div>
    `;

    bindSwitch();

    $('#saveStudentChoiceBtn').addEventListener('click', async () => {
      const reg = $('#facStudentSelect').value;
      if (!reg) return toast('Please select a student from the dropdown.');
      const btn = $('#saveStudentChoiceBtn');
      btn.disabled = true;
      btn.textContent = 'Saving…';

      const r = await api('POST', '/api/faculty/select-student', { register_no: reg });
      btn.disabled = false;
      btn.textContent = 'Record Student Selection';

      if (!r.ok) return toast(r.data.message || 'Error recording student selection.');
      toast('Student selection recorded successfully!');
      if (me.faculty_dashboard) me.faculty_dashboard.faculty_selections = r.data.faculty_selections;
      showFacultyPreview('select_students');
    });

    container.querySelectorAll('.delete-pick-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = Number(btn.dataset.id);
        const r = await api('POST', '/api/faculty/delete-student-selection', { id });
        if (r.ok) {
          toast('Removed student selection.');
          if (me.faculty_dashboard) me.faculty_dashboard.faculty_selections = r.data.faculty_selections;
          showFacultyPreview('select_students');
        }
      });
    });
  }

  function renderFacultyTestMode(container) {
    selectedId = null;
    container.innerHTML = `
      <div class="banner-notice">
        ${ico('science')}
        <div>
          <b>🧪 Test Mode Active (Student Flow Simulation):</b> Experience exactly how students select faculties.
          You can test selecting <b>any faculty, including yourself</b>. Test submissions do not decrement real quotas and are written to the <b>Test Responses</b> sheet tab.
        </div>
      </div>

      <div class="title-card">
        <div class="accent"></div>
        <div class="title-body">
          <h1>${esc(APP.title)}</h1>
          <p class="muted">${esc(APP.description)}</p>
          <p class="required-note">* Indicates required question</p>
        </div>
        ${accountBar()}
      </div>

      <div class="card">
        <div class="q-title">Email <span class="req">*</span></div>
        <input class="text-input" value="${esc(me.email)} (Faculty Tester)" readonly />
      </div>

      <div class="card">
        <div class="q-title">Name <span class="req">*</span></div>
        <input class="text-input" value="${esc(me.name)} (Test Mode)" readonly />
      </div>

      <div class="card">
        <div class="q-title">Register Number <span class="req">*</span></div>
        <input class="text-input" value="FACULTY-SIM" readonly />
      </div>

      <div class="card" id="facCard">
        <div class="q-title">Select your faculty <span class="req">*</span></div>
        <div class="options" id="previewOptions">
          ${faculty.map(f => {
            const spec = facSpec(f);
            const specHtml = spec ? ` <span class="fac-spec-tag">(${esc(spec)})</span>` : '';
            return `
              <label class="option" data-id="${f.id}">
                <input type="radio" name="previewFaculty" value="${f.id}" />
                <span class="radio"></span>
                <span class="name">${esc(f.name)} ${f.name === me.name ? '(You)' : ''}${specHtml}</span>
                <span class="seats">${f.remaining} seats left</span>
              </label>`;
          }).join('')}
        </div>
        <div class="q-error">${ico('error_outline')}<span id="facErrorText">This is a required question</span></div>
      </div>

      <div class="submit-area">
        <button class="btn-primary" id="testSubmitBtn" type="button" style="display: inline-flex; align-items: center; gap: 6px;">
          ${ico('science')} Submit Test Selection
        </button>
        <button class="btn-text" id="testClearBtn" type="button">Clear choice</button>
      </div>

      <div class="form-note">
        This is a safe sandbox. Real student quotas will remain 100% intact.
      </div>
    `;

    bindSwitch();

    const facCard = $('#facCard');
    const optionsBox = $('#previewOptions');
    if (optionsBox) {
      optionsBox.addEventListener('change', (e) => {
        if (e.target.name === 'previewFaculty') {
          selectedId = Number(e.target.value);
          facCard.classList.remove('has-error');
        }
      });
    }

    $('#testClearBtn').addEventListener('click', () => {
      selectedId = null;
      if (optionsBox) optionsBox.querySelectorAll('input').forEach(inp => { inp.checked = false; });
      facCard.classList.remove('has-error');
    });

    $('#testSubmitBtn').addEventListener('click', async () => {
      if (!selectedId) {
        facCard.classList.add('has-error');
        return toast('Please select a faculty member to test.');
      }
      const btn = $('#testSubmitBtn');
      btn.disabled = true;
      btn.textContent = 'Submitting Test…';

      const r = await api('POST', '/api/faculty/test-submit', { faculty_id: selectedId });
      btn.disabled = false;
      btn.textContent = 'Submit Test Selection';

      if (!r.ok) return toast(r.data.message || 'Test submission failed.');
      showTestDone(container, r.data.selection);
    });
  }

  function showTestDone(container, sel) {
    const spec = facSpec(sel.faculty);
    container.innerHTML = `
      <div class="banner-notice">
        ${ico('check_circle')}
        <div>
          <b>Test Successful!</b> Your simulation choice has been recorded in the <b>Test Responses</b> sheet tab. Real quotas are unaffected.
        </div>
      </div>

      <div class="title-card">
        <div class="accent"></div>
        <div class="title-body">
          <h1>${esc(APP.title)}</h1>
          <p class="done-note">Test response simulation confirmed.</p>
        </div>
        ${accountBar()}
      </div>

      <div class="card">
        <div class="done-tick">${ico('check_circle')} Test Simulation Confirmed</div>
        <div class="detail-row"><div class="k">Selected Faculty</div><div class="v"><b>${esc(sel.faculty)}${spec ? ` (${esc(spec)})` : ''}</b></div></div>
        <div class="detail-row"><div class="k">Tester Name</div><div class="v">${esc(sel.name)}</div></div>
        <div class="detail-row"><div class="k">Simulated Reg No</div><div class="v">${esc(sel.register_no)}</div></div>
        <div class="detail-row"><div class="k">Test Timestamp</div><div class="v">${esc(sel.time)} IST</div></div>
        <div class="detail-row"><div class="k">Simulation Ref</div><div class="v">#${esc(sel.seq)}</div></div>
      </div>

      <div class="submit-area">
        <button class="btn-primary" id="testAgainBtn" type="button" style="display: inline-flex; align-items: center; gap: 6px;">
          ${ico('science')} Test Another Selection
        </button>
        <button class="btn-text" id="testBackDashBtn" type="button">
          ← Back to Faculty Dashboard
        </button>
      </div>
    `;

    bindSwitch();
    $('#testAgainBtn').addEventListener('click', () => showFacultyPreview('test_mode'));
    $('#testBackDashBtn').addEventListener('click', () => showFacultyDashboard('my_students'));
  }

  // ============================================================
  // STUDENT FLOW (ATOMIC FCFS ALLOCATION)
  // ============================================================
  function showClosed() {
    stopTimers();
    root.classList.remove('wide-view');
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
      if (serverNow() < me.opens_at_ms - 1500) return;
      const r = await api('GET', '/api/me');
      if (r.ok && r.data.is_open) { clearInterval(openTimer); boot(); }
    }, 1000);
  }

  async function showForm(preloadedAttempt) {
    stopTimers();
    root.classList.remove('wide-view');
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
        <div class="options" id="options"></div>
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

    if (preloadedAttempt) {
      beginAttempt(preloadedAttempt);
      pollTimer = setInterval(refreshAvailability, 2500);
    } else {
      api('POST', '/api/start').then(r => {
        if (!r.ok) return handleStartError(r);
        beginAttempt(r.data);
        pollTimer = setInterval(refreshAvailability, 2500);
      });
    }
  }

  function handleStartError(r) {
    const d = r.data || {};
    if (d.code === 'already_submitted' && d.selection) return showDone(d.selection, true);
    if (r.status === 401) return showSignin('Please sign in again.');
    if (d.code === 'not_open' || d.code === 'closed') { me.is_open = false; me.reason = d.code; return showClosed(); }
    fatal(d.message || 'Could not start your selection attempt.');
  }

  function beginAttempt(att) {
    if (att) {
      expiresMs = att.expires_ms || 0;
      offset = (att.server_now || Date.now()) - Date.now();
    }
    if (timerEl && expiresMs > 0) {
      timerEl.classList.remove('hidden');
      timerEl.classList.remove('warn');
      clearInterval(tickTimer);
      tickAttempt();
      tickTimer = setInterval(tickAttempt, 500);
    }
  }

  function tickAttempt() {
    if (!expiresMs) return;
    const remaining = Math.max(0, Math.round((expiresMs - serverNow()) / 1000));
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    if (timerText) timerText.textContent = `${m}:${s < 10 ? '0' : ''}${s}`;
    if (timerEl) {
      timerEl.classList.toggle('warn', remaining <= 15);
    }
    if (remaining <= 0) {
      clearInterval(tickTimer);
      tickTimer = null;
      onTimerExpired();
    }
  }

  function onTimerExpired() {
    setLocked(true);
    const sbtn = $('#submitBtn');
    if (sbtn) {
      sbtn.disabled = true;
      sbtn.textContent = 'Timer Expired';
    }
    const banner = $('#formBanner');
    if (banner) {
      banner.innerHTML = `<div class="banner">${ico('hourglass_bottom')}<div><b>Timer expired.</b> The 60-second limit has reached. You cannot submit responses anymore.</div></div>`;
    }
    toast('Timer expired. Form is locked.');
  }

  function setLocked(locked) {
    root.querySelectorAll('#options input, #regSelect, #submitBtn, #clearBtn').forEach(el => { el.disabled = locked; });
    if (!locked) updateOptions();
  }

  function renderOptions() {
    const box = $('#options');
    if (!box) return;
    if (!faculty || !faculty.length) {
      box.innerHTML = '<div style="padding:14px;color:var(--text-secondary);font-size:13px;text-align:center;">Loading faculty choices…</div>';
      return;
    }
    box.innerHTML = faculty.map(f => {
      const spec = facSpec(f);
      const specHtml = spec ? ` <span class="fac-spec-tag">(${esc(spec)})</span>` : '';
      return `
      <label class="option" data-id="${f.id}">
        <input type="radio" name="faculty" value="${f.id}" ${selectedId === f.id ? 'checked' : ''} />
        <span class="radio"></span>
        <span class="name">${esc(f.name)}${specHtml}</span>
        <span class="seats"></span>
      </label>`;
    }).join('');

    box.addEventListener('change', (e) => {
      if (e.target.name === 'faculty') {
        selectedId = Number(e.target.value);
        markError('facCard', false);
      }
    });

    updateOptions();
  }

  function selectFaculty(id) {
    selectedId = id;
    markError('facCard', false);
    const inp = root.querySelector(`.option[data-id="${id}"] input`);
    if (inp && !inp.disabled) {
      inp.checked = true;
    }
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
      if (input) {
        input.disabled = full || submitting;
        if (selectedId === f.id) input.checked = !full;
      }
      if (seats) {
        seats.textContent = full ? 'Full' : f.remaining + (f.remaining === 1 ? ' seat left' : ' seats left');
        seats.classList.toggle('low', !full && f.remaining <= 2);
      }
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
    const hasOptions = root.querySelectorAll('#options .option').length > 0;
    const headers = (currentEtag && hasOptions) ? { 'If-None-Match': currentEtag } : {};
    const r = await api('GET', '/api/availability', undefined, headers);
    if (r.notModified) {
      if (!hasOptions && faculty && faculty.length) renderOptions();
      return;
    }
    if (r.ok && r.data.faculty) {
      faculty = r.data.faculty;
      if (r.etag) currentEtag = r.etag;
      if (!hasOptions) {
        renderOptions();
      } else {
        updateOptions();
      }
    } else if (!r.ok && !hasOptions) {
      const box = $('#options');
      if (box) {
        box.innerHTML = `<div style="padding:14px;color:var(--error);font-size:13px;text-align:center;">Could not load faculty options. <button type="button" class="btn-text" id="retryAvailBtn" style="margin-left:6px;font-size:13px;">Retry</button></div>`;
        const retryBtn = $('#retryAvailBtn');
        if (retryBtn) retryBtn.addEventListener('click', () => refreshAvailability());
      }
    }
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

  async function submit() {
    if (submitting) return;
    const reg = $('#regSelect');
    let bad = false;
    if (reg && !reg.value) { markError('regCard', true, 'This is a required question'); bad = true; }
    if (!selectedId) { markError('facCard', true, 'This is a required question'); bad = true; }
    if (bad) return;

    submitting = true;
    const btn = $('#submitBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }
    setLocked(true);

    const r = await api('POST', '/api/submit', { faculty_id: selectedId, register_no: reg ? reg.value : undefined });
    submitting = false;
    const d = r.data || {};
    if (r.ok) return showDone(d.selection, d.already);

    if (btn) btn.textContent = 'Submit';

    if (d.code === 'already_submitted' && d.selection) return showDone(d.selection, true);
    if (r.status === 401) return showSignin('Your session ended. Please sign in again.');
    if (d.code === 'not_open' || d.code === 'closed') { me.is_open = false; me.reason = d.code; return showClosed(); }
    if (d.code === 'timer_expired') {
      onTimerExpired();
      return;
    }
    if (d.code === 'faculty_full') {
      if (d.faculty) faculty = d.faculty;
      selectedId = null;
      root.querySelectorAll('#options input').forEach(i => { i.checked = false; });
      setLocked(false);
      if (btn) btn.disabled = false;
      updateOptions();
      markError('facCard', true, d.message);
      toast(d.message);
      return;
    }
    setLocked(false);
    if (btn) btn.disabled = false;
    updateOptions();
    const msg = d.message || 'Something went wrong. Please try again.';
    toast(msg);
    const b = $('#formBanner');
    if (b) b.innerHTML = `<div class="banner">${ico('error')}<div>${esc(msg)}</div></div>`;
  }

  function showDone(sel, already) {
    stopTimers();
    root.classList.remove('wide-view');
    me.selection = sel;
    const isSuganesan = (me.register_no === '7376257MB144') || ((me.email || '').toLowerCase().includes('suganesan'));

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
        <div class="detail-row"><div class="k">Faculty</div><div class="v"><b>${esc(sel.faculty)}${facSpec(sel.faculty) ? ` (${esc(facSpec(sel.faculty))})` : ''}</b></div></div>
        <div class="detail-row"><div class="k">Name</div><div class="v">${esc(sel.name)}</div></div>
        <div class="detail-row"><div class="k">Register number</div><div class="v">${esc(sel.register_no)}</div></div>
        <div class="detail-row"><div class="k">Submitted at</div><div class="v">${esc(sel.time)} IST</div></div>
        <div class="detail-row"><div class="k">Response no.</div><div class="v">#${esc(sel.seq)}</div></div>
      </div>
      <div class="form-note">Selections can't be changed. Contact your coordinator if something is wrong.</div>`;
    bindSwitch();

    // Fire non-blocking background sync to Google Sheets (response already rendered to user)
    api('POST', '/api/sync-mine').catch(() => {});

    /*
    // Reset selection test button (hidden from UI, preserved in code as comments):
    // ${isSuganesan ? `
    // <div style="margin-top: 20px; padding-top: 16px; border-top: 1px dashed var(--border); text-align: center;">
    //   <button class="btn-text" id="resetMyTestDataBtn" type="button" style="color: #d93025; font-weight: 500; font-size: 13px; display: inline-flex; align-items: center; gap: 6px; margin: 0 auto;">
    //     ${ico('delete')} Reset My Selection (7376257MB144) to Test Again
    //   </button>
    //   <div class="hint" style="font-size: 12px; margin-top: 4px;">Clicking this resets your test submission so you can test the form flow again.</div>
    // </div>` : ''}

    const resetSelfBtn = $('#resetMyTestDataBtn');
    if (resetSelfBtn) {
      resetSelfBtn.addEventListener('click', async () => {
        resetSelfBtn.disabled = true;
        resetSelfBtn.textContent = 'Resetting…';
        const r = await api('POST', '/api/admin/reset-user', { register_no: '7376257MB144', email: me.email });
        if (!r.ok) {
          resetSelfBtn.disabled = false;
          resetSelfBtn.textContent = 'Reset Failed. Try again';
          return toast(r.data.message || 'Failed to reset.');
        }
        toast('Your test selection was cleared! Returning to selection form…');
        me.selection = null;
        window.INITIAL_STATE = null;
        setTimeout(() => boot(), 400);
      });
    }
    */
  }

  // Keyboard navigation (1-9 and 0 for #10)
  document.addEventListener('keydown', (e) => {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT')) return;
    let idx = -1;
    if (e.key >= '1' && e.key <= '9') {
      idx = Number(e.key) - 1;
    } else if (e.key === '0') {
      idx = 9;
    }
    if (idx >= 0 && faculty && faculty[idx] && faculty[idx].remaining > 0 && !submitting) {
      selectFaculty(faculty[idx].id);
    }
  });

  // Page visibility awareness
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      clearInterval(pollTimer);
      pollTimer = null;
    } else {
      if (me && me.role === 'director') {
        api('GET', '/api/director/overview').then(r => {
          if (r.ok) { me.master_overview = r.data.master_overview; }
        });
      } else if (me && me.role === 'faculty') {
        api('GET', '/api/faculty/dashboard').then(r => {
          if (r.ok) { me.faculty_dashboard = r.data; showFacultyDashboard(); }
        });
      } else {
        refreshAvailability();
        if (!pollTimer && !submitting && $('#options')) {
          pollTimer = setInterval(refreshAvailability, 2500);
        }
      }
    }
  });

  boot();
})();
