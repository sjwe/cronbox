import { describe, it, expect, vi, afterEach } from "vitest";
import { parseCronSchedule, relativeTime } from "../JobList";

describe("parseCronSchedule", () => {
  it('parses "0 9 * * *" as 9 AM', () => {
    const result = parseCronSchedule("0 9 * * *", "America/New_York");
    expect(result).toContain("9");
    expect(result).toContain("AM");
  });

  it('parses "30 14 * * 1-5" as weekday afternoon', () => {
    const result = parseCronSchedule("30 14 * * 1-5", "America/New_York");
    expect(result).toContain("Mon");
    expect(result).toContain("Fri");
    expect(result).toContain("2:30");
    expect(result).toContain("PM");
  });

  it('parses "0 4 * * 2-6" as Tue-Sat 4 AM', () => {
    const result = parseCronSchedule("0 4 * * 2-6", "US/Eastern");
    expect(result).toContain("Tue");
    expect(result).toContain("Sat");
    expect(result).toContain("4");
    expect(result).toContain("AM");
  });

  it("returns raw string for non-5-part cron", () => {
    expect(parseCronSchedule("*/5 * * * * *", "UTC")).toBe("*/5 * * * * *");
    expect(parseCronSchedule("@daily", "UTC")).toBe("@daily");
  });

  it('parses "0 0 * * *" as 12 AM (midnight)', () => {
    const result = parseCronSchedule("0 0 * * *", "UTC");
    expect(result).toContain("12");
    expect(result).toContain("AM");
  });
});

describe("relativeTime", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns 'ago' for past timestamps", () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60_000).toISOString();
    expect(relativeTime(fiveMinAgo)).toContain("ago");
  });

  it("returns 'in' for future timestamps", () => {
    const fiveMinFromNow = new Date(Date.now() + 5 * 60_000).toISOString();
    expect(relativeTime(fiveMinFromNow)).toContain("in");
  });
});
