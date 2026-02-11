import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchJobs, triggerJob } from "../api";
import StatusBadge from "./StatusBadge";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function parseCronSchedule(cron: string, timezone: string): string {
  const parts = cron.split(/\s+/);
  if (parts.length !== 5) return cron;
  const [minute, hour, , , dow] = parts;

  const h = parseInt(hour);
  const m = parseInt(minute);
  if (isNaN(h) || isNaN(m)) return cron;

  const period = h >= 12 ? "PM" : "AM";
  const displayHour = h === 0 ? 12 : h > 12 ? h - 12 : h;
  const displayMin = m === 0 ? "" : `:${String(m).padStart(2, "0")}`;

  let dayStr = "";
  if (dow !== "*") {
    const dayParts = dow.split(",").flatMap((part) => {
      const range = part.match(/^(\d)-(\d)$/);
      if (range) {
        const start = parseInt(range[1]);
        const end = parseInt(range[2]);
        const days: string[] = [];
        for (let i = start; i <= end; i++) days.push(WEEKDAYS[i]);
        return days;
      }
      const idx = parseInt(part);
      return isNaN(idx) ? [part] : [WEEKDAYS[idx]];
    });
    dayStr = dayParts.join("-") + " ";
  }

  const tz = timezone.includes("/")
    ? timezone.split("/").pop()!.replace(/_/g, " ")
    : timezone;

  return `${dayStr}${displayHour}${displayMin} ${period} ${tz}`;
}

export function relativeTime(iso: string): string {
  const now = Date.now();
  const target = new Date(iso).getTime();
  const diff = target - now;
  const abs = Math.abs(diff);

  if (abs < 60_000) return diff > 0 ? "in <1m" : "<1m ago";

  const minutes = Math.floor(abs / 60_000);
  if (minutes < 60) return diff > 0 ? `in ${minutes}m` : `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return diff > 0 ? `in ${hours}h` : `${hours}h ago`;

  const days = Math.floor(hours / 24);
  return diff > 0 ? `in ${days}d` : `${days}d ago`;
}

export default function JobList() {
  const queryClient = useQueryClient();
  const { data: jobs, isLoading, error } = useQuery({
    queryKey: ["jobs"],
    queryFn: fetchJobs,
    refetchInterval: 10_000,
  });

  const trigger = useMutation({
    mutationFn: triggerJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });

  if (isLoading) {
    return <div className="text-gray-400 py-12 text-center">Loading jobs...</div>;
  }

  if (error) {
    return (
      <div className="text-red-400 py-12 text-center">
        Failed to load jobs: {(error as Error).message}
      </div>
    );
  }

  if (!jobs || jobs.length === 0) {
    return <div className="text-gray-400 py-12 text-center">No jobs configured.</div>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Jobs</h1>
      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 bg-gray-900/50 text-left text-gray-400">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Schedule</th>
              <th className="px-4 py-3 font-medium">Next Run</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Last Run</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.name} className="border-b border-gray-800/50 hover:bg-gray-900/30">
                <td className="px-4 py-3">
                  <Link
                    to={`/jobs/${job.name}`}
                    className="font-medium text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    {job.name}
                  </Link>
                  <div className="text-xs text-gray-500 mt-0.5">{job.description}</div>
                </td>
                <td className="px-4 py-3 text-gray-300">
                  {job.schedule.enabled ? (
                    parseCronSchedule(job.schedule.cron, job.schedule.timezone)
                  ) : (
                    <span className="text-gray-500 italic">disabled</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-300">
                  {job.next_run_time ? relativeTime(job.next_run_time) : "—"}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={job.last_run?.status ?? "never_run"} />
                </td>
                <td className="px-4 py-3 text-gray-300">
                  {job.last_run ? relativeTime(job.last_run.started_at) : "—"}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => trigger.mutate(job.name)}
                    disabled={trigger.isPending}
                    className="rounded bg-gray-800 px-3 py-1 text-xs font-medium text-gray-300 hover:bg-gray-700 hover:text-white transition-colors disabled:opacity-50"
                  >
                    Trigger
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
