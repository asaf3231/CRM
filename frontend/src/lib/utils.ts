import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format an integer with thousands separators, e.g. 1500 -> "1,500". */
export function fmtInt(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}
