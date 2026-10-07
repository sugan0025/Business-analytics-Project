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
  let expired = false;
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
      const etag = res.headers.get('ETag') || '';
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
    timerEl.classList.add('hidden');
    timerEl.classList.remove('warn');
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
    const isFac = me && me.role === 'faculty';
    return `
      <div class="account-bar">
        ${ico('account_circle')}
        <div class="who">
          <b>${esc(me.name || me.email)}</b>
          <small>${esc(me.email)}${isFac ? ' · Faculty Portal' : ' · Responses recorded to class roster'}</small>
        </div>
        ${isFac ? `<button class="preview-icon-btn" id="openPreviewBtn" type="button" title="Preview Form">${ico('preview')} Preview</button>` : ''}
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
    const prevBtn = $('#openPreviewBtn');
    if (prevBtn) {
      prevBtn.addEventListener('click', () => showFacultyPreview('select_students'));
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
    expired = false; submitting = false; selectedId = null;
    me = state;
    offset = me.server_now - Date.now();
    if (me.faculty && me.faculty.length) {
      faculty = me.faculty;
      if (me.etag) currentEtag = me.etag;
    }
    if (!me.signed_in) return showSignin();
    if (me.role === 'faculty') return showFacultyDashboard();
    if (me.selection) return showDone(me.selection, false);
    if (!me.is_open) return showClosed();
    return showForm(me.attempt);
  }

  // ---------- boot ----------
  async function boot() {
    stopTimers();
    expired = false; submitting = false; selectedId = null;

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
  function showSignin(error) {
    stopTimers();
    root.innerHTML = titleCard() + `
      <div class="card">
        <div class="q-title">Sign in to continue</div>
        <div class="signin-box">
          <div id="gbtn"></div>
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
    }, 80);
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
  // FACULTY PORTAL & DASHBOARD
  // ============================================================
  async function showFacultyDashboard() {
    stopTimers();
    let dash = me.faculty_dashboard;
    if (!dash) {
      const r = await api('GET', '/api/faculty/dashboard');
      if (r.ok) {
        dash = r.data;
        me.faculty_dashboard = dash;
      }
    }

    const fac = (dash && dash.faculty) || { name: me.name, capacity: 4, selected_count: 0, remaining: 4 };
    const students = (dash && dash.students_selected) || [];
    const pct = fac.capacity > 0 ? Math.round((Math.max(0, fac.selected_count) / fac.capacity) * 100) : 0;

    root.innerHTML = `
      <div class="title-card">
        <div class="accent"></div>
        <div class="title-body">
          <h1>Faculty Portal</h1>
          <p class="muted">Guide allocation overview for <b>${esc(fac.name)}</b>. Monitor student selections in real-time.</p>
        </div>
        ${accountBar()}
      </div>

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
                <th>#</th>
                <th>Register No</th>
                <th>Student Name</th>
                <th>Student Email</th>
                <th>Selection Time</th>
              </tr>
            </thead>
            <tbody>
              ${students.map((s, idx) => `
                <tr>
                  <td><b>${idx + 1}</b></td>
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
        <button class="btn-primary" id="openPreviewCta" type="button" style="display: inline-flex; align-items: center; gap: 6px; margin: 0 auto;">
          ${ico('preview')} Open Google Form Preview & Test Mode
        </button>
      </div>
    `;

    bindSwitch();
    const cta = $('#openPreviewCta');
    if (cta) cta.addEventListener('click', () => showFacultyPreview('select_students'));

    const refBtn = $('#refreshDashBtn');
    if (refBtn) {
      refBtn.addEventListener('click', async () => {
        refBtn.textContent = 'Refreshing…';
        const r = await api('GET', '/api/faculty/dashboard');
        if (r.ok) {
          me.faculty_dashboard = r.data;
          showFacultyDashboard();
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
          showFacultyDashboard();
        }
      }
    }, 3500);
  }

  // ============================================================
  // FACULTY PREVIEW & TEST MODES
  // ============================================================
  async function showFacultyPreview(subMode = 'select_students') {
    stopTimers();
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
          <button class="exit-btn" id="exitPreviewBtn" type="button">
            ${ico('arrow_back')} Back to Dashboard
          </button>
        </div>
        <div class="mode-tabs">
          <button class="mode-tab ${subMode === 'select_students' ? 'active' : ''}" id="tabFacultySelect" type="button">
            ${ico('list_alt')} Select Students (Faculty Data)
          </button>
          <button class="mode-tab ${subMode === 'test_mode' ? 'active' : ''}" id="tabTestMode" type="button">
            ${ico('science')} Test Mode (Student Flow)
          </button>
        </div>
      </div>
      <div id="previewContent"></div>
    `;

    $('#exitPreviewBtn').addEventListener('click', () => showFacultyDashboard());
    $('#tabFacultySelect').addEventListener('click', () => showFacultyPreview('select_students'));
    $('#tabTestMode').addEventListener('click', () => showFacultyPreview('test_mode'));

    const container = $('#previewContent');
    if (subMode === 'select_students') {
      renderFacultyStudentSelection(container, dash.all_students || [], dash.faculty_selections || []);
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
        <div class="search-box">
          ${ico('search')}
          <input class="search-input" id="testFacSearch" placeholder="Search faculty name…" autocomplete="off" />
        </div>
        <div class="options" id="options" role="radiogroup" aria-label="Faculty"></div>
        <div class="q-error">${ico('error_outline')}<span id="facErrorText">This is a required question</span></div>
      </div>

      <div class="submit-area">
        <button class="btn-primary" id="testSubmitBtn" type="button">Submit Test Selection</button>
        <button class="btn-text" id="testClearBtn" type="button">Clear choice</button>
      </div>

      <div class="form-note">
        This is a safe sandbox. Real student quotas will remain 100% intact.
      </div>
    `;

    bindSwitch();

    // Render all faculty options for testing (none disabled!)
    const box = $('#options');
    box.innerHTML = faculty.map((f, idx) => `
      <div class="option ${selectedId === f.id ? 'selected' : ''}" data-id="${f.id}" role="radio" aria-checked="${selectedId === f.id}">
        <input type="radio" name="faculty" value="${f.id}" ${selectedId === f.id ? 'checked' : ''} />
        <div class="option-main">
          <span class="key-badge">${idx === 9 ? '0' : idx + 1}</span>
          <span class="radio"></span>
          <span class="name">${esc(f.name)} ${f.name === me.name ? '(You)' : ''}</span>
          <span class="seats-badge">${f.remaining} seats left</span>
        </div>
        <div class="meter-row">
          <div class="meter-bar"><div class="meter-fill" style="width: ${Math.round(((f.capacity - f.remaining) / f.capacity) * 100)}%;"></div></div>
          <span class="meter-text">${f.capacity - f.remaining}/${f.capacity} taken</span>
        </div>
      </div>
    `).join('');

    box.addEventListener('click', (e) => {
      const opt = e.target.closest('.option');
      if (!opt) return;
      const fid = Number(opt.dataset.id);
      selectedId = fid;
      root.querySelectorAll('#options .option').forEach(el => {
        const isSel = Number(el.dataset.id) === fid;
        el.classList.toggle('selected', isSel);
        const inp = el.querySelector('input');
        if (inp) inp.checked = isSel;
      });
      markError('facCard', false);
    });

    const sInp = $('#testFacSearch');
    if (sInp) {
      sInp.addEventListener('input', () => {
        const q = sInp.value.trim().toLowerCase();
        root.querySelectorAll('#options .option').forEach(el => {
          const name = (el.querySelector('.name') || {}).textContent || '';
          el.style.display = (!q || name.toLowerCase().includes(q)) ? '' : 'none';
        });
      });
    }

    $('#testClearBtn').addEventListener('click', () => {
      selectedId = null;
      root.querySelectorAll('#options .option').forEach(el => {
        el.classList.remove('selected');
        const inp = el.querySelector('input');
        if (inp) inp.checked = false;
      });
    });

    $('#testSubmitBtn').addEventListener('click', async () => {
      if (!selectedId) {
        markError('facCard', true, 'Please select a faculty member to test.');
        return;
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
        <div class="detail-row"><div class="k">Selected Faculty</div><div class="v"><b>${esc(sel.faculty)}</b></div></div>
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
          Back to Faculty Dashboard
        </button>
      </div>
    `;

    bindSwitch();
    $('#testAgainBtn').addEventListener('click', () => showFacultyPreview('test_mode'));
    $('#testBackDashBtn').addEventListener('click', () => showFacultyDashboard());
  }

  // ============================================================
  // STUDENT FLOW (ATOMIC FCFS ALLOCATION)
  // ============================================================
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
      if (serverNow() < me.opens_at_ms - 1500) return;
      const r = await api('GET', '/api/me');
      if (r.ok && r.data.is_open) { clearInterval(openTimer); boot(); }
    }, 1000);
  }

  async function showForm(preloadedAttempt) {
    stopTimers();
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
        <div class="search-box">
          ${ico('search')}
          <input class="search-input" id="facSearch" placeholder="Quick search faculty name…" autocomplete="off" />
        </div>
        <div class="options" id="options" role="radiogroup" aria-label="Faculty"></div>
        <div class="q-error">${ico('error_outline')}<span id="facErrorText">This is a required question</span></div></div>
      <div class="submit-area">
        <button class="btn-primary" id="submitBtn" type="button">Submit</button>
        <button class="btn-text" id="clearBtn" type="button">Clear form</button>
      </div>
      <div class="form-note">Seats update live. Once a faculty is full it can't be selected. You can't change your choice after submitting.</div>
      <div class="sticky-bar" id="stickyBar">
        <div class="sticky-info">
          <div class="sticky-label">Selected Choice</div>
          <div class="sticky-name" id="stickyName">None</div>
        </div>
        <button class="sticky-btn" id="stickySubmitBtn" type="button">Submit Selection</button>
      </div>`;

    bindSwitch();
    $('#submitBtn').addEventListener('click', submit);
    const stickyBtn = $('#stickySubmitBtn');
    if (stickyBtn) stickyBtn.addEventListener('click', submit);
    $('#clearBtn').addEventListener('click', clearForm);

    const regSel = $('#regSelect');
    if (regSel) regSel.addEventListener('change', () => {
      const hit = (me.roster || []).find(r => r.register_no === regSel.value);
      $('#nameField').value = hit ? hit.name : '';
      markError('regCard', false);
    });

    const searchInput = $('#facSearch');
    if (searchInput) {
      const applyFilter = () => {
        const q = searchInput.value.trim().toLowerCase();
        root.querySelectorAll('#options .option').forEach(el => {
          const name = (el.querySelector('.name') || {}).textContent || '';
          el.style.display = (!q || name.toLowerCase().includes(q)) ? '' : 'none';
        });
      };
      searchInput.addEventListener('input', applyFilter);
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          searchInput.value = '';
          applyFilter();
          searchInput.blur();
        }
      });
    }

    if (faculty && faculty.length) {
      renderOptions();
    }

    if (preloadedAttempt) {
      beginAttempt(preloadedAttempt);
      pollTimer = setInterval(refreshAvailability, 2500);
    } else {
      const r = await api('POST', '/api/start');
      if (!r.ok) return handleStartError(r);
      beginAttempt(r.data);
      pollTimer = setInterval(refreshAvailability, 2500);
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
    expiresMs = att.expires_ms;
    offset = att.server_now - Date.now();
    timerEl.classList.remove('hidden');
    updateTimer();
    clearInterval(tickTimer);
    tickTimer = setInterval(updateTimer, 250);
  }

  function updateTimer() {
    const msLeft = expiresMs - serverNow();
    if (msLeft <= 0) {
      timerText.textContent = '0:00';
      timerEl.classList.add('warn');
      onExpired();
      return;
    }
    const totalSec = Math.ceil(msLeft / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    timerText.textContent = `${m}:${s < 10 ? '0' : ''}${s}`;
    timerEl.classList.toggle('warn', totalSec <= 10);
  }

  function setLocked(locked) {
    root.querySelectorAll('#options input, #regSelect, #submitBtn, #clearBtn, #stickySubmitBtn, #facSearch').forEach(el => { el.disabled = locked; });
    if (!locked) updateOptions();
  }

  function onExpired() {
    expired = true;
    clearInterval(tickTimer);
    setLocked(true);
    const sticky = $('#stickyBar');
    if (sticky) sticky.classList.remove('show');
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

  function renderOptions() {
    const box = $('#options');
    if (!box) return;
    box.innerHTML = faculty.map((f, idx) => `
      <div class="option ${selectedId === f.id ? 'selected' : ''}" data-id="${f.id}" role="radio" aria-checked="${selectedId === f.id}">
        <input type="radio" name="faculty" value="${f.id}" ${selectedId === f.id ? 'checked' : ''} />
        <div class="option-main">
          <span class="key-badge" title="Shortcut key: ${idx === 9 ? '0' : idx + 1}">${idx === 9 ? '0' : idx + 1}</span>
          <span class="radio"></span>
          <span class="name">${esc(f.name)}</span>
          <span class="seats-badge"></span>
        </div>
        <div class="meter-row">
          <div class="meter-bar"><div class="meter-fill"></div></div>
          <span class="meter-text"></span>
        </div>
      </div>`).join('');

    box.addEventListener('click', (e) => {
      const opt = e.target.closest('.option');
      if (!opt || opt.classList.contains('disabled') || expired || submitting) return;
      selectFaculty(Number(opt.dataset.id));
    });
    updateOptions();
  }

  function selectFaculty(id) {
    selectedId = id;
    markError('facCard', false);
    root.querySelectorAll('#options .option').forEach(el => {
      const isSel = Number(el.dataset.id) === id;
      el.classList.toggle('selected', isSel);
      const inp = el.querySelector('input');
      if (inp) inp.checked = isSel;
    });
    const f = faculty.find(item => item.id === id);
    const sticky = $('#stickyBar');
    if (sticky && f) {
      $('#stickyName').textContent = f.name;
      sticky.classList.add('show');
    }
  }

  function updateOptions() {
    let lostChoice = null;
    faculty.forEach(f => {
      const row = root.querySelector(`.option[data-id="${f.id}"]`);
      if (!row) return;
      const full = f.remaining <= 0;
      const isSel = selectedId === f.id;
      const input = row.querySelector('input');
      const badge = row.querySelector('.seats-badge');
      const meterFill = row.querySelector('.meter-fill');
      const meterText = row.querySelector('.meter-text');

      row.classList.toggle('disabled', full);
      row.classList.toggle('selected', isSel && !full);
      if (input) {
        input.disabled = full || expired || submitting;
        input.checked = isSel;
      }
      if (badge) {
        badge.textContent = full ? 'Full' : f.remaining + (f.remaining === 1 ? ' seat left' : ' seats left');
        badge.className = 'seats-badge' + (full ? ' full' : (!full && f.remaining <= 2 ? ' low' : ''));
      }
      if (meterFill && meterText) {
        const filled = f.capacity - f.remaining;
        const pct = Math.round((Math.max(0, filled) / f.capacity) * 100);
        meterFill.style.width = pct + '%';
        meterFill.className = 'meter-fill' + (full ? ' full' : (!full && f.remaining <= 2 ? ' low' : ''));
        meterText.textContent = `${Math.max(0, filled)}/${f.capacity} taken`;
      }
      if (full && selectedId === f.id) { lostChoice = f; }
    });
    if (lostChoice) {
      selectedId = null;
      const sticky = $('#stickyBar');
      if (sticky) sticky.classList.remove('show');
      root.querySelectorAll('#options .option').forEach(i => {
        i.classList.remove('selected');
        const inp = i.querySelector('input');
        if (inp) inp.checked = false;
      });
      markError('facCard', true, `${lostChoice.name} just filled up. Please choose another.`);
    }
  }

  async function refreshAvailability() {
    if (submitting || !$('#options')) return;
    const r = await api('GET', '/api/availability', undefined, currentEtag ? { 'If-None-Match': currentEtag } : {});
    if (r.notModified) return;
    if (r.ok && r.data.faculty) {
      faculty = r.data.faculty;
      if (r.etag) currentEtag = r.etag;
      updateOptions();
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
    const sticky = $('#stickyBar');
    if (sticky) sticky.classList.remove('show');
    root.querySelectorAll('#options .option').forEach(i => {
      i.classList.remove('selected');
      const inp = i.querySelector('input');
      if (inp) inp.checked = false;
    });
    const reg = $('#regSelect'); if (reg) { reg.value = ''; $('#nameField').value = ''; }
    markError('facCard', false); markError('regCard', false);
  }

  async function submit() {
    if (submitting || expired) return;
    const reg = $('#regSelect');
    let bad = false;
    if (reg && !reg.value) { markError('regCard', true, 'This is a required question'); bad = true; }
    if (!selectedId) { markError('facCard', true, 'This is a required question'); bad = true; }
    if (bad) return;

    submitting = true;
    const btn = $('#submitBtn');
    const stickyBtn = $('#stickySubmitBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }
    if (stickyBtn) { stickyBtn.disabled = true; stickyBtn.textContent = 'Submitting…'; }
    setLocked(true);

    const r = await api('POST', '/api/submit', { faculty_id: selectedId, register_no: reg ? reg.value : undefined });
    submitting = false;
    const d = r.data || {};
    if (r.ok) return showDone(d.selection, d.already);

    if (btn) btn.textContent = 'Submit';
    if (stickyBtn) { stickyBtn.disabled = false; stickyBtn.textContent = 'Submit Selection'; }

    if (d.code === 'already_submitted' && d.selection) return showDone(d.selection, true);
    if (r.status === 401) return showSignin('Your session ended. Please sign in again.');
    if (d.code === 'not_open' || d.code === 'closed') { me.is_open = false; me.reason = d.code; return showClosed(); }
    if (d.code === 'timer_expired') { setLocked(false); onExpired(); return; }
    if (d.code === 'faculty_full') {
      if (d.faculty) faculty = d.faculty;
      selectedId = null;
      const sticky = $('#stickyBar');
      if (sticky) sticky.classList.remove('show');
      root.querySelectorAll('#options .option').forEach(i => {
        i.classList.remove('selected');
        const inp = i.querySelector('input');
        if (inp) inp.checked = false;
      });
      setLocked(expired);
      if (btn) btn.disabled = expired;
      updateOptions();
      markError('facCard', true, d.message);
      toast(d.message);
      return;
    }
    setLocked(expired);
    if (btn) btn.disabled = expired;
    updateOptions();
    const msg = d.message || 'Something went wrong. Please try again.';
    toast(msg);
    const b = $('#formBanner');
    if (b) b.innerHTML = `<div class="banner">${ico('error')}<div>${esc(msg)}</div></div>`;
  }

  function showDone(sel, already) {
    stopTimers();
    const sticky = $('#stickyBar');
    if (sticky) sticky.classList.remove('show');
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

  // Keyboard navigation (1-9 and 0 for #10)
  document.addEventListener('keydown', (e) => {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT')) return;
    let idx = -1;
    if (e.key >= '1' && e.key <= '9') {
      idx = Number(e.key) - 1;
    } else if (e.key === '0') {
      idx = 9;
    }
    if (idx >= 0 && faculty && faculty[idx] && faculty[idx].remaining > 0 && !submitting && !expired) {
      selectFaculty(faculty[idx].id);
    }
  });

  // Page visibility awareness
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      clearInterval(pollTimer);
      pollTimer = null;
    } else {
      if (me && me.role === 'faculty') {
        api('GET', '/api/faculty/dashboard').then(r => {
          if (r.ok) { me.faculty_dashboard = r.data; showFacultyDashboard(); }
        });
      } else {
        refreshAvailability();
        if (!pollTimer && !submitting && !expired && $('#options')) {
          pollTimer = setInterval(refreshAvailability, 2500);
        }
      }
    }
  });

  boot();
})();
