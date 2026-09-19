const app = document.getElementById("app");

const state = {
  view: "home",
  loginOpen: false,
  loginRole: "hr",
  user: null,
  token: localStorage.getItem("aionos_token"),
  error: "",
  hr: null,
  emp: null,
  dept: "",
  employees: [],
  messages: [],
  busy: false,
};

function logo() {
  return `<span class="brand">
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <path d="M6 24L16 6l10 18H6z" stroke="#1b7c74" stroke-width="2.4"/>
      <path d="M12 24l4-8 4 8" stroke="#5aa7a1" stroke-width="2.2"/>
    </svg>
    AionOS
  </span>`;
}

function topbar() {
  const right = state.user
    ? `<div class="userchip"><span class="avatar">${state.user.name.slice(0,1)}</span>${state.user.name}
        <button class="btn btn-ghost" onclick="logout()">Sign out</button></div>`
    : `<div class="top-actions">
        <div class="search-pill">Search  ⌘K</div>
        <button class="btn btn-teal" onclick="openLogin()">Contact / Sign in</button>
      </div>`;
  return `<header class="topbar">
    ${logo()}
    ${right}
  </header>`;
}

function home() {
  return `<section class="simple-home">
      <svg class="simple-home-mark" viewBox="0 0 32 32" fill="none">
        <path d="M6 24L16 6l10 18H6z" stroke="#1b7c74" stroke-width="2.2"/>
        <path d="M12 24l4-8 4 8" stroke="#5aa7a1" stroke-width="2"/>
      </svg>
      <h1 class="simple-home-title">AionOS</h1>
      <p class="simple-home-tag">People OS</p>
      <div class="simple-home-actions">
        <button class="btn btn-teal btn-lg" onclick="openLogin('employee')">Employee Login</button>
        <button class="btn btn-outline btn-lg" onclick="openLogin('hr')">HR Login</button>
      </div>
    </section>
    ${state.loginOpen ? loginModal() : ""}`;
}

function card(color, icon, title, subtitle, role) {
  return `<button class="product-card" onclick="openLogin('${role}')">
    <div class="icon ${color}">${icon}</div>
    <h3>${title}</h3>
    <p>${subtitle}</p>
  </button>`;
}

function briefcase() {
  return `<svg width="22" height="22" fill="none" stroke="white" stroke-width="2"><rect x="3" y="8" width="16" height="11" rx="2"/><path d="M8 8V6a3 3 0 0 1 6 0v2"/></svg>`;
}
function layers() {
  return `<svg width="22" height="22" fill="none" stroke="white" stroke-width="2"><path d="M11 3 3 8l8 5 8-5-8-5z"/><path d="M3 12l8 5 8-5"/></svg>`;
}
function store() {
  return `<svg width="22" height="22" fill="none" stroke="white" stroke-width="2"><path d="M4 10h14v9H4z"/><path d="M3 7h16l-1 3H4L3 7z"/><path d="M11 10v9"/></svg>`;
}
function shield() {
  return `<svg width="22" height="22" fill="none" stroke="white" stroke-width="2"><path d="M11 3 4 6v6c0 4 3 7 7 8 4-1 7-4 7-8V6l-7-3z"/></svg>`;
}

function loginModal() {
  const emp = state.loginRole === "employee";
  return `<div class="modal-back" onclick="if(event.target.classList.contains('modal-back')) state.loginOpen=false, render()">
    <form class="modal" onsubmit="doLogin(event)">
      <h2 style="margin:0">AIONOS People OS</h2>
      <p style="color:var(--muted);font-size:13px">Same portal. Different knowledge. HR sees employee records; employees see policies and their own profile.</p>
      <div class="role-switch">
        <button type="button" class="${emp ? "" : "active"}" onclick="state.loginRole='hr';render()">HR</button>
        <button type="button" class="${emp ? "active" : ""}" onclick="state.loginRole='employee';render()">Employee</button>
      </div>
      <label>Username</label>
      <input name="username" value="${emp ? "10002" : "hr"}" />
      <label>Password</label>
      <input name="password" type="password" value="aionos2026" />
      <p class="hint">${emp
        ? "Try EmpID 10002 (Linda Anderson) or another active EmpID from the HR file. Password: aionos2026"
        : "Username: hr &nbsp; Password: aionos2026"}</p>
      ${state.error ? `<div class="error">${state.error}</div>` : ""}
      <button class="btn btn-teal" style="width:100%;margin-top:16px" type="button" onclick="doLogin(event)">Enter portal</button>
    </form>
  </div>`;
}

