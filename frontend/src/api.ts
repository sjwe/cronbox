import type { JobSummary, JobDetail, RunSummary, RunDetail, AuthUser, APIKeyItem, APIKeyCreated, UserItem, JobFormData } from "./types";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("cronbox_token");
  const headers: Record<string, string> = {
    ...((init?.headers as Record<string, string>) || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, { ...init, headers });

  if (res.status === 401) {
    const refreshRes = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
    });
    if (refreshRes.ok) {
      const data = await refreshRes.json();
      localStorage.setItem("cronbox_token", data.access_token);
      headers["Authorization"] = `Bearer ${data.access_token}`;
      const retry = await fetch(url, { ...init, headers });
      if (!retry.ok) throw new Error(`${retry.status} ${retry.statusText}`);
      return retry.json();
    }
    localStorage.removeItem("cronbox_token");
    window.location.href = "/login";
    throw new Error("Session expired");
  }

  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// --- Job APIs ---

export function fetchJobs(): Promise<JobSummary[]> {
  return fetchJSON("/api/jobs");
}

export function fetchJob(name: string): Promise<JobDetail> {
  return fetchJSON(`/api/jobs/${encodeURIComponent(name)}`);
}

export function createJob(data: JobFormData): Promise<{ message: string; job_name: string }> {
  return fetchJSON("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function updateJob(name: string, data: Partial<JobFormData>): Promise<{ message: string; job_name: string }> {
  return fetchJSON(`/api/jobs/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteJob(name: string): Promise<void> {
  const token = localStorage.getItem("cronbox_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`/api/jobs/${encodeURIComponent(name)}`, { method: "DELETE", headers });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

export async function triggerJob(name: string): Promise<void> {
  const token = localStorage.getItem("cronbox_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`/api/jobs/${encodeURIComponent(name)}/trigger`, {
    method: "POST",
    headers,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

export async function fetchRuns(jobName?: string, limit?: number): Promise<RunSummary[]> {
  const params = new URLSearchParams();
  if (jobName) params.set("job_name", jobName);
  if (limit) params.set("per_page", String(limit));
  const qs = params.toString();
  const data = await fetchJSON<{ runs: RunSummary[] }>(`/api/runs${qs ? `?${qs}` : ""}`);
  return data.runs;
}

export function fetchRun(id: number): Promise<RunDetail> {
  return fetchJSON(`/api/runs/${id}`);
}

export async function fetchLogFiles(jobName: string): Promise<string[]> {
  const data = await fetchJSON<{ filename: string }[]>(
    `/api/logs/${encodeURIComponent(jobName)}`
  );
  return data.map((entry) => entry.filename);
}

export async function fetchLogContent(jobName: string, filename: string): Promise<string> {
  const token = localStorage.getItem("cronbox_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(
    `/api/logs/${encodeURIComponent(jobName)}/${encodeURIComponent(filename)}`,
    { headers }
  );
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.text();
}

// --- Auth APIs ---

export async function loginAPI(
  username: string,
  password: string
): Promise<{ access_token: string; token_type: string; expires_in: number; user: AuthUser }> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function refreshToken(): Promise<{ access_token: string; user: AuthUser }> {
  const res = await fetch("/api/auth/refresh", {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function logoutAPI(): Promise<void> {
  const token = localStorage.getItem("cronbox_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  await fetch("/api/auth/logout", { method: "POST", headers, credentials: "include" });
}

export async function fetchMe(token?: string): Promise<AuthUser> {
  const t = token || localStorage.getItem("cronbox_token");
  const headers: Record<string, string> = {};
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const res = await fetch("/api/auth/me", { headers });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// --- API Key APIs ---

export function fetchAPIKeys(): Promise<APIKeyItem[]> {
  return fetchJSON("/api/keys");
}

export function createAPIKey(name: string, expires_in_days: number | null): Promise<APIKeyCreated> {
  return fetchJSON("/api/keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, expires_in_days }),
  });
}

export async function revokeAPIKey(id: number): Promise<void> {
  const token = localStorage.getItem("cronbox_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`/api/keys/${id}`, { method: "DELETE", headers });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

// --- Admin User APIs ---

export function fetchUsers(): Promise<UserItem[]> {
  return fetchJSON("/api/admin/users");
}

export function createUser(
  username: string,
  email: string,
  password: string,
  role: string
): Promise<UserItem> {
  return fetchJSON("/api/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, email, password, role }),
  });
}

export function updateUser(id: number, updates: Record<string, unknown>): Promise<UserItem> {
  return fetchJSON(`/api/admin/users/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
}

export async function deleteUser(id: number): Promise<void> {
  const token = localStorage.getItem("cronbox_token");
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`/api/admin/users/${id}`, { method: "DELETE", headers });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}
