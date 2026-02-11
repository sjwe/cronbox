import type { JobStatus } from "../types";

const config: Record<JobStatus, { bg: string; text: string; label: string; animate?: boolean }> = {
  success: { bg: "bg-green-500/15", text: "text-green-400", label: "Success" },
  failed: { bg: "bg-red-500/15", text: "text-red-400", label: "Failed" },
  running: { bg: "bg-blue-500/15", text: "text-blue-400", label: "Running", animate: true },
  never_run: { bg: "bg-gray-500/15", text: "text-gray-400", label: "Never run" },
};

export default function StatusBadge({ status }: { status: JobStatus }) {
  const c = config[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${c.bg} ${c.text}`}
    >
      {c.animate && (
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
        </span>
      )}
      {c.label}
    </span>
  );
}
