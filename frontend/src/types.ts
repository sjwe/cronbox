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