function chatPanel() {
  const suggestions = state.user?.role === "hr"
    ? ["Workforce summary by department", "Who is on PIP?", "Promotion candidates in IT/IS", "Employees with more than 15 absences", "Bonus rules for Exceeds rating"]
    : ["How many casual leave days do I get?", "When is the annual bonus paid?", "Am I eligible for a raise in April?", "Who is the medical insurance partner?", "What is the promotion checklist?"];
  const msgs = state.messages.map((m) => {
    const extra = m.trace
      ? `<div class="trace">${m.trace.map((t) => t.status === "blocked" ? `Blocked ${t.tool}` : `Used ${t.tool}`).join(" · ")}</div>`
      : "";
    return `<div class="bubble ${m.who}">${escapeHtml(m.text)}${extra}</div>`;
  }).join("");
  return `<aside class="chat">
    <div class="chat-head">
      <h3>Agentic RAG assistant</h3>
      <p>${state.user?.role === "hr"
        ? "Tools: employee search, filters, analytics, policies"
        : "Tools: company policies + your profile only"}</p>
    </div>
    <div class="messages" id="msgbox">${msgs || `<div class="bubble bot">Ask a real internal question. I retrieve from the vector store and, for HR, from live employee tables.</div>`}</div>
    <div class="chips">${suggestions.map((s) => `<button type="button" onclick="ask(${JSON.stringify(s)})">${s}</button>`).join("")}</div>
    <form class="composer" onsubmit="sendChat(event)">
      <input name="q" placeholder="Ask the AIONOS assistant…" />
      <button class="btn btn-teal" ${state.busy ? "disabled" : ""}>Send</button>
    </form>
  </aside>`;
}

function hrDashboard() {
  const s = state.hr || {};
  const depts = s.departments || [];
  const rows = (state.employees.length ? state.employees : []).slice(0, 80);
  return `${topbar()}
  <div class="shell">
    <aside class="side">
      <h4>WORKSPACE</h4>
      <button class="active">HR command center</button>
      <button onclick="ask('List employees on PIP')">PIP watchlist</button>
      <button onclick="ask('Promotion candidates')">Promotion desk</button>
      <button onclick="ask('Employees with more than 15 absences')">Attendance risk</button>
      <h4>PRODUCTS</h4>
      <button>UniStack</button><button>UniWeave</button><button>UniScale</button><button>UniProtect</button>
    </aside>
    <section class="main">
      <h2 style="margin-top:0">People analytics</h2>
      <p style="color:var(--muted);margin-top:0">Confidential employee data retrieved from HRDataset_v14 and the policy vector index.</p>
      <div class="kpis">
        <div class="kpi"><span>People on file</span><strong>${s.total_employees ?? "—"}</strong></div>
        <div class="kpi"><span>Active</span><strong>${s.active ?? "—"}</strong></div>
        <div class="kpi"><span>Attrition</span><strong>${s.attrition_rate ?? "—"}%</strong></div>
        <div class="kpi"><span>Avg salary (active)</span><strong>$${Number(s.avg_salary_active || 0).toLocaleString()}</strong></div>
      </div>
      <div class="panel">
        <h3>Department health</h3>
        <table>
          <thead><tr><th>Department</th><th>Headcount</th><th>Active</th><th>Avg salary</th><th>Absences</th><th>Engagement</th></tr></thead>
          <tbody>${depts.map((d) => `<tr>
            <td><a href="#" onclick="filterDept('${d.Department}');return false">${d.Department}</a></td>
            <td>${d.headcount}</td><td>${d.active}</td>
            <td>$${Number(d.avg_salary).toLocaleString()}</td>
            <td>${d.avg_absences}</td><td>${d.avg_engagement}</td>
          </tr>`).join("")}</tbody>
        </table>
      </div>
      <div class="panel">
        <h3>Employee directory ${state.dept ? "· " + state.dept : ""}</h3>
        <table>
          <thead><tr><th>Name</th><th>ID</th><th>Dept</th><th>Role</th><th>Salary</th><th>Perf</th><th>Absences</th><th>Status</th></tr></thead>
          <tbody>${rows.map((e) => `<tr>
            <td>${e.Employee_Name}</td><td>${e.EmpID}</td><td>${e.Department}</td>
            <td>${e.Position}</td><td>$${Number(e.Salary).toLocaleString()}</td>
            <td>${perfTag(e.PerformanceScore)}</td><td>${e.Absences}</td>
            <td>${e.EmploymentStatus}</td>
          </tr>`).join("")}</tbody>
        </table>
      </div>
    </section>
    ${chatPanel()}
  </div>`;
}

