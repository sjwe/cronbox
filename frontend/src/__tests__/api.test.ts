import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchJobs, triggerJob, fetchRuns, fetchLogContent } from "../api";

const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal("fetch", mockFetch);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchJobs", () => {
  it("calls /api/jobs and returns parsed JSON", async () => {
    const jobs = [{ name: "test-job" }];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(jobs),
    });

    const result = await fetchJobs();
    expect(mockFetch).toHaveBeenCalledWith("/api/jobs");
    expect(result).toEqual(jobs);
  });
});

describe("fetchJSON (via fetchJobs)", () => {
  it("throws on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
    });

    await expect(fetchJobs()).rejects.toThrow("500 Internal Server Error");
  });
});

describe("triggerJob", () => {
  it("sends POST request to trigger endpoint", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true });

    await triggerJob("my-job");
    expect(mockFetch).toHaveBeenCalledWith("/api/jobs/my-job/trigger", {
      method: "POST",
    });
  });
});

describe("fetchRuns", () => {
  it("builds query string with job_name and per_page", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ runs: [] }),
    });

    await fetchRuns("my-job", 10);
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("job_name=my-job");
    expect(url).toContain("per_page=10");
  });

  it("calls /api/runs with no query string when no params", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ runs: [] }),
    });

    await fetchRuns();
    expect(mockFetch).toHaveBeenCalledWith("/api/runs");
  });
});

describe("fetchLogContent", () => {
  it("returns text content (not JSON)", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: () => Promise.resolve("line1\nline2\nline3"),
    });

    const result = await fetchLogContent("my-job", "output.log");
    expect(result).toBe("line1\nline2\nline3");
  });
});
