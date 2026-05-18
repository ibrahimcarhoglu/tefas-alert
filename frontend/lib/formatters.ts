/* TEFAS Platform — Formatting Utilities */

/** Format large numbers with Turkish locale: 1.234.567 */
export function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("tr-TR", { maximumFractionDigits: 0 });
}

/** Format currency (TL): ₺1.234.567 */
export function formatTL(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1e9) return `₺${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `₺${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `₺${(n / 1e3).toFixed(0)}K`;
  return `₺${n.toLocaleString("tr-TR")}`;
}

/** Format percentage: +2.35% or -1.20% */
export function formatPct(n: number | null | undefined): string {
  if (n == null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

/** Format price: 1,2345 */
export function formatPrice(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("tr-TR", { minimumFractionDigits: 4, maximumFractionDigits: 4 });
}

/** Return CSS class for positive/negative */
export function pctColor(n: number | null | undefined): string {
  if (n == null) return "text-zinc-400";
  if (n > 0) return "text-emerald-400";
  if (n < 0) return "text-rose-400";
  return "text-zinc-400";
}

/** Risk badge color */
export function riskColor(risk: string): string {
  switch (risk) {
    case "low": return "bg-emerald-500/15 text-emerald-400 border-emerald-500/20";
    case "high": return "bg-rose-500/15 text-rose-400 border-rose-500/20";
    default: return "bg-amber-500/15 text-amber-400 border-amber-500/20";
  }
}

/** Pie chart slice color by risk */
export function riskSliceColor(risk: string): string {
  switch (risk) {
    case "low": return "#10b981";
    case "high": return "#f43f5e";
    default: return "#f59e0b";
  }
}

export function riskLabel(risk: string): string {
  switch (risk) {
    case "low": return "Düşük";
    case "high": return "Yüksek";
    default: return "Orta";
  }
}
