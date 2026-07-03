import { describe, it, expect } from "vitest";
import { describeCron } from "@/lib/cron";

describe("describeCron", () => {
  it("returns '-' for empty / null", () => {
    expect(describeCron(null)).toBe("-");
    expect(describeCron("")).toBe("-");
    expect(describeCron(undefined)).toBe("-");
  });

  it("returns raw for invalid", () => {
    expect(describeCron("garbage")).toBe("garbage");
  });

  it("daily hour:min", () => {
    expect(describeCron("30 9 * * *")).toMatch(/每天 09:30/);
  });

  it("hourly minute", () => {
    expect(describeCron("15 * * * *")).toMatch(/每小时 15 分/);
  });

  it("weekly dow", () => {
    expect(describeCron("0 18 * * 1")).toMatch(/周1 18:00/);
  });
});