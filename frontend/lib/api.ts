/* TEFAS Platform — SWR Data Hooks */
import useSWR from "swr";
import type {
  DashboardData,
  FundListResponse,
  FundDetail,
  HistoryPoint,
  Manager,
  Category,
  CashflowData,
  AnomaliesData,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "";

async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(`${API}${url}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export function useDashboard() {
  return useSWR<DashboardData>("/api/dashboard", fetcher, {
    refreshInterval: 5 * 60 * 1000,
  });
}

export function useFunds(params: Record<string, string | number>) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== "" && v !== undefined && v !== null) qs.set(k, String(v));
  });
  return useSWR<FundListResponse>(`/api/funds?${qs.toString()}`, fetcher);
}

export function useFundDetail(code: string | null) {
  return useSWR<FundDetail>(code ? `/api/fund/${code}` : null, fetcher);
}

export function useFundHistory(code: string | null, days = 30) {
  return useSWR<{ code: string; days: number; history: HistoryPoint[] }>(
    code ? `/api/fund/${code}/history?days=${days}` : null,
    fetcher
  );
}

export function useManagers() {
  return useSWR<Manager[]>("/api/managers", fetcher, {
    refreshInterval: 10 * 60 * 1000,
  });
}

export function useCategories() {
  return useSWR<Category[]>("/api/categories", fetcher, {
    refreshInterval: 10 * 60 * 1000,
  });
}

export function useCashflow(days = 30) {
  return useSWR<CashflowData>(`/api/cashflow?days=${days}`, fetcher);
}

export function useAnomalies(limit = 50, alertType?: string, minZscore?: number) {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (alertType) qs.set("alert_type", alertType);
  if (minZscore !== undefined) qs.set("min_zscore", String(minZscore));
  return useSWR<AnomaliesData>(`/api/anomalies?${qs.toString()}`, fetcher);
}

export function useSocial(codes?: string[]) {
  const qs = codes && codes.length > 0 ? `?codes=${codes.join(",")}` : "";
  return useSWR<{ trends: import("./types").SocialTrend[]; date: string | null }>(
    `/api/social${qs}`,
    fetcher
  );
}

export function useSimilarFunds(code: string | null) {
  return useSWR<{ funds: import("./types").SimilarFund[]; source_code: string }>(
    code ? `/api/fund/${code}/similar` : null,
    fetcher
  );
}

export function usePortfolioSummary(sessionId: string | null) {
  return useSWR<any>(
    sessionId ? `/api/portfolio/summary?session_id=${sessionId}` : null,
    fetcher
  );
}

export function usePortfolioTransactions(sessionId: string | null) {
  return useSWR<any>(
    sessionId ? `/api/portfolio/transactions?session_id=${sessionId}` : null,
    fetcher
  );
}

export function usePortfolioAllocation(sessionId: string | null) {
  return useSWR<any>(
    sessionId ? `/api/portfolio/allocation?session_id=${sessionId}` : null,
    fetcher
  );
}

export function usePortfolioAlerts(sessionId: string | null) {
  return useSWR<any>(
    sessionId ? `/api/portfolio/alerts?session_id=${sessionId}` : null,
    fetcher
  );
}

export function usePortfolioNotifications(sessionId: string | null) {
  return useSWR<any>(
    sessionId ? `/api/portfolio/notifications?session_id=${sessionId}` : null,
    fetcher,
    { refreshInterval: 30000 } // Canlı bildirimler için 30 saniyede bir otomatik yenile
  );
}

export function usePortfolioPerformance(sessionId: string | null) {
  return useSWR<any>(
    sessionId ? `/api/portfolio/performance?session_id=${sessionId}` : null,
    fetcher
  );
}

export async function createPortfolioAlert(sessionId: string, code: string, threshold: number) {
  const res = await fetch("/api/portfolio/alerts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, code, threshold }),
  });
  if (!res.ok) throw new Error("Alarm kuralı oluşturulamadı");
  return res.json();
}

export async function deletePortfolioAlert(alertId: number) {
  const res = await fetch(`/api/portfolio/alerts/${alertId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Alarm kuralı silinemedi");
  return res.json();
}

export async function runInvestmentSimulation(code: string, amount: number, startDate: string) {
  const qs = new URLSearchParams({ code, amount: String(amount), start_date: startDate });
  const res = await fetch(`/api/simulator/run?${qs.toString()}`);
  if (!res.ok) throw new Error("Simülasyon çalıştırılamadı");
  return res.json();
}

export async function getAiFundInterpretation(code: string, riskProfile?: string) {
  const qs = new URLSearchParams({ code });
  if (riskProfile) qs.set("risk_profile", riskProfile);
  const res = await fetch(`/api/ai/interpret?${qs.toString()}`);
  if (!res.ok) throw new Error("Yapay zeka analiz motorundan yanıt alınamadı");
  return res.json();
}

export async function getAiPortfolioReview(sessionId: string) {
  const qs = new URLSearchParams({ session_id: sessionId });
  const res = await fetch(`/api/ai/portfolio-review?${qs.toString()}`);
  if (!res.ok) throw new Error("Yapay zeka portföy incelemesinden yanıt alınamadı");
  return res.json();
}

export async function bulkImportTransactions(
  sessionId: string,
  transactions: { code: string; tx_type?: string; date: string; units: number; unit_price: number }[]
) {
  const res = await fetch("/api/portfolio/transactions/bulk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, transactions }),
  });
  if (!res.ok) throw new Error("CSV içe aktarma başarısız");
  return res.json();
}

