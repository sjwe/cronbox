import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchLogContent } from "../api";

interface Props {
  jobName: string;
  logFile: string;
}

export function highlightLine(line: string): ReactNode {
  if (line.includes("[STDERR]")) {
    return <span className="text-red-400">{line}</span>;
  }
  if (line.includes("[STDOUT]")) {
    return <span className="text-gray-300">{line}</span>;
  }
  if (/exit code[:\s]+\d+/i.test(line)) {
    const hasNonZero = /exit code[:\s]+[1-9]\d*/i.test(line);
    return <span className={hasNonZero ? "text-red-400 font-bold" : "text-green-400"}>{line}</span>;
  }
  if (/\b(FAIL(ED)?|ERROR)\b/i.test(line)) {
    return <span className="text-red-400">{line}</span>;
  }
  if (/\b(SUCCESS|PASS(ED)?|OK)\b/i.test(line)) {
    return <span className="text-green-400">{line}</span>;
  }
  return <span>{line}</span>;
}

export default function LogViewer({ jobName, logFile }: Props) {
  const [follow, setFollow] = useState(false);
  const containerRef = useRef<HTMLPreElement>(null);

  // Extract just the filename from full path (e.g. "logs/polygon_sync/20260211_040000.log" → "20260211_040000.log")
  const filename = logFile.includes("/") ? logFile.split("/").pop()! : logFile;

  const { data: content } = useQuery({
    queryKey: ["log", jobName, filename],
    queryFn: () => fetchLogContent(jobName, filename),
    refetchInterval: follow ? 3000 : false,
  });

  useEffect(() => {
    if (follow && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [content, follow]);

  // Auto-scroll to bottom on initial load
  useEffect(() => {
    if (content && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [content === undefined]); // only on first load

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500 font-mono">{logFile}</span>
        <button
          onClick={() => setFollow((f) => !f)}
          className={`rounded px-2 py-0.5 text-xs font-medium transition-colors ${
            follow
              ? "bg-blue-500/20 text-blue-400"
              : "bg-gray-800 text-gray-400 hover:text-gray-300"
          }`}
        >
          {follow ? "Following" : "Follow"}
        </button>
      </div>
      <pre
        ref={containerRef}
        className="max-h-96 overflow-auto rounded-lg bg-gray-950 border border-gray-800 p-4 text-xs leading-relaxed font-mono text-gray-400"
      >
        {content
          ? content.split("\n").map((line, i) => (
              <div key={i}>{highlightLine(line)}</div>
            ))
          : "Loading..."}
      </pre>
    </div>
  );
}
