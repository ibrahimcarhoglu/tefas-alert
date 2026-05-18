/* TEFAS Platform — Shared TypeScript Interfaces */

export interface Fund {
  code: string;
  name: string;
  price: number | null;
  pct_change: number | null;
  period_return?: number | null;
  return_period?: string;
  management_fee?: number | null;
  net_flow: number | null;
  num_investors: number | null;
  market_cap: number | null;
  investor_change: number | null;
  category: string;
  manager: string;
  risk: "low" | "mid" | "high";
  tefas_status: string;
}

export interface FundListResponse {
  funds: Fund[];
  total: number;
  page: number;
  page_size: number;
  last_date: string;
}

export interface HistoryPoint {
  date: string;
  price: number | null;
  num_investors: number | null;
  net_flow: number | null;
  pct_change: number | null;
  market_cap: number | null;
}

export interface FundPerformance {
  return_1m: number | null;
  return_3m: number | null;
  return_6m: number | null;
  return_1y: number | null;
  max_drawdown: number;
  volatility: number | null;
}

export interface SimilarFund {
  code: string;
  name: string;
  category: string;
  risk: string;
  price: number | null;
  pct_change: number | null;
  return_1m: number | null;
}

export interface FundDetail {
  code: string;
  name: string;
  tefas_status: string;
  category: string;
  manager: string;
  risk: string;
  max_drawdown: number;
  management_fee?: number | null;
  performance?: FundPerformance;
  monthly_returns: Record<string, number>;
  allocation: Record<string, number>;
  history: HistoryPoint[];
}

export interface DashboardTopFund {
  code: string;
  name: string;
  price: number | null;
  pct_change: number | null;
  net_flow: number | null;
  num_investors: number | null;
  market_cap: number | null;
  tefas_status: string;
  prev_price?: number | null;
}

export interface AlertItem {
  date: string;
  code: string;
  alert_type: string;
  value: number | null;
  z_score: number | null;
  message: string;
}

export interface SocialTrend {
  code: string;
  pct: string;
  stat: string;
  reason: string;
  score: number;
  name: string;
  fund_pct_change?: number | null;
  fund_net_flow?: number | null;
  tefas_status: string;
}

export interface DashboardData {
  last_date: string;
  total_funds: number;
  total_inflow: number;
  total_outflow: number;
  top_inflows: DashboardTopFund[];
  top_outflows: DashboardTopFund[];
  top_returns: DashboardTopFund[];
  top_losers: DashboardTopFund[];
  recent_alerts: AlertItem[];
  social_trends: SocialTrend[];
  periodic: Record<string, DashboardTopFund[]>;
}

export interface Manager {
  manager: string;
  fund_count: number;
  total_investors: number;
  total_net_flow: number;
  total_aum: number;
  market_share: number;
  average_return: number;
  low_risk_count: number;
  mid_risk_count: number;
  high_risk_count: number;
}

export interface Category {
  category: string;
  fund_count: number;
  total_net_flow: number;
  total_aum: number;
  average_return: number;
}

export interface CashflowDay {
  date: string;
  inflow: number;
  outflow: number;
  net: number;
}

export interface CashflowData {
  daily: CashflowDay[];
  by_category: { category: string; net_flow: number }[];
  last_date: string;
}

export interface AnomaliesData {
  alerts: AlertItem[];
  stats: {
    total: number;
    avg_zscore: number;
    max_zscore: number;
  };
}
