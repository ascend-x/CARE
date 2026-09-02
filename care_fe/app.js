const API = window.location.origin;
let currentUser = null;
let currentPage = 'dashboard';
let currentPatientId = null;
let appConfig = { hospital_name: 'CARE EMR', hospital_id: '' };

const storage = {
  get token() { return localStorage.getItem('care_access_token'); },
  set token(v) { v ? localStorage.setItem('care_access_token', v) : localStorage.removeItem('care_access_token'); },
  get refresh() { return localStorage.getItem('care_refresh_token'); },
  set refresh(v) { v ? localStorage.setItem('care_refresh_token', v) : localStorage.removeItem('care_refresh_token'); },
};

function showToast(msg, type='success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span style="font-size: 1.2rem;">${type==='success'?'✅':'❌'}</span> <span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (storage.token && !opts.noAuth) headers['Authorization'] = `Bearer ${storage.token}`;
  
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined
  });

  if (res.status === 401 && storage.refresh && !opts._retry) {
    try {
      const r = await fetch(`${API}/api/v1/auth/token/refresh/`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({refresh: storage.refresh})
      });
      if (r.ok) {
        const d = await r.json();
        storage.token = d.access; storage.refresh = d.refresh;
        return api(path, {...opts, _retry: true});
      }
    } catch(e) {}
    logout();
    return null;
  }

  if (!res.ok) {
    const e = await res.json().catch(()=>({}));
    throw new Error(e.detail || e.error || `Request failed (${res.status})`);
  }
  return res.json();
}

async function login(username, password) {
  const data = await api('/api/v1/auth/login/', { method: 'POST', body: { username, password }, noAuth: true });
  storage.token = data.access; storage.refresh = data.refresh;
  currentUser = await api('/api/v1/users/me/');
  render();
}

function logout() {
  storage.token = null; storage.refresh = null; currentUser = null;
  render();
}

// ─── Rendering Engine ───
function render() {
  const app = document.getElementById('app');
  if (!storage.token || !currentUser) {
    app.innerHTML = renderLogin();
    bindLogin();
    return;
  }
  app.innerHTML = renderSidebar() + `<div class="main fade-in" id="main-content"></div>`;
  bindSidebar();
  navigateTo(currentPage);
}

function renderLogin() {
  return `
    <div class="login-wrap">
      <div class="login-box fade-in">
        <div style="text-align:center; margin-bottom:24px;">
          <div class="logo-icon" style="margin: 0 auto; width: 64px; height: 64px; font-size: 32px; border-radius: 16px;">C</div>
        </div>
        <h2 style="text-align:center; font-size:1.8rem; font-weight:800; margin-bottom:8px;">${appConfig.hospital_name}</h2>
        <p style="text-align:center; color:var(--text-muted); margin-bottom:32px;">Clinical EMR Dashboard</p>
        <div id="login-error" style="display:none; padding:12px; border-radius:8px; background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.2); color:var(--danger); margin-bottom:20px; font-size:0.9rem;"></div>
        <form id="login-form">
          <div class="form-group"><label class="form-label">Username</label><input class="form-input" id="login-user" value="admin" required></div>
          <div class="form-group"><label class="form-label">Password</label><input class="form-input" id="login-pass" type="password" value="admin" required></div>
          <button class="btn btn-primary" type="submit" style="width:100%; padding:14px; font-size:1rem;" id="login-btn">Secure Login</button>
        </form>
        <p style="text-align:center; margin-top:20px; font-size:0.8rem; color:var(--text-muted);">Defaults: admin/admin or dr-shivani/Coronasafe@123</p>
      </div>
    </div>`;
}

function bindLogin() {
  const form = document.getElementById('login-form');
  if (!form) return;
  form.onsubmit = async (e) => {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    const errEl = document.getElementById('login-error');
    btn.innerHTML = '<span class="spinner"></span> Authenticating...'; btn.disabled = true;
    errEl.style.display = 'none';
    try {
      await login(document.getElementById('login-user').value, document.getElementById('login-pass').value);
    } catch(err) {
      errEl.textContent = err.message; errEl.style.display = 'block';
      btn.innerHTML = 'Secure Login'; btn.disabled = false;
    }
  };
}

function renderSidebar() {
  const nav = [
    {id:'dashboard', icon:'•', label:'Dashboard'},
    {id:'patients', icon:'•', label:'Patients'},
    {id:'medgemma', icon:'•', label:'Clinical Analytics'},
    {id:'chat', icon:'•', label:'Clinical Assistant'},
    {id:'consent', icon:'•', label:'Consent Mgmt'},
    {id:'cross_hospital', icon:'•', label:'UHI Network'},
    {id:'audit', icon:'•', label:'Audit Log'},
  ];
  return `
    <aside class="sidebar">
      <div class="sidebar-logo"><div class="logo-icon">C</div><h1>${appConfig.hospital_name}</h1></div>
      <div class="sidebar-nav">
        ${nav.map(n => `<div class="nav-item ${currentPage===n.id?'active':''}" data-page="${n.id}"><span class="icon">${n.icon}</span>${n.label}</div>`).join('')}
      </div>
      <div class="sidebar-footer">
        <div class="user-badge">
          <div class="user-avatar">${(currentUser?.first_name||'U')[0]}</div>
          <div class="user-info">
            <div class="name">${currentUser?.first_name||''} ${currentUser?.last_name||''}</div>
            <div class="role">${currentUser?.user_type||''}</div>
          </div>
          <button class="btn-logout" onclick="logout()" title="Logout">✕</button>
        </div>
      </div>
    </aside>`;
}

