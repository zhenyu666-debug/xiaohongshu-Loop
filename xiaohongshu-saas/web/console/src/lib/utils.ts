import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(input: string | Date | null | undefined, fallback = "-"): string {
  if (!input) return fallback;
  const d = typeof input === "string" ? new Date(input) : input;
  if (Number.isNaN(d.getTime())) return fallback;
  return d.toLocaleString("zh-CN", { hour12: false });
}

export function formatNumber(n: number | null | undefined, fallback = "-"): string {
  if (n === null || n === undefined || Number.isNaN(n)) return fallback;
  return new Intl.NumberFormat("zh-CN").format(n);
}
