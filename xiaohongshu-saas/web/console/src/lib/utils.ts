import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const FALLBACK = "-";

function safeDate(value: Date | string | number | null | undefined): Date | null {
  if (value === null || value === undefined || value === "") return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(
  value: Date | string | number | null | undefined,
  fallback: string = FALLBACK
): string {
  const d = safeDate(value);
  if (!d) return fallback;
  return d.toISOString().slice(0, 10);
}

export function formatNumber(
  value: number | null | undefined,
  fallback: string = FALLBACK
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return value.toLocaleString("en-US");
}
