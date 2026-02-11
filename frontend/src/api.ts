import type { JobSummary, JobDetail, RunSummary, RunDetail } from "./types";

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export function fetchJobs(): Promise<JobSummary[]> {
  return fetchJSON("/api/jobs");
}

export function fetchJob(name: string): Promise<JobDetail> {
  return fetchJSON(`/api/jobs/${encodeURIComponent(name)}`);
}

export async function triggerJob(name: string): Promise<void> {
  const res = await fetch(`/api/jobs/${encodeURIComponent(name)}/trigger`, {
    method: "POST",
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
  const res = await fetch(
    `/api/logs/${encodeURIComponent(jobName)}/${encodeURIComponent(filename)}`
  );
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.text();
}