function empDashboard() {
  const p = state.emp?.profile || {};
  const b = state.emp?.bonus || {};
  const l = state.emp?.leave || {};
  const policies = state.emp?.policies || [];
  return `${topbar()}
  <div class="shell">
    <aside class="side">
      <h4>MY WORKSPACE</h4>
      <button class="active">Employee home</button>
      <button onclick="ask('Explain the leave policy')">Leave</button>
      <button onclick="ask('How does the annual bonus work?')">Bonus</button>
      <button onclick="ask('When do raises happen?')">Raises</button>
      <button onclick="ask('Promotion eligibility checklist')">Promotions</button>
      <button onclick="ask('Who are the benefits partners?')">Partners</button>
    </aside>
    <section class="main">
      <h2 style="margin-top:0">Hello, ${p.name || ""}</h2>
      <p style="color:var(--muted);margin-top:0">${p.position} · ${p.department} · EmpID ${p.empid} · Manager ${p.manager}</p>
      <div class="kpis">
        <div class="kpi"><span>Performance</span><strong style="font-size:20px">${p.performance || "—"}</strong></div>
        <div class="kpi"><span>Est. bonus (policy)</span><strong>$${Number(b.estimated_annual_bonus_usd || 0).toLocaleString()}</strong></div>
        <div class="kpi"><span>Casual leave</span><strong>${l.casual ?? 8}</strong></div>
        <div class="kpi"><span>Unplanned absences</span><strong>${l.unplanned_absences_on_file ?? 0}</strong></div>
      </div>
      <div class="panel">
        <h3>Policy desk</h3>
        <div class="policy-grid">
          ${policies.map((x) => `<div class="policy-card" onclick="ask('${x.title} policy for AIONOS employees')">
            <strong>${x.title}</strong>
            <p style="color:var(--muted);font-size:13px;margin:8px 0 0">${x.blurb}</p>
          </div>`).join("")}
        </div>
        <p style="color:var(--muted);font-size:13px;margin-top:12px">${l.attendance_note || ""}</p>
      </div>
      <div class="panel">
        <h3>Your record (visible only to you and HR)</h3>
        <table>
          <tbody>
            <tr><th>Salary</th><td>$${Number(p.salary || 0).toLocaleString()}</td><th>Hire date</th><td>${p.hire_date || ""}</td></tr>
            <tr><th>Engagement</th><td>${p.engagement}</td><th>Satisfaction</th><td>${p.satisfaction}</td></tr>
            <tr><th>Special projects</th><td>${p.projects}</td><th>Status</th><td>${p.status}</td></tr>
          </tbody>
        </table>
      </div>
    </section>
    ${chatPanel()}
  </div>`;
}

function perfTag(v) {
  if (v === "Exceeds") return `<span class="tag ok">${v}</span>`;
  if (v === "PIP") return `<span class="tag bad">${v}</span>`;
  if (v === "Needs Improvement") return `<span class="tag warn">${v}</span>`;
  return `<span class="tag info">${v}</span>`;
}

function escapeHtml(s) {
  return String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function render() {
  if (state.view === "hr") app.innerHTML = hrDashboard();
  else if (state.view === "employee") app.innerHTML = empDashboard();
  else app.innerHTML = home();
  const box = document.getElementById("msgbox");
  if (box) box.scrollTop = box.scrollHeight;
}

function openLogin(role) {
  if (role === "ops") role = "hr";
  state.loginRole = role === "employee" ? "employee" : "hr";
  state.loginOpen = true;
  state.error = "";
  render();
}

async function doLogin(ev) {
  ev.preventDefault();
  const form = ev.target.closest("form") || ev.target;
  const fd = new FormData(form);
  state.error = "";
  try {
    const res = await api("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: fd.get("username"),
        password: fd.get("password"),
        role: state.loginRole,
      }),
    });
    state.token = res.token;
    state.user = res.user;
    localStorage.setItem("aionos_token", res.token);
    localStorage.setItem("aionos_user", JSON.stringify(res.user));
    state.loginOpen = false;
    state.messages = [];
    if (res.user.role === "hr") {
      state.view = "hr";
      await loadHr();
    } else {
      state.view = "employee";
      await loadEmp();
    }
  } catch (err) {
    state.error = err.message;
    render();
  }
}

async function loadHr() {
  state.hr = await api("/api/hr/overview");
  const dir = await api("/api/hr/employees");
  state.employees = dir.employees || [];
  render();
}

async function loadEmp() {
  state.emp = await api("/api/employee/home");
  render();
}

async function filterDept(dept) {
  state.dept = dept;
  const dir = await api("/api/hr/employees?department=" + encodeURIComponent(dept));
  state.employees = dir.employees || [];
  render();
}

function logout() {
  state.user = null;
  state.token = null;
  localStorage.removeItem("aionos_token");
  localStorage.removeItem("aionos_user");
  state.view = "home";
  render();
}

async function sendChat(ev) {
  ev.preventDefault();
  const q = ev.target.q.value.trim();
  if (!q) return;
  ev.target.q.value = "";
  await ask(q);
}

async function ask(q) {
  state.messages.push({ who: "user", text: q });
  state.busy = true;
  render();
  try {
    const res = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: q }),
    });
    state.messages.push({ who: "bot", text: res.answer, trace: res.trace, citations: res.citations });
  } catch (err) {
    state.messages.push({ who: "bot", text: err.message });
  }
  state.busy = false;
  render();
}

async function api(path, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  if (state.token) headers.Authorization = "Bearer " + state.token;
  const res = await fetch(path, Object.assign({}, options, { headers }));
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

window.openLogin = openLogin;
window.doLogin = doLogin;
window.logout = logout;
window.sendChat = sendChat;
window.ask = ask;
window.filterDept = filterDept;

if (state.token && localStorage.getItem("aionos_user")) {
  state.user = JSON.parse(localStorage.getItem("aionos_user"));
  state.view = state.user.role === "hr" ? "hr" : "employee";
  render();
  (state.user.role === "hr" ? loadHr() : loadEmp()).catch(() => logout());
} else {
  render();
}