function bindSidebar() {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.onclick = () => navigateTo(el.dataset.page);
  });
}

function navigateTo(page, params = {}) {
  currentPage = page;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.page===page));
  const main = document.getElementById('main-content');
  if (!main) return;
  main.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100%;"><span class="spinner" style="width:40px;height:40px;"></span></div>';
  
  const pages = {
    dashboard: renderDashboard,
    patients: renderPatients,
    patient_detail: () => renderPatientDetail(params.id),
    new_encounter: () => renderNewEncounter(params.id),
    medgemma: renderMedGemma,
    chat: renderChat,
    consent: renderConsent,
    cross_hospital: (el) => renderCrossHospital(el, params.abha),
    audit: renderAudit
  };
  
  setTimeout(() => {
    if(pages[page]) pages[page](main);
    else renderDashboard(main);
  }, 100); // slight delay for smooth transition
}

// ─── Dashboard ───
async function renderDashboard(el) {
  try {
    const stats = await api('/api/v1/dashboard/stats/');
    el.innerHTML = `
      <div class="page-header">
        <div><h2>Dashboard</h2><p>Overview of clinical operations</p></div>
      </div>
      <div class="stats-grid fade-in">
        <div class="stat-card purple"><div class="stat-value">${stats.patient_count}</div><div class="stat-label">Active Patients</div></div>
        <div class="stat-card green"><div class="stat-value">${stats.encounter_count}</div><div class="stat-label">Total Encounters</div></div>
        <div class="stat-card amber"><div class="stat-value">${stats.report_count}</div><div class="stat-label">Diagnostic Reports</div></div>
        <div class="stat-card blue"><div class="stat-value">${stats.analysis_count}</div><div class="stat-label">Analyses Run</div></div>
      </div>
      <div class="card fade-in" style="animation-delay: 0.1s;">
        <div class="card-header"><h3 class="card-title">Key Metrics</h3></div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Date</th><th>Patient</th><th>Complaint</th><th>Diagnosis</th><th>Status</th></tr></thead>
            <tbody>
              ${stats.recent_encounters.length ? stats.recent_encounters.map(e => `
                <tr>
                  <td>${new Date(e.created_date).toLocaleDateString()}</td>
                  <td><code style="font-size:0.8rem;background:var(--bg-glass);padding:2px 6px;border-radius:4px;">${e.patient_id.slice(0,8)}...</code></td>
                  <td>${e.chief_complaint || '—'}</td>
                  <td>${Array.isArray(e.diagnosis) && e.diagnosis.length ? e.diagnosis.map(d=>`<span class="badge badge-neutral">${d}</span>`).join(' ') : '—'}</td>
                  <td><span class="badge ${e.status==='completed'?'badge-success':'badge-warning'}">${e.status}</span></td>
                </tr>
              `).join('') : '<tr><td colspan="5" class="empty-state">No recent encounters</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>`;
  } catch(e) {
    el.innerHTML = `<div class="card"><p style="color:var(--danger)">Failed to load dashboard: ${e.message}</p></div>`;
  }
}

