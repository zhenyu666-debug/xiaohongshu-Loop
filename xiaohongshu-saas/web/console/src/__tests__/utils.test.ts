import { describe, it, expect } from "vitest";
import { cn, formatDate, formatNumber } from "@/lib/utils";

describe("cn", () => {
  it("merges classes and dedupes", () => {
    expect(cn("px-2 py-1", "px-4")).toBe("py-1 px-4");
  });
  it("handles falsy", () => {
    expect(cn("a", false, null, undefined, "b")).toBe("a b");
  });
});

describe("formatDate", () => {
  it("returns fallback for null", () => {
    expect(formatDate(null)).toBe("-");
  });
  it("returns fallback for invalid date", () => {
    expect(formatDate("not-a-date")).toBe("-");
  });
  it("formats ISO string", () => {
    const r = formatDate("2026-01-02T03:04:05Z");
    expect(r).toMatch(/2026/);
  });
});

describe("formatNumber", () => {
  it("formats int", () => {
    expect(formatNumber(1234567)).toMatch(/1,234,567/);
  });
  it("returns fallback for null", () => {
    expect(formatNumber(null)).toBe("-");
  });
});