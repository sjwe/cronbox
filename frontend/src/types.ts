export type JobStatus = "success" | "failed" | "running" | "never_run";
export type TriggerType = "scheduled" | "manual";

export interface JobSummary {
  name: string;
  description: string | null;
  schedule: { cron: string; timezone: string; enabled: boolean };
  next_run_time: string | null;
  last_run: { status: JobStatus; started_at: string; duration_seconds: number } | null;
}

export interface StepConfig {
  name: string;
  command: string;
  timeout_seconds: number | null;
}

export interface JobDetail extends JobSummary {
  container: { mode: string; name?: string; image?: string };
  steps: StepConfig[];
  recent_runs: RunSummary[];
}

export interface RunSummary {
  id: number;
  job_name: string;
  status: JobStatus;
  trigger: TriggerType;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
}

export interface StepResult {
  name: string;
  status: string;
  exit_code: number | null;
  duration_seconds: number | null;
}

export interface RunDetail extends RunSummary {
  steps: StepResult[];
  log_file: string | null;
}

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  role: "admin" | "operator" | "viewer";
}

export interface APIKeyItem {
  id: number;
  key_prefix: string;
  name: string;
  expires_at: string;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

export interface APIKeyCreated extends APIKeyItem {
  key: string;
}

export interface UserItem {
  id: number;
  username: string;
  email: string;
  role: "admin" | "operator" | "viewer";
  is_active: boolean;
  created_at: string;
}

// --- Job CRUD types ---

export interface StepFormData {
  name: string;
  command: string;
  timeout_seconds: number | null;
  workdir: string | null;
  environment: Record<string, string> | null;
  user: string | null;
}

export interface ContainerFormData {
  mode: "persistent" | "ephemeral";
  name: string | null;
  image: string | null;
  volumes: Record<string, string> | null;
  network: string | null;
}

export interface ScheduleFormData {
  cron: string;
  timezone: string;
  enabled: boolean;
}

export interface NotifyFormData {
  on_failure: boolean;
  on_success: boolean;
  discord_webhook_url: string | null;
}

export interface JobFormData {
  name: string;
  description: string | null;
  schedule: ScheduleFormData;
  container: ContainerFormData;
  steps: StepFormData[];
  notify: NotifyFormData | null;
  timeout_seconds: number;
}