// ─── Patients List ───
async function renderPatients(el) {
  el.innerHTML = `
    <div class="page-header">
      <div><h2>Patients</h2><p>Patient directory and records</p></div>
      <button class="btn btn-primary" onclick="alert('Add Patient flow not fully implemented in mock')">+ New Patient</button>
    </div>
    <div id="patients-content"><div style="text-align:center;padding:40px;"><span class="spinner"></span></div></div>`;
    
  try {
    const [localData, uhiData] = await Promise.all([
      api('/api/v1/patient/'),
      api('/api/v1/cross_hospital/consented_patients/').catch(() => ({ consented_patients: [] }))
    ]);
    
    let allPatients = [...(localData.results || [])];
    const localAbhas = new Set(allPatients.map(p => p.meta?.abha_id));
    
    if (uhiData.consented_patients) {
      uhiData.consented_patients.forEach(abha => {
        if (!localAbhas.has(abha)) {
          allPatients.push({
            is_uhi: true,
            external_id: 'uhi-' + abha,
            name: 'UHI Consented Patient',
            meta: { abha_id: abha },
            gender: 'Unknown',
            date_of_birth: '—',
            blood_group: '—'
          });
        }
      });
    }

    if (!allPatients.length) {
      document.getElementById('patients-content').innerHTML = '<div class="empty-state"><div class="icon"></div><h3>No patients found</h3></div>';
      return;
    }
    document.getElementById('patients-content').innerHTML = `
      <div class="card fade-in">
        <div class="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>ABHA ID</th><th>Gender</th><th>DOB</th><th>Blood Group</th><th>Action</th></tr></thead>
            <tbody>
              ${allPatients.map(p => `
                <tr>
                  <td style="font-weight:600; color:var(--text-primary);">
                    ${p.name}
                    ${p.is_uhi ? '<span class="badge badge-info" style="margin-left:8px;">UHI Network</span>' : ''}
                  </td>
                  <td><code style="background:var(--bg-glass);padding:4px 8px;border-radius:6px;font-size:0.85rem;color:var(--accent);">${p.meta?.abha_id||'—'}</code></td>
                  <td style="text-transform:capitalize;">${p.gender}</td>
                  <td>${p.date_of_birth||'—'}</td>
                  <td><span class="badge badge-danger">${p.blood_group||'—'}</span></td>
                  <td>
                    ${p.is_uhi 
                      ? `<button class="btn btn-success btn-sm" onclick="navigateTo('cross_hospital', {abha: '${p.meta.abha_id}'})">View UHI Records</button>`
                      : `<button class="btn btn-outline btn-sm" onclick="navigateTo('patient_detail', {id: '${p.external_id}'})">View EMR</button>`
                    }
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>`;
  } catch(e) {
    document.getElementById('patients-content').innerHTML = `<div class="card"><p style="color:var(--danger)">${e.message}</p></div>`;
  }
}

// ─── Patient Detail (Full EMR) ───
async function renderPatientDetail(id) {
  currentPatientId = id;
  const main = document.getElementById('main-content');
  try {
    const data = await api(`/api/v1/patient/${id}/detail/`);
    const p = data.patient;
    
    // Header
    let html = `
      <div style="display:flex; align-items:center; gap:16px; margin-bottom:24px;">
        <button class="btn btn-outline btn-sm" onclick="navigateTo('patients')">Back</button>
        <h2 style="font-size:1.8rem; font-weight:800; margin:0;">${p.name}</h2>
        <span class="badge badge-info">${p.gender}</span>
        <span class="badge badge-danger">${p.blood_group}</span>
        <code style="background:var(--bg-card);padding:6px 12px;border-radius:8px;border:1px solid var(--border);color:var(--accent);font-weight:600;">ABHA: ${p.meta.abha_id}</code>
      </div>
      
      <div class="card fade-in" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:20px; margin-bottom:24px; padding:20px;">
        <div><div style="font-size:0.8rem;color:var(--text-muted);text-transform:uppercase;">DOB</div><div style="font-weight:600;">${p.date_of_birth}</div></div>
        <div><div style="font-size:0.8rem;color:var(--text-muted);text-transform:uppercase;">Phone</div><div style="font-weight:600;">${p.phone_number}</div></div>
        <div style="grid-column: span 2;"><div style="font-size:0.8rem;color:var(--text-muted);text-transform:uppercase;">Address</div><div style="font-weight:600;">${p.address}</div></div>
      </div>
      
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <div class="tabs" id="pt-tabs">
          <div class="tab active" data-tab="encounters">Encounters (${data.encounters.length})</div>
          <div class="tab" data-tab="reports">Reports (${data.diagnostic_reports.length})</div>
          <div class="tab" data-tab="prescriptions">Prescriptions (${data.prescriptions.length})</div>
          <div class="tab" data-tab="labs">Labs (${data.lab_results.length})</div>
        </div>
        <div>
          <button class="btn btn-primary btn-sm" onclick="navigateTo('new_encounter', {id:'${id}'})">New Encounter</button>
        </div>
      </div>
      
      <div id="tab-encounters" class="tab-content active">`;
      
      if(data.encounters.length) {
        html += `<div class="timeline">`;
        data.encounters.forEach(e => {
          html += `
            <div class="timeline-item">
              <div class="timeline-icon"></div>
              <div class="timeline-content">
                <div style="display:flex; justify-content:space-between;">
                  <div class="timeline-date">${new Date(e.created_date).toLocaleString()} • ${e.encounter_type.toUpperCase()}</div>
                  <span class="badge ${e.status==='completed'?'badge-success':'badge-warning'}">${e.status}</span>
                </div>
                <div class="timeline-title">${e.chief_complaint || 'Follow-up'}</div>
                <div class="timeline-body">
                  ${Array.isArray(e.diagnosis) && e.diagnosis.length ? `<div style="margin-bottom:8px;"><strong>Diagnosis:</strong> ${e.diagnosis.map(d=>`<span class="badge badge-danger">${d}</span>`).join(' ')}</div>` : ''}
                  ${e.vitals && typeof e.vitals === 'object' && Object.keys(e.vitals).length ? `<div style="margin-bottom:8px; font-size:0.85rem; background:var(--bg-primary); padding:8px; border-radius:6px;"><strong>Vitals:</strong> BP ${e.vitals.bp||'--'} | HR ${e.vitals.hr||'--'} | Temp ${e.vitals.temp||'--'}</div>` : ''}
                  ${e.examination ? `<div style="margin-bottom:8px;"><strong>Exam:</strong> ${e.examination}</div>` : ''}
                  ${e.plan ? `<div><strong>Plan:</strong> ${e.plan}</div>` : ''}
                </div>
              </div>
            </div>`;
        });
        html += `</div>`;
      } else {
        html += `<div class="empty-state"><div class="icon"></div><h3>No encounters recorded</h3></div>`;
      }
      
      html += `</div>
      <div id="tab-reports" class="tab-content">`;
      if(data.diagnostic_reports.length) {
        data.diagnostic_reports.forEach(r => {
          html += `
            <div class="card" style="margin-bottom:16px; padding:20px;">
              <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
                <h4 style="font-size:1.1rem; color:var(--accent);">${r.title}</h4>
                <span class="badge badge-info">${r.report_type}</span>
              </div>
              <div style="font-size:0.85rem; color:var(--text-muted); margin-bottom:16px;">Date: ${new Date(r.created_date).toLocaleDateString()} | Category: ${r.category}</div>
              <div style="margin-bottom:12px;"><strong>Findings:</strong><p style="color:var(--text-secondary); margin-top:4px;">${r.findings}</p></div>
              <div style="margin-bottom:12px;"><strong>Impression:</strong><p style="color:var(--text-secondary); margin-top:4px;">${r.impression}</p></div>
              <div><strong>Recommendations:</strong><p style="color:var(--text-secondary); margin-top:4px;">${r.recommendations}</p></div>
            </div>`;
        });
      } else {
        html += `<div class="empty-state"><div class="icon"></div><h3>No diagnostic reports</h3></div>`;
      }
      
      html += `</div>
      <div id="tab-prescriptions" class="tab-content">`;
      if(data.prescriptions.length) {
        html += `<div class="table-wrap"><table><thead><tr><th>Medication</th><th>Dosage & Freq</th><th>Duration</th><th>Status</th><th>Date</th></tr></thead><tbody>`;
        data.prescriptions.forEach(p => {
          html += `<tr>
            <td style="font-weight:600;color:var(--text-primary);">${p.medication}</td>
            <td>${p.dosage} ${p.frequency} (${p.route})</td>
            <td>${p.duration}</td>
            <td><span class="badge ${p.status==='active'?'badge-success':'badge-neutral'}">${p.status}</span></td>
            <td>${new Date(p.created_date).toLocaleDateString()}</td>
          </tr>`;
        });
        html += `</tbody></table></div>`;
      } else {
        html += `<div class="empty-state"><div class="icon"></div><h3>No prescriptions</h3></div>`;
      }
      
      html += `</div>
      <div id="tab-labs" class="tab-content">`;
      if(data.lab_results.length) {
        data.lab_results.forEach(l => {
          html += `
            <div class="card" style="margin-bottom:16px; padding:20px;">
              <h4 style="font-size:1.1rem; color:var(--success); margin-bottom:12px;">${l.panel_name}</h4>
              <div style="font-size:0.85rem; color:var(--text-muted); margin-bottom:16px;">Date: ${new Date(l.created_date).toLocaleDateString()}</div>
              <div class="table-wrap" style="background:var(--bg-primary);">
                <table>
                  <thead><tr><th>Test</th><th>Value</th><th>Status</th><th>Reference</th></tr></thead>
                  <tbody>
                    ${l.results.map(res => `<tr>
                      <td style="font-weight:600;">${res.parameter}</td>
                      <td>${res.value}</td>
                      <td><span class="badge ${res.status==='HIGH'?'badge-danger':res.status==='LOW'?'badge-warning':'badge-success'}">${res.status}</span></td>
                      <td style="color:var(--text-muted);">${res.reference}</td>
                    </tr>`).join('')}
                  </tbody>
                </table>
              </div>
            </div>`;
        });
      } else {
        html += `<div class="empty-state"><div class="icon"></div><h3>No lab results</h3></div>`;
      }
      html += `</div>`;
      
    main.innerHTML = html;
    
    // Tab switching logic
    document.querySelectorAll('.tab').forEach(tab => {
      tab.onclick = () => {
        document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
      };
    });
    
  } catch(e) {
    main.innerHTML = `<div class="card"><p style="color:var(--danger)">Failed to load patient: ${e.message}</p></div>`;
  }
}

// ─── New Encounter ───
async function renderNewEncounter(patientId) {
  const main = document.getElementById('main-content');
  main.innerHTML = `
    <div class="page-header">
      <div><h2>New Encounter</h2><p>Record a new clinical consultation</p></div>
      <button class="btn btn-outline btn-sm" onclick="navigateTo('patient_detail', {id:'${patientId}'})">Cancel</button>
    </div>
    <div class="card fade-in">
      <form id="encounter-form">
        <div class="form-group">
          <label class="form-label">Chief Complaint</label>
          <input class="form-input" id="enc-cc" required placeholder="e.g. Persistent cough and fever">
        </div>
        
        <h4 style="margin:24px 0 12px; color:var(--text-primary); border-bottom:1px solid var(--border); padding-bottom:8px;">Vitals</h4>
        <div class="form-grid">
          <div class="form-group"><label class="form-label">BP (mmHg)</label><input class="form-input" id="enc-bp" placeholder="120/80"></div>
          <div class="form-group"><label class="form-label">Heart Rate (bpm)</label><input class="form-input" id="enc-hr" placeholder="72"></div>
          <div class="form-group"><label class="form-label">Temp (°F)</label><input class="form-input" id="enc-temp" placeholder="98.6"></div>
          <div class="form-group"><label class="form-label">SpO2 (%)</label><input class="form-input" id="enc-spo2" placeholder="98"></div>
        </div>
        
        <h4 style="margin:24px 0 12px; color:var(--text-primary); border-bottom:1px solid var(--border); padding-bottom:8px;">Clinical Assessment</h4>
        <div class="form-group">
          <label class="form-label">Physical Examination</label>
          <textarea class="form-textarea" id="enc-exam" placeholder="Clear breath sounds, soft abdomen..."></textarea>
        </div>
        <div class="form-group">
          <label class="form-label">Diagnosis (comma separated)</label>
          <input class="form-input" id="enc-dx" placeholder="e.g. Community acquired pneumonia, Hypertension">
        </div>
        <div class="form-group">
          <label class="form-label">Treatment Plan</label>
          <textarea class="form-textarea" id="enc-plan" style="min-height:150px;" placeholder="Prescribe antibiotics, follow up in 1 week..."></textarea>
        </div>
        
        <div style="margin-top:32px; display:flex; gap:16px;">
          <button type="submit" class="btn btn-primary" id="btn-save-enc">Save Encounter</button>
          <button type="button" class="btn btn-outline" onclick="generateSOAP()">Auto-fill with MedGemma</button>
        </div>
      </form>
    </div>
  `;
  
  document.getElementById('encounter-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-save-enc');
    btn.innerHTML = '<span class="spinner"></span> Saving...'; btn.disabled = true;
    try {
      const dxStr = document.getElementById('enc-dx').value;
      const diagnosis = dxStr ? dxStr.split(',').map(s=>s.trim()) : [];
      
      await api('/api/v1/encounter/', {
        method: 'POST',
        body: {
          patient_id: patientId,
          chief_complaint: document.getElementById('enc-cc').value,
          vitals: {
            bp: document.getElementById('enc-bp').value,
            hr: document.getElementById('enc-hr').value,
            temp: document.getElementById('enc-temp').value,
            spo2: document.getElementById('enc-spo2').value,
          },
          examination: document.getElementById('enc-exam').value,
          diagnosis: diagnosis,
          plan: document.getElementById('enc-plan').value,
        }
      });
      showToast('Encounter saved successfully');
      navigateTo('patient_detail', {id: patientId});
    } catch(err) {
      showToast(err.message, 'error');
      btn.innerHTML = 'Save Encounter'; btn.disabled = false;
    }
  };
}

// ─── AI Chatbot ───
async function renderChat(el) {
  el.innerHTML = `
    <div class="page-header">
      <div><h2>Clinical Assistant</h2><p>Conversational interface</p></div>
    </div>
    <div class="chat-container fade-in">
      <div class="chat-messages" id="chat-msgs">
        <div class="chat-msg ai">Hello Dr. ${currentUser?.last_name || ''}, I am your Clinical Assistant. How can I help you today? If you want to analyze a specific patient, enter their ABHA ID below.</div>
      </div>
      <div class="chat-input-area">
        <input type="text" class="form-input" id="chat-patient" placeholder="Patient ABHA ID (optional)" style="width:200px; background:var(--bg-secondary);">
        <input type="text" class="chat-input" id="chat-input" placeholder="Type your clinical question..." style="color: #0f172a !important;">
        <button class="chat-send" id="chat-send">Send</button>
      </div>
    </div>
  `;
  
  const sessionId = crypto.randomUUID();
  const input = document.getElementById('chat-input');
  const btn = document.getElementById('chat-send');
  const msgs = document.getElementById('chat-msgs');
  const patientInput = document.getElementById('chat-patient');
  
  const sendMessage = async () => {
    const text = input.value.trim();
    if(!text) return;
    
    // Add user message
    msgs.innerHTML += `<div class="chat-msg user">${text}</div>`;
    input.value = '';
    msgs.scrollTop = msgs.scrollHeight;
    
    // Add loading indicator
    const loadingId = 'loading-' + Date.now();
    msgs.innerHTML += `<div class="chat-msg ai" id="${loadingId}"><span class="spinner" style="width:16px;height:16px;border-width:2px;"></span></div>`;
    msgs.scrollTop = msgs.scrollHeight;
    
    try {
      const data = await api('/api/v1/chat/', {
        method: 'POST',
        body: {
          message: text,
          session_id: sessionId,
          patient_id: patientInput.value.trim()
        }
      });
      
      document.getElementById(loadingId).remove();
      // Format markdown-like response
      let formatted = data.message.replace(/\n/g, '<br>');
      msgs.innerHTML += `<div class="chat-msg ai">${formatted}</div>`;
    } catch(e) {
      document.getElementById(loadingId).remove();
      msgs.innerHTML += `<div class="chat-msg ai" style="color:var(--danger)">Error: ${e.message}</div>`;
    }
    msgs.scrollTop = msgs.scrollHeight;
  };
  
  btn.onclick = sendMessage;
  input.onkeypress = (e) => { if(e.key==='Enter') sendMessage(); };
}

// ─── Cross-Hospital Data ───
async function renderCrossHospital(el, abha) {
  el.innerHTML = `
    <div class="page-header">
      <div><h2>Cross-Hospital Records</h2><p>View decentralized records across UHI</p></div>
    </div>
    <div class="card fade-in">
      <div class="card-header"><h3 class="card-title">Hospitals Holding Data</h3></div>
      <div style="display:flex; gap:16px; margin-bottom:24px;">
        <input type="text" class="form-input" id="uhi-abha" value="${abha || ''}" placeholder="Patient ABHA ID (e.g. 91-1234-5678-9012)" style="flex:1;">
        <button class="btn btn-primary" onclick="searchUHI()">Search Records</button>
      </div>
      <div id="uhi-results"></div>
    </div>
  `;
  if (abha) setTimeout(() => searchUHI(), 100);
}

async function searchUHI() {
  const abha = document.getElementById('uhi-abha').value.trim();
  const resEl = document.getElementById('uhi-results');
  if(!abha) { showToast('Enter ABHA ID', 'error'); return; }
  
  resEl.innerHTML = '<div style="text-align:center;padding:40px;"><span class="spinner"></span></div>';
  
  try {
    const sum = await api(`/api/v1/cross_hospital/summary/?abha_id=${abha}`);
    if(sum.error) throw new Error(sum.error);
    
    let html = `
      <div style="padding:20px; border-radius:12px; background:var(--bg-secondary); border:1px solid var(--border); margin-bottom:20px;">
        <h4 style="margin-bottom:12px; color:var(--accent);">Data Located Across UHI Network</h4>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
          <div><strong>Total Bundles:</strong> <span class="badge badge-info">${sum.data_summary.total_bundles}</span></div>
          <div><strong>Hospitals Holding Data:</strong> ${sum.data_summary.hospitals_with_data.join(', ')}</div>
          <div><strong>Active Consents:</strong> <span class="badge badge-success">${sum.consent_summary.active}</span></div>
          <div><strong>Data Types:</strong> <span style="font-size:0.85rem;color:var(--text-muted);">${sum.data_summary.resource_types.join(', ')}</span></div>
        </div>
      </div>
      <button class="btn btn-success" onclick="fetchUHIRecords('${abha}')" style="width:100%; margin-bottom:24px;">⬇️ Decrypt & View Full Records (Requires Consent)</button>
      <div id="uhi-full-records"></div>
    `;
    resEl.innerHTML = html;
  } catch(e) {
    resEl.innerHTML = `<div style="color:var(--danger); padding:20px; background:rgba(239,68,68,0.1); border-radius:8px;">${e.message}</div>`;
  }
}

async function fetchUHIRecords(abha) {
  const resEl = document.getElementById('uhi-full-records');
  resEl.innerHTML = '<div style="text-align:center;padding:40px;"><span class="spinner"></span><p style="margin-top:12px;color:var(--text-muted);">Verifying consent and decrypting bundles...</p></div>';
  
  try {
    const data = await api(`/api/v1/cross_hospital/patient_records/?abha_id=${abha}`);
    if(data.error) throw new Error(data.error);
    
    let html = `<h4 style="margin-bottom:16px; border-bottom:1px solid var(--border); padding-bottom:8px;">Decrypted Records from Network</h4>`;
    
    // Hospitals
    html += `<div style="display:flex; gap:12px; margin-bottom:20px;">`;
    data.hospitals.forEach(h => {
      html += `<div style="padding:8px 16px; background:var(--bg-glass); border-radius:20px; border:1px solid var(--border); font-size:0.85rem;">🏥 <strong>${h.name}</strong> (${h.id})</div>`;
    });
    html += `</div>`;
    
    // Timeline
    html += `<div class="timeline">`;
    data.progress_records.forEach(r => {
      html += `
        <div class="timeline-item">
          <div class="timeline-icon"></div>
          <div class="timeline-content">
            <div style="display:flex; justify-content:space-between;">
              <div class="timeline-date">Month ${r.month} Progress Report</div>
              <span class="badge badge-neutral">${r.source_hospital}</span>
            </div>
            <div class="timeline-body">
              <div style="margin-bottom:8px;"><strong>Assessment:</strong> ${r.assessment}</div>
              <div style="display:flex; gap:16px; font-size:0.85rem; color:var(--text-muted);">
                <span><strong>BP:</strong> ${r.blood_pressure}</span>
                <span><strong>Weight:</strong> ${r.weight_kg}kg</span>
              </div>
            </div>
          </div>
        </div>`;
    });
    
    data.imaging_records.forEach(img => {
      html += `
        <div class="timeline-item">
          <div class="timeline-icon"></div>
          <div class="timeline-content" style="border-color:var(--info);">
            <div style="display:flex; justify-content:space-between;">
              <div class="timeline-date">Month ${img.month} • ${img.type.toUpperCase()}</div>
              <span class="badge badge-neutral">${img.source_hospital}</span>
            </div>
            <div class="timeline-title">${img.technique}</div>
            <div class="timeline-body">
              <div style="margin-bottom:8px;"><strong>Impression:</strong> ${img.impression}</div>
              <div style="font-size:0.85rem; color:var(--text-muted);">Reported by ${img.radiologist}</div>
            </div>
          </div>
        </div>`;
    });
    html += `</div>
      <button class="btn btn-primary" onclick="summarizeUHIRecords('${abha}')" style="margin-top:20px; width:100%;">Generate Summary of UHI Records</button>
      <div id="uhi-ai-summary" style="margin-top:16px;"></div>
    `;
    
    resEl.innerHTML = html;
  } catch(e) {
    resEl.innerHTML = `<div style="color:var(--danger); padding:20px; background:rgba(239,68,68,0.1); border-radius:8px;">Failed to decrypt records: ${e.message}<br><br><small>Patient has likely not granted consent to this facility.</small></div>`;
  }
}

async function summarizeUHIRecords(abha) {
  const el = document.getElementById('uhi-ai-summary');
  el.innerHTML = '<div style="text-align:center;padding:20px;"><div class="spinner" style="margin-bottom:12px;"></div><p style="color:var(--text-muted)">MedGemma AI is analyzing the encrypted UHI bundles...</p></div>';
  try {
    const data = await api('/api/v1/medgemma/analyze/', {
      method: 'POST',
      body: { analysis_type: 'report_summary', patient_id: abha }
    });
    el.innerHTML = `
      <div style="background:rgba(99,102,241,0.05); border-left:4px solid var(--accent); padding:16px; border-radius:8px; line-height:1.6; font-size:0.95rem;">
        <h4 style="margin-bottom:12px; color:var(--accent);">Cross-Hospital Summary</h4>
        ${data.analysis_result.summary}
      </div>
    `;
  } catch(e) {
    el.innerHTML = `<div style="color:var(--danger); padding:12px; background:rgba(239,68,68,0.1); border-radius:8px;">AI Analysis Failed: ${e.message}</div>`;
  }
}


// ─── Analytics (Existing functionality, ported to new UI) ───
async function renderMedGemma(el) {
  el.innerHTML = `
    <div class="page-header">
      <div><h2>Clinical Analytics</h2><p>Run advanced clinical analyses on patient records</p></div>
    </div>
    <div class="card fade-in">
      <div style="display:flex; gap:16px; margin-bottom:24px;">
        <input type="text" class="form-input" id="mg-abha" value="91-1234-5678-9012" placeholder="Patient ABHA ID" style="flex:1;">
        <select class="form-select" id="mg-type" style="width:250px;">
          <option value="report_summary">Clinical Summary</option>
          <option value="ddi_check">Drug Interactions</option>
          <option value="trend_analysis">Trend Analysis</option>
          <option value="differential_diagnosis">Differential Diagnosis</option>
          <option value="soap_autofill">SOAP Autofill</option>
        </select>
        <button class="btn btn-primary" id="mg-run" onclick="runMedGemma()">🧬 Analyze</button>
      </div>
      <div id="mg-result">
        <div class="empty-state"><div class="icon">🤖</div><h3>Ready for analysis</h3><p>Select an analysis type and click analyze.</p></div>
      </div>
    </div>
  `;
}

async function runMedGemma() {
  const btn = document.getElementById('mg-run');
  const resEl = document.getElementById('mg-result');
  btn.innerHTML = '<span class="spinner"></span> Analyzing...'; btn.disabled = true;
  resEl.innerHTML = '<div style="text-align:center;padding:60px;"><div class="spinner" style="width:40px;height:40px;border-width:4px;margin-bottom:16px;"></div><p style="color:var(--text-muted);">AI models analyzing clinical context...</p></div>';
  
  try {
    const data = await api('/api/v1/medgemma/analyze/', {
      method: 'POST',
      body: {
        analysis_type: document.getElementById('mg-type').value,
        patient_id: document.getElementById('mg-abha').value,
      }
    });
    
    const r = data.analysis_result || {};
    let html = `
      <div class="fade-in" style="background:var(--bg-secondary); border:1px solid var(--border); border-radius:12px; padding:24px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom:1px solid var(--border); padding-bottom:12px;">
          <h3 style="font-size:1.2rem; color:var(--accent); margin:0;">Analysis Complete</h3>
          <div><span class="badge badge-info">${data.analysis_type}</span> <span class="badge badge-neutral">${r.processing_time_ms||0}ms</span></div>
        </div>
        
        <div style="background:rgba(99,102,241,0.05); border-left:4px solid var(--accent); padding:16px; border-radius:8px; margin-bottom:24px; line-height:1.6; font-size:0.95rem;">
          ${r.summary}
        </div>
    `;
    
    if (r.flags?.length) {
      html += `<div style="margin-bottom:24px;">
        <h4 style="margin-bottom:12px; font-size:1rem;">🚩 Clinical Flags</h4>
        <div style="display:flex; flex-wrap:wrap; gap:8px;">
          ${r.flags.map(f=>`<span class="badge badge-warning">${f}</span>`).join('')}
        </div>
      </div>`;
    }
    
    if (r.key_findings?.length) {
      html += `<div>
        <h4 style="margin-bottom:12px; font-size:1rem;">🔬 Key Findings</h4>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Parameter</th><th>Value</th><th>Status</th><th>Reference</th></tr></thead>
            <tbody>
              ${r.key_findings.map(f => `<tr>
                <td style="font-weight:600;">${f.parameter}</td>
                <td>${f.value}</td>
                <td><span class="badge ${f.status==='HIGH'?'badge-danger':f.status==='LOW'?'badge-warning':'badge-success'}">${f.status}</span></td>
                <td style="color:var(--text-muted); font-size:0.8rem;">${f.reference}</td>
              </tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div>`;
    }
    
    html += `</div>`;
    resEl.innerHTML = html;
    
  } catch(e) {
    resEl.innerHTML = `<div style="color:var(--danger); padding:20px; background:rgba(239,68,68,0.1); border-radius:8px;">Analysis Failed: ${e.message}</div>`;
  }
  
  btn.innerHTML = '🧬 Analyze'; btn.disabled = false;
}

// ─── Consent, Audit (Placeholders connecting to existing APIs) ───
async function renderConsent(el) {
  el.innerHTML = `
    <div class="page-header">
      <div><h2>🔐 Consent Management</h2><p>DEPA-compliant consent artifacts</p></div>
    </div>
    <div class="card fade-in">
      <h3 class="card-title" style="margin-bottom:20px;">Request Data Access</h3>
      <div class="form-grid">
        <div class="form-group"><label class="form-label">Patient ABHA ID</label><input class="form-input" id="c-abha" value="91-1234-5678-9012"></div>
        <div class="form-group"><label class="form-label">Purpose of Request</label><select class="form-select" id="c-purpose"><option>Clinical Diagnosis</option><option>Second Opinion</option></select></div>
      </div>
      <button class="btn btn-primary" onclick="requestConsent()">✉️ Send Consent Request to Patient's App</button>
    </div>
    <div id="consent-list" style="margin-top:24px;"></div>
  `;
  loadConsents();
}

async function requestConsent() {
  showToast('Consent request sent via UHI Switch to Patient\'s HealthWallet App.', 'success');
  // API call would go here
}

async function loadConsents() {
  const el = document.getElementById('consent-list');
  try {
    const data = await api('/api/v1/consent/');
    if(!data.results?.length) { el.innerHTML = '<div class="empty-state">No consent records found</div>'; return; }
    el.innerHTML = `
      <div class="table-wrap fade-in">
        <table>
          <thead><tr><th>Patient ABHA</th><th>Purpose</th><th>Status</th><th>Valid Until</th></tr></thead>
          <tbody>
            ${data.results.map(c => `<tr>
              <td><code>${c.patient_abha_id}</code></td>
              <td>${c.purpose}</td>
              <td><span class="badge ${c.status==='ACTIVE'?'badge-success':c.status==='REVOKED'?'badge-danger':'badge-warning'}">${c.status}</span></td>
              <td>${c.valid_until ? new Date(c.valid_until).toLocaleDateString() : '—'}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  } catch(e) { el.innerHTML = `<p style="color:var(--danger)">${e.message}</p>`; }
}

async function renderAudit(el) {
  el.innerHTML = `
    <div class="page-header">
      <div><h2>📋 Audit Log</h2><p>Cryptographically verified immutable logs</p></div>
    </div>
    <div id="audit-list"></div>
  `;
  try {
    const data = await api('/api/v1/audit/?limit=50');
    document.getElementById('audit-list').innerHTML = `
      <div class="table-wrap fade-in">
        <table>
          <thead><tr><th>Time</th><th>Event</th><th>Actor</th><th>Hash</th></tr></thead>
          <tbody>
            ${data.results.map(a => `<tr>
              <td style="font-size:0.8rem; white-space:nowrap;">${new Date(a.timestamp).toLocaleString()}</td>
              <td><span class="badge badge-info">${a.event_type}</span></td>
              <td><span style="font-size:0.85rem;">${a.actor_id.slice(0,8)}...</span></td>
              <td><code style="color:var(--text-muted); font-size:0.75rem;">${a.entry_hash.slice(0,16)}...</code></td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  } catch(e) {}
}

// ─── Init ───
(async function init() {
  try {
    appConfig = await api('/api/v1/config/', {noAuth:true}) || appConfig;
    if (appConfig.hospital_id === 'HOSP-001') {
      document.documentElement.style.setProperty('--accent', '#3b82f6'); // Blue
      document.documentElement.style.setProperty('--accent-hover', '#2563eb');
      document.documentElement.style.setProperty('--accent-glow', 'rgba(59,130,246,0.3)');
    } else if (appConfig.hospital_id === 'HOSP-002') {
      document.documentElement.style.setProperty('--accent', '#14b8a6'); // Teal
      document.documentElement.style.setProperty('--accent-hover', '#0d9488');
      document.documentElement.style.setProperty('--accent-glow', 'rgba(20,184,166,0.3)');
    }
    document.title = appConfig.hospital_name + " — CARE EMR";
  } catch(e) {}

  if (storage.token) {
    try { currentUser = await api('/api/v1/users/me/'); } catch(e) { storage.token = null; }
  }
  render();
})();
