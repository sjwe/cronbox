import { describe, it, expect } from "vitest";
import { isValidElement, type ReactElement } from "react";
import { highlightLine } from "../LogViewer";

function getClassName(node: ReturnType<typeof highlightLine>): string | undefined {
  if (isValidElement(node)) {
    return (node as ReactElement<{ className?: string }>).props.className;
  }
  return undefined;
}

describe("highlightLine", () => {
  it("highlights [STDERR] lines in red", () => {
    const result = highlightLine("2024-01-01 [STDERR] something failed");
    const cls = getClassName(result);
    expect(cls).toContain("text-red");
  });

  it("highlights [STDOUT] lines in gray", () => {
    const result = highlightLine("2024-01-01 [STDOUT] output here");
    const cls = getClassName(result);
    expect(cls).toContain("text-gray");
  });

  it("highlights exit code 0 in green", () => {
    const result = highlightLine("Process exit code: 0");
    const cls = getClassName(result);
    expect(cls).toContain("text-green");
  });

  it("highlights non-zero exit code in red", () => {
    const result = highlightLine("Process exit code: 1");
    const cls = getClassName(result);
    expect(cls).toContain("text-red");
  });

  it("highlights FAILED keyword in red", () => {
    const result = highlightLine("Test FAILED with errors");
    const cls = getClassName(result);
    expect(cls).toContain("text-red");
  });

  it("highlights ERROR keyword in red", () => {
    const result = highlightLine("ERROR: connection refused");
    const cls = getClassName(result);
    expect(cls).toContain("text-red");
  });

  it("returns unstyled element for plain lines", () => {
    const result = highlightLine("just a regular log line");
    const cls = getClassName(result);
    expect(cls).toBeUndefined();
  });
});
