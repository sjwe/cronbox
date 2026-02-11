import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJob, fetchRun, triggerJob, deleteJob } from "../api";
import { useAuth } from "../context/AuthContext";
import type { RunSummary } from "../types";
import StatusBadge from "./StatusBadge";
import LogViewer from "./LogViewer";

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

function RunRow({ run, jobName }: { run: RunSummary; jobName: string }) {
  const [expanded, setExpanded] = useState(false);

  const { data: detail } = useQuery({
    queryKey: ["run", run.id],
    queryFn: () => fetchRun(run.id),
    enabled: expanded,
  });

  return (
    <>
      <tr
        onClick={() => setExpanded((e) => !e)}
        className="border-b border-gray-800/50 hover:bg-gray-900/30 cursor-pointer"
      >
        <td className="px-4 py-2.5">
          <StatusBadge status={run.status} />
        </td>
        <td className="px-4 py-2.5 text-gray-300">{formatTime(run.started_at)}</td>
        <td className="px-4 py-2.5 text-gray-300">{formatDuration(run.duration_seconds)}</td>
        <td className="px-4 py-2.5">
          <span className="text-xs text-gray-500 capitalize">{run.trigger}</span>
        </td>
        <td className="px-4 py-2.5 text-gray-500 text-xs">
          {expanded ? "▾" : "▸"}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-gray-800/50">
          <td colSpan={5} className="px-4 py-3 bg-gray-900/20">
            {detail ? (
              <div>
                {detail.steps.length > 0 && (
                  <div className="mb-3">
                    <h4 className="text-xs font-medium text-gray-400 mb-2">Step Results</h4>
                    <div className="space-y-1">
                      {detail.steps.map((step) => (
                        <div
                          key={step.name}
                          className="flex items-center gap-3 text-xs font-mono"
                        >
                          <span
                            className={
                              step.exit_code === 0
                                ? "text-green-400"
                                : step.exit_code !== null
                                ? "text-red-400"
                                : "text-gray-400"
                            }
                          >
                            {step.exit_code === 0
                              ? "OK"
                              : step.exit_code !== null
                              ? `exit ${step.exit_code}`
                              : step.status}
                          </span>
                          <span className="text-gray-300">{step.name}</span>
                          {step.duration_seconds !== null && (
                            <span className="text-gray-500">
                              {formatDuration(step.duration_seconds)}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {detail.log_file && (
                  <LogViewer jobName={jobName} logFile={detail.log_file} />
                )}
              </div>
            ) : (
              <div className="text-gray-500 text-xs">Loading run details...</div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export default function JobDetailPage() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const { data: job, isLoading, error } = useQuery({
    queryKey: ["job", name],
    queryFn: () => fetchJob(name!),
    enabled: !!name,
    refetchInterval: 10_000,
  });

  const trigger = useMutation({
    mutationFn: () => triggerJob(name!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["job", name] }),
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteJob(name!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate("/");
    },
  });

  if (isLoading) {
    return <div className="text-gray-400 py-12 text-center">Loading...</div>;
  }

  if (error || !job) {
    return (
      <div className="text-red-400 py-12 text-center">
        Failed to load job: {(error as Error)?.message ?? "Not found"}
      </div>
    );
  }

  return (
    <div>
      {/* Breadcrumb */}
      <div className="mb-6 text-sm text-gray-500">
        <Link to="/" className="hover:text-gray-300 transition-colors">
          Jobs
        </Link>
        <span className="mx-2">/</span>
        <span className="text-gray-300">{job.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">{job.name}</h1>
          <p className="text-gray-400 mt-1">{job.description}</p>
          <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
            <span className="font-mono">{job.schedule.cron}</span>
            <span>{job.schedule.timezone}</span>
            {!job.schedule.enabled && (
              <span className="text-yellow-500 font-medium">Disabled</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {user?.role === "admin" && (
            <>
              <Link
                to={`/jobs/${name}/edit`}
                className="rounded-lg bg-gray-700 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-600 transition-colors"
              >
                Edit
              </Link>
              <button
                onClick={() => {
                  if (confirm(`Delete job "${job.name}"? This cannot be undone.`)) {
                    deleteMut.mutate();
                  }
                }}
                disabled={deleteMut.isPending}
                className="rounded-lg bg-red-500/15 px-4 py-2 text-sm font-medium text-red-400 hover:bg-red-500/25 transition-colors disabled:opacity-50"
              >
                {deleteMut.isPending ? "Deleting..." : "Delete"}
              </button>
            </>
          )}
          <button
            onClick={() => trigger.mutate()}
            disabled={trigger.isPending}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors disabled:opacity-50"
          >
            {trigger.isPending ? "Triggering..." : "Trigger Now"}
          </button>
        </div>
      </div>

      {/* Steps */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Steps</h2>
        <div className="space-y-2">
          {job.steps.map((step, i) => (
            <div
              key={step.name}
              className="flex items-center gap-3 rounded-lg border border-gray-800 bg-gray-900/30 px-4 py-3"
            >
              <span className="text-xs text-gray-500 font-mono w-5">{i + 1}</span>
              <span className="font-medium text-gray-200">{step.name}</span>
              <code className="ml-auto text-xs text-gray-500 bg-gray-800 rounded px-2 py-0.5">
                {step.command}
              </code>
            </div>
          ))}
        </div>
      </section>

      {/* Run History */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Run History</h2>
        {job.recent_runs.length === 0 ? (
          <div className="text-gray-500 text-sm">No runs yet.</div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-gray-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900/50 text-left text-gray-400">
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Started</th>
                  <th className="px-4 py-2.5 font-medium">Duration</th>
                  <th className="px-4 py-2.5 font-medium">Trigger</th>
                  <th className="px-4 py-2.5 w-8"></th>
                </tr>
              </thead>
              <tbody>
                {job.recent_runs.map((run) => (
                  <RunRow key={run.id} run={run} jobName={job.name} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
