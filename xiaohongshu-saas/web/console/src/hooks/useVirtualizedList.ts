import { useEffect, useMemo, useRef, useState } from "react";

interface VirtualItem {
  index: number;
  start: number;
  size: number;
}

/**
 * Lightweight windowed virtualization. Works for any fixed-height row.
 * Returns items to render + total height + offset for the spacer.
 */
export function useVirtualizedList<T>(items: T[], rowHeight = 36, viewport = 600, overscan = 8) {
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onScroll = () => setScrollTop(el.scrollTop);
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  const total = items.length;
  const totalHeight = total * rowHeight;
  const startIdx = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const visibleCount = Math.ceil(viewport / rowHeight) + overscan * 2;
  const endIdx = Math.min(total, startIdx + visibleCount);

  const slice = useMemo(() => items.slice(startIdx, endIdx), [items, startIdx, endIdx]);
  const offsetY = startIdx * rowHeight;

  const virtualItems: VirtualItem[] = slice.map((_, i) => ({
    index: startIdx + i,
    start: (startIdx + i) * rowHeight,
    size: rowHeight,
  }));

  return { containerRef, virtualItems, slice, totalHeight, offsetY, startIdx, endIdx };
}