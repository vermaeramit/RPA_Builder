// Thin wrapper around the backend REST API, with JWT auth.
const base = "/api";

const TOKEN_KEY = "rpa_token";
export const auth = {
  get token() {
    return localStorage.getItem(TOKEN_KEY) || "";
  },
  set token(v) {
    if (v) localStorage.setItem(TOKEN_KEY, v);
    else localStorage.removeItem(TOKEN_KEY);
  },
};

// Called when the server rejects our token (expired / invalid). App subscribes.
let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function j(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;

  const res = await fetch(base + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    auth.token = "";
    onUnauthorized();
    throw new Error("Session expired — please sign in again.");
  }
  if (!res.ok) {
    let detail = await res.text();
    try {
      detail = JSON.parse(detail).detail || detail;
    } catch {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  // auth
  login: (username, password) => j("POST", "/auth/login", { username, password }),
  me: () => j("GET", "/auth/me"),
  // users (admin)
  listUsers: () => j("GET", "/users"),
  createUser: (username, password, role) => j("POST", "/users", { username, password, role }),
  setUserRole: (id, role) => j("PATCH", `/users/${id}/role`, { role }),
  deleteUser: (id) => j("DELETE", `/users/${id}`),
  // app
  getNodes: () => j("GET", "/nodes"),
  listWorkflows: () => j("GET", "/workflows"),
  getWorkflow: (id) => j("GET", `/workflows/${id}`),
  saveWorkflow: (wf) => j("POST", "/workflows", wf),
  deleteWorkflow: (id) => j("DELETE", `/workflows/${id}`),
  run: (graph, workflow_id, name) => j("POST", "/run", { graph, workflow_id, name }),
  listSchedules: () => j("GET", "/schedules"),
  addSchedule: (workflow_id, cron) => j("POST", "/schedules", { workflow_id, cron }),
  removeSchedule: (jobId) => j("DELETE", `/schedules/${jobId}`),
  listRuns: (limit = 50) => j("GET", `/runs?limit=${limit}`),
  getRun: (id) => j("GET", `/runs/${id}`),
};
