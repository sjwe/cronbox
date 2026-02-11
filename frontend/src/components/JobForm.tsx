import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJob, createJob, updateJob } from "../api";
import type { JobFormData, StepFormData } from "../types";

const EMPTY_STEP: StepFormData = {
  name: "",
  command: "",
  timeout_seconds: null,
  workdir: null,
  environment: null,
  user: null,
};

const DEFAULT_FORM: JobFormData = {
  name: "",
  description: null,
  schedule: { cron: "0 0 * * *", timezone: "UTC", enabled: true },
  container: { mode: "persistent", name: null, image: null, volumes: null, network: null },
  steps: [{ ...EMPTY_STEP }],
  notify: null,
  timeout_seconds: 7200,
};

export default function JobForm() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEdit = !!name;

  const [form, setForm] = useState<JobFormData>({ ...DEFAULT_FORM, steps: [{ ...EMPTY_STEP }] });
  const [error, setError] = useState<string | null>(null);

  const { data: existingJob } = useQuery({
    queryKey: ["job", name],
    queryFn: () => fetchJob(name!),
    enabled: isEdit,
  });

  // Pre-populate form when editing
  useEffect(() => {
    if (existingJob && isEdit) {
      setForm({
        name: existingJob.name,
        description: existingJob.description,
        schedule: { ...existingJob.schedule },
        container: {
          mode: existingJob.container.mode as "persistent" | "ephemeral",
          name: existingJob.container.name ?? null,
          image: existingJob.container.image ?? null,
          volumes: null,
          network: null,
        },
        steps: existingJob.steps.map((s) => ({
          name: s.name,
          command: s.command,
          timeout_seconds: s.timeout_seconds,
          workdir: null,
          environment: null,
          user: null,
        })),
        notify: null,
        timeout_seconds: 7200,
      });
    }
  }, [existingJob, isEdit]);

  const saveMutation = useMutation({
    mutationFn: async (data: JobFormData) => {
      if (isEdit) {
        const { name: _name, ...rest } = data;
        return updateJob(name!, rest);
      }
      return createJob(data);
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["job", result.job_name] });
      navigate(isEdit ? `/jobs/${result.job_name}` : "/");
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    saveMutation.mutate(form);
  }

  function addStep() {
    setForm({ ...form, steps: [...form.steps, { ...EMPTY_STEP }] });
  }

  function removeStep(index: number) {
    if (form.steps.length <= 1) return;
    setForm({ ...form, steps: form.steps.filter((_, i) => i !== index) });
  }

  function updateStep(index: number, field: keyof StepFormData, value: string | number | null) {
    const steps = [...form.steps];
    steps[index] = { ...steps[index], [field]: value };
    setForm({ ...form, steps });
  }

  function moveStep(index: number, direction: -1 | 1) {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= form.steps.length) return;
    const steps = [...form.steps];
    [steps[index], steps[newIndex]] = [steps[newIndex], steps[index]];
    setForm({ ...form, steps });
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Breadcrumb */}
      <div className="mb-6 text-sm text-gray-500">
        <Link to="/" className="hover:text-gray-300 transition-colors">
          Jobs
        </Link>
        <span className="mx-2">/</span>
        {isEdit ? (
          <>
            <Link to={`/jobs/${name}`} className="hover:text-gray-300 transition-colors">
              {name}
            </Link>
            <span className="mx-2">/</span>
            <span className="text-gray-300">Edit</span>
          </>
        ) : (
          <span className="text-gray-300">New Job</span>
        )}
      </div>

      <h1 className="text-2xl font-bold mb-6">{isEdit ? "Edit Job" : "Create Job"}</h1>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400 mb-6">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Basic Info */}
        <section className="rounded-lg border border-gray-800 bg-gray-900/30 p-6 space-y-4">
          <h2 className="text-lg font-semibold">Basic Info</h2>
          <div className="grid grid-cols-1 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Name</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                disabled={isEdit}
                placeholder="my-job-name"
                className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600 disabled:opacity-50"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Description</label>
              <input
                type="text"
                value={form.description ?? ""}
                onChange={(e) => setForm({ ...form, description: e.target.value || null })}
                placeholder="What this job does"
                className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
          </div>
        </section>

        {/* Schedule */}
        <section className="rounded-lg border border-gray-800 bg-gray-900/30 p-6 space-y-4">
          <h2 className="text-lg font-semibold">Schedule</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Cron Expression</label>
              <input
                type="text"
                value={form.schedule.cron}
                onChange={(e) => setForm({ ...form, schedule: { ...form.schedule, cron: e.target.value } })}
                placeholder="0 4 * * 2-6"
                className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 font-mono focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
              <p className="text-xs text-gray-500 mt-1">minute hour day month day_of_week</p>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Timezone</label>
              <input
                type="text"
                value={form.schedule.timezone}
                onChange={(e) => setForm({ ...form, schedule: { ...form.schedule, timezone: e.target.value } })}
                placeholder="America/New_York"
                className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={form.schedule.enabled}
                onChange={(e) => setForm({ ...form, schedule: { ...form.schedule, enabled: e.target.checked } })}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-gray-700 peer-focus:ring-2 peer-focus:ring-blue-600 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
            <span className="text-sm text-gray-300">Enabled</span>
          </div>
        </section>

        {/* Container */}
        <section className="rounded-lg border border-gray-800 bg-gray-900/30 p-6 space-y-4">
          <h2 className="text-lg font-semibold">Container</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Mode</label>
              <select
                value={form.container.mode}
                onChange={(e) => setForm({
                  ...form,
                  container: { ...form.container, mode: e.target.value as "persistent" | "ephemeral" },
                })}
                className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="persistent">Persistent</option>
                <option value="ephemeral">Ephemeral</option>
              </select>
            </div>
            {form.container.mode === "persistent" ? (
              <div>
                <label className="block text-sm text-gray-400 mb-1">Container Name</label>
                <input
                  type="text"
                  value={form.container.name ?? ""}
                  onChange={(e) => setForm({ ...form, container: { ...form.container, name: e.target.value || null } })}
                  placeholder="my-container"
                  className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
                />
              </div>
            ) : (
              <div>
                <label className="block text-sm text-gray-400 mb-1">Image</label>
                <input
                  type="text"
                  value={form.container.image ?? ""}
                  onChange={(e) => setForm({ ...form, container: { ...form.container, image: e.target.value || null } })}
                  placeholder="python:3.12-slim"
                  className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
                />
              </div>
            )}
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Network (optional)</label>
            <input
              type="text"
              value={form.container.network ?? ""}
              onChange={(e) => setForm({ ...form, container: { ...form.container, network: e.target.value || null } })}
              placeholder="bridge"
              className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>
        </section>

        {/* Steps */}
        <section className="rounded-lg border border-gray-800 bg-gray-900/30 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Steps</h2>
            <button
              type="button"
              onClick={addStep}
              className="rounded-md bg-gray-700 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-600 transition-colors"
            >
              + Add Step
            </button>
          </div>
          <div className="space-y-4">
            {form.steps.map((step, i) => (
              <div key={i} className="rounded-lg border border-gray-700 bg-gray-800/50 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500 font-mono">Step {i + 1}</span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => moveStep(i, -1)}
                      disabled={i === 0}
                      className="rounded px-1.5 py-0.5 text-xs text-gray-400 hover:text-white hover:bg-gray-700 disabled:opacity-30 transition-colors"
                    >
                      &uarr;
                    </button>
                    <button
                      type="button"
                      onClick={() => moveStep(i, 1)}
                      disabled={i === form.steps.length - 1}
                      className="rounded px-1.5 py-0.5 text-xs text-gray-400 hover:text-white hover:bg-gray-700 disabled:opacity-30 transition-colors"
                    >
                      &darr;
                    </button>
                    {form.steps.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeStep(i)}
                        className="rounded px-1.5 py-0.5 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/15 transition-colors ml-2"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Name</label>
                    <input
                      type="text"
                      value={step.name}
                      onChange={(e) => updateStep(i, "name", e.target.value)}
                      placeholder="step-name"
                      className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Timeout (seconds)</label>
                    <input
                      type="number"
                      value={step.timeout_seconds ?? ""}
                      onChange={(e) => updateStep(i, "timeout_seconds", e.target.value ? parseInt(e.target.value) : null)}
                      placeholder="3600"
                      className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Command</label>
                  <textarea
                    value={step.command}
                    onChange={(e) => updateStep(i, "command", e.target.value)}
                    placeholder="/path/to/script.sh"
                    rows={2}
                    className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 font-mono focus:outline-none focus:ring-2 focus:ring-blue-600 resize-y"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Working Directory (optional)</label>
                    <input
                      type="text"
                      value={step.workdir ?? ""}
                      onChange={(e) => updateStep(i, "workdir", e.target.value || null)}
                      placeholder="/app"
                      className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">User (optional)</label>
                    <input
                      type="text"
                      value={step.user ?? ""}
                      onChange={(e) => updateStep(i, "user", e.target.value || null)}
                      placeholder="appuser"
                      className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Notifications */}
        <section className="rounded-lg border border-gray-800 bg-gray-900/30 p-6 space-y-4">
          <h2 className="text-lg font-semibold">Notifications</h2>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={form.notify?.on_failure ?? true}
                onChange={(e) =>
                  setForm({
                    ...form,
                    notify: {
                      on_failure: e.target.checked,
                      on_success: form.notify?.on_success ?? false,
                      discord_webhook_url: form.notify?.discord_webhook_url ?? null,
                    },
                  })
                }
                className="rounded bg-gray-800 border-gray-700 text-blue-600 focus:ring-blue-600"
              />
              Notify on failure
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                checked={form.notify?.on_success ?? false}
                onChange={(e) =>
                  setForm({
                    ...form,
                    notify: {
                      on_failure: form.notify?.on_failure ?? true,
                      on_success: e.target.checked,
                      discord_webhook_url: form.notify?.discord_webhook_url ?? null,
                    },
                  })
                }
                className="rounded bg-gray-800 border-gray-700 text-blue-600 focus:ring-blue-600"
              />
              Notify on success
            </label>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Discord Webhook URL (optional, overrides global)</label>
            <input
              type="text"
              value={form.notify?.discord_webhook_url ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  notify: {
                    on_failure: form.notify?.on_failure ?? true,
                    on_success: form.notify?.on_success ?? false,
                    discord_webhook_url: e.target.value || null,
                  },
                })
              }
              placeholder="https://discord.com/api/webhooks/..."
              className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>
        </section>

        {/* Timeout */}
        <section className="rounded-lg border border-gray-800 bg-gray-900/30 p-6 space-y-4">
          <h2 className="text-lg font-semibold">Job Timeout</h2>
          <div className="max-w-xs">
            <label className="block text-sm text-gray-400 mb-1">Timeout (seconds)</label>
            <input
              type="number"
              value={form.timeout_seconds}
              onChange={(e) => setForm({ ...form, timeout_seconds: parseInt(e.target.value) || 7200 })}
              className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
            <p className="text-xs text-gray-500 mt-1">Overall job timeout in seconds (default: 7200 = 2 hours)</p>
          </div>
        </section>

        {/* Submit */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={saveMutation.isPending || !form.name || form.steps.length === 0}
            className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-500 transition-colors disabled:opacity-50"
          >
            {saveMutation.isPending ? "Saving..." : isEdit ? "Save Changes" : "Create Job"}
          </button>
          <Link
            to={isEdit ? `/jobs/${name}` : "/"}
            className="rounded-lg bg-gray-700 px-6 py-2.5 text-sm font-medium text-gray-300 hover:bg-gray-600 transition-colors"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
