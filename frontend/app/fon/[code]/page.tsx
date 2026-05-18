"use client";

import { useFundDetail, useFundHistory, useSimilarFunds, getAiFundInterpretation } from "@/lib/api";
import { formatTL, formatNumber, formatPct, formatPrice, pctColor, riskColor, riskLabel } from "@/lib/formatters";
import Skeleton from "@/components/ui/Skeleton";
import Badge from "@/components/ui/Badge";
import StatCard from "@/components/ui/StatCard";
import GlossaryTerm from "@/components/ui/GlossaryTerm";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, TrendingUp, TrendingDown, Shield, Briefcase, Star, Sparkles, X } from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import { useState, useMemo } from "react";
import { useWatchlist } from "@/lib/watchlist";

const PIE_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#f43f5e", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"];

const RANGES = [
  { value: "1W", label: "1H", labelFull: "1 Hafta", days: 7 },
  { value: "1M", label: "1A", labelFull: "1 Ay", days: 30 },
  { value: "3M", label: "3A", labelFull: "3 Ay", days: 90 },
  { value: "1Y", label: "1Y", labelFull: "1 Yıl", days: 365 },
  { value: "3Y", label: "3Y", labelFull: "3 Yıl", days: 1095 },
];

export default function FonDetayPage() {
  const params = useParams();
  const code = typeof params.code === "string" ? params.code.toUpperCase() : "";
  const { data, isLoading } = useFundDetail(code);

  const { watchlist, isFavorite, toggleFavorite } = useWatchlist();
  const [range, setRange] = useState<"1W" | "1M" | "3M" | "1Y" | "3Y">("1M");

  const days = useMemo(() => {
    switch (range) {
      case "1W": return 7;
      case "1M": return 30;
      case "3M": return 90;
      case "1Y": return 365;
      case "3Y": return 1095;
      default: return 30;
    }
  }, [range]);

  const { data: historyData, isLoading: isHistoryLoading } = useFundHistory(code, days);
  const { data: similarData } = useSimilarFunds(code);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState<string | null>(null);

  const handleAiInterpret = async () => {
    setAiOpen(true);
    setAiLoading(true);
    setAiResult(null);
    try {
      const res = await getAiFundInterpretation(code);
      setAiResult(res.analysis || "Analiz boş döndü.");
    } catch {
      setAiResult("AI analizi alınamadı. GEMINI_API_KEY tanımlı mı kontrol edin.");
    } finally {
      setAiLoading(false);
    }
  };

  if (isLoading || !data) {
    return (
      <div className="mx-auto max-w-[1600px] p-6">
        <Skeleton count={6} />
      </div>
    );
  }

  const last = data.history[data.history.length - 1];
  const first = data.history[0];
  const periodReturn = last && first && first.price
    ? ((last.price! - first.price) / first.price * 100)
    : 0;

  // Pie chart data from allocation
  const allocEntries = Object.entries(data.allocation || {}).filter(([, v]) => v > 0);
  const pieData = allocEntries.map(([k, v]) => ({ name: k, value: v }));

  // Monthly heatmap
  const monthEntries = Object.entries(data.monthly_returns || {}).sort();

  // Dynamic history charts data
  const chartsHistory = historyData?.history || data.history;

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-6">
      {/* Back + Header */}
      <div className="flex items-start gap-4">
        <Link
          href="/fonlar"
          className="mt-1 rounded-lg bg-white/5 p-2 text-zinc-400 transition-colors hover:bg-white/10 hover:text-white"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <span className="rounded-lg bg-blue-500/15 px-3 py-1.5 font-mono text-lg font-extrabold text-blue-400">
              {data.code}
            </span>
            <button
              onClick={() => toggleFavorite(data.code)}
              className="rounded-lg bg-white/5 p-2 text-zinc-400 hover:bg-white/10 hover:text-amber-400 transition-all cursor-pointer"
              title={isFavorite(data.code) ? "İzleme Listesinden Çıkar" : "İzleme Listesine Ekle"}
            >
              <Star className={`h-5 w-5 ${isFavorite(data.code) ? "fill-amber-400 text-amber-400" : ""}`} />
            </button>
            <Badge className={riskColor(data.risk)}>{riskLabel(data.risk)}</Badge>
            <span className="rounded-md bg-white/5 px-2 py-0.5 text-xs text-zinc-400">{data.category}</span>
            <span className={`rounded-md px-2 py-0.5 text-xs font-bold ${data.tefas_status === "Açık" ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"}`}>
              {data.tefas_status}
            </span>
            <button
              onClick={handleAiInterpret}
              className="ml-auto flex items-center gap-1.5 rounded-lg bg-purple-500/15 border border-purple-500/30 px-3 py-1.5 text-xs font-bold text-purple-300 hover:bg-purple-500/25 transition-all cursor-pointer"
            >
              <Sparkles className="h-3.5 w-3.5" />
              AI Yorum
            </button>
          </div>
          <h1 className="mt-2 text-lg font-bold text-zinc-200">{data.name}</h1>
          <p className="mt-1 text-xs text-zinc-500">
            <Briefcase className="mr-1 inline h-3 w-3" />
            {data.manager}
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard
          label="Son Fiyat"
          value={formatPrice(last?.price)}
          color="blue"
          icon={<TrendingUp className="h-4 w-4" />}
        />
        <StatCard
          label={<GlossaryTerm term="30 Gün Getiri">Dönem Getirisi</GlossaryTerm>}
          value={formatPct(periodReturn)}
          color={periodReturn >= 0 ? "green" : "red"}
          icon={periodReturn >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
        />
        <StatCard
          label={<GlossaryTerm term="Max Drawdown" />}
          value={`-${data.max_drawdown.toFixed(2)}%`}
          color="red"
          icon={<Shield className="h-4 w-4" />}
        />
        <StatCard
          label="Yatırımcı"
          value={formatNumber(last?.num_investors)}
          sub={`AUM: ${formatTL(last?.market_cap)}`}
          color="blue"
        />
      </div>

      {data.performance && (
        <div className="glass p-5 space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400">
            <GlossaryTerm term="KYD">Performans & KYD</GlossaryTerm>
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {[
              { label: "1 Ay", value: data.performance.return_1m },
              { label: "3 Ay", value: data.performance.return_3m },
              { label: "6 Ay", value: data.performance.return_6m },
              { label: "1 Yıl", value: data.performance.return_1y },
              { label: "Max DD", value: data.performance.max_drawdown != null ? -data.performance.max_drawdown : null, glossary: "Max Drawdown" },
              { label: "Volatilite", value: data.performance.volatility, glossary: "Volatilite" },
            ].map((m) => (
              <div key={m.label} className="rounded-xl border border-white/6 bg-white/2 p-3 text-center">
                <div className="text-[10px] text-zinc-500 mb-1">
                  {m.glossary ? <GlossaryTerm term={m.glossary}>{m.label}</GlossaryTerm> : m.label}
                </div>
                <div className={`text-sm font-extrabold tabular-nums ${pctColor(m.value)}`}>
                  {m.value != null ? `${m.value > 0 && m.label !== "Max DD" ? "+" : ""}${m.value.toFixed(2)}%` : "veri yok"}
                </div>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-zinc-500">
            <GlossaryTerm term="Yönetim Ücreti">Yönetim ücreti</GlossaryTerm>:{" "}
            {data.management_fee != null ? `%${data.management_fee.toFixed(2)} (tahmini)` : "veri yok"}
          </p>
        </div>
      )}

      {similarData?.funds && similarData.funds.length > 0 && (
        <div className="glass p-5 space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Benzer Fonlar</h2>
          <div className="flex flex-wrap gap-2">
            {similarData.funds.map((sf) => (
              <Link key={sf.code} href={`/fon/${sf.code}`} className="rounded-xl border border-white/8 bg-white/3 px-3 py-2 hover:border-blue-500/40 transition-colors">
                <span className="font-mono text-xs font-bold text-blue-400">{sf.code}</span>
                <span className={`ml-2 text-xs font-semibold ${pctColor(sf.return_1m)}`}>{formatPct(sf.return_1m)}</span>
                <span className="block text-[10px] text-zinc-500 truncate max-w-[180px]">{sf.name}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Timeframe Selector & Charts */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Performans Analizi</h2>
          <div className="flex items-center gap-1 rounded-xl bg-white/5 p-1 border border-white/5">
            {RANGES.map((r) => (
              <button
                key={r.value}
                onClick={() => setRange(r.value as any)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
                  range === r.value
                    ? "bg-blue-500 text-white shadow-md shadow-blue-500/25"
                    : "text-zinc-400 hover:text-white"
                }`}
                title={r.labelFull}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Price Chart */}
          <div className="glass p-5 relative overflow-hidden">
            <h3 className="mb-4 text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center justify-between">
              <span>Fiyat Grafiği</span>
              <span className="text-[10px] text-zinc-500 font-mono capitalize">
                {range === "1W" ? "1 Hafta" : range === "1M" ? "1 Ay" : range === "3M" ? "3 Ay" : range === "1Y" ? "1 Yıl" : "3 Yıl"}
              </span>
            </h3>
            <div className={`transition-opacity duration-300 ${isHistoryLoading ? "opacity-50" : "opacity-100"}`}>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartsHistory}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10, fill: "#64748b" }}
                    tickFormatter={(d: string) => d.slice(5)}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#64748b" }}
                    domain={["auto", "auto"]}
                    tickFormatter={(v: number) => v.toFixed(3)}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(15,23,42,0.95)",
                      border: "1px solid rgba(255,255,255,0.1)",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="price"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, fill: "#3b82f6" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Net Flow Bar Chart */}
          <div className="glass p-5 relative overflow-hidden">
            <h3 className="mb-4 text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center justify-between">
              <span>Net Para Giriş/Çıkışı</span>
              <span className="text-[10px] text-zinc-500 font-mono capitalize">
                {range === "1W" ? "1 Hafta" : range === "1M" ? "1 Ay" : range === "3M" ? "3 Ay" : range === "1Y" ? "1 Yıl" : "3 Yıl"}
              </span>
            </h3>
            <div className={`transition-opacity duration-300 ${isHistoryLoading ? "opacity-50" : "opacity-100"}`}>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartsHistory}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10, fill: "#64748b" }}
                    tickFormatter={(d: string) => d.slice(5)}
                  />
                  <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickFormatter={(v: number) => `${(v / 1e6).toFixed(0)}M`} />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(15,23,42,0.95)",
                      border: "1px solid rgba(255,255,255,0.1)",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                    formatter={(v: number) => formatTL(v)}
                  />
                  <Bar dataKey="net_flow" radius={[4, 4, 0, 0]}>
                    {chartsHistory.map((h, i) => (
                      <Cell key={i} fill={h.net_flow && h.net_flow >= 0 ? "#10b981" : "#f43f5e"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>

      {/* Second row: Allocation + Heatmap */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Allocation Pie */}
        {pieData.length > 0 && (
          <div className="glass p-5">
            <h3 className="mb-4 text-xs font-bold uppercase tracking-wider text-zinc-400">
              Portföy Dağılımı
            </h3>
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}%`}
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Monthly Heatmap */}
        {monthEntries.length > 0 && (
          <div className="glass p-5">
            <h3 className="mb-4 text-xs font-bold uppercase tracking-wider text-zinc-400">
              Aylık Getiri Haritası
            </h3>
            <div className="grid grid-cols-4 gap-3 sm:grid-cols-6">
              {monthEntries.map(([month, ret]) => {
                const bg = ret > 2 ? "bg-emerald-500/30" : ret > 0 ? "bg-emerald-500/15" : ret > -2 ? "bg-rose-500/15" : "bg-rose-500/30";
                const text = ret >= 0 ? "text-emerald-400" : "text-rose-400";
                return (
                  <div
                    key={month}
                    className={`flex flex-col items-center justify-center rounded-xl border border-white/4 p-3 ${bg}`}
                  >
                    <span className="text-[0.6rem] text-zinc-400">{month}</span>
                    <span className={`text-sm font-extrabold ${text}`}>{formatPct(ret)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {aiOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass w-full max-w-2xl p-6 space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-white/8 pb-3">
              <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-purple-400" />
                {code} — AI Yorum
              </h3>
              <button onClick={() => setAiOpen(false)} className="text-zinc-400 hover:text-white cursor-pointer">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto text-xs text-zinc-200 whitespace-pre-line leading-relaxed">
              {aiLoading ? "Analiz hazırlanıyor..." : aiResult}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
