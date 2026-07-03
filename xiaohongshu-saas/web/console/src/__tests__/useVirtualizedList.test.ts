import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useVirtualizedList } from "@/hooks/useVirtualizedList";

describe("useVirtualizedList", () => {
  it("renders initial visible window + offset 0", () => {
    const items = Array.from({ length: 1000 }, (_, i) => i);
    const { result } = renderHook(() => useVirtualizedList(items, 40, 600));
    expect(result.current.slice.length).toBeGreaterThan(0);
    expect(result.current.offsetY).toBe(0);
    expect(result.current.totalHeight).toBe(1000 * 40);
  });

  it("caps visible window", () => {
    const items = Array.from({ length: 5000 }, (_, i) => i);
    const { result } = renderHook(() => useVirtualizedList(items, 40, 400));
    // 400/40=10 rows + 2*overscan = 26
    expect(result.current.slice.length).toBeLessThanOrEqual(30);
  });

  it("small list returns all items", () => {
    const items = [1, 2, 3];
    const { result } = renderHook(() => useVirtualizedList(items, 40, 600));
    expect(result.current.slice.length).toBe(3);
  });
});