"use client";

import { useManagers } from "@/lib/api";
import { formatTL, formatNumber, formatPct, pctColor } from "@/lib/formatters";
import Skeleton from "@/components/ui/Skeleton";
import { Briefcase, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

const PIE_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#f43f5e", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"];

export default function YoneticilerPage() {
  const { data, isLoading } = useManagers();
  const [sortBy, setSortBy] = useState<string>("total_aum");
  const [order, setOrder] = useState("desc");

  if (isLoading || !data) {
    return <div className="mx-auto max-w-[1600px] p-6"><Skeleton count={10} /></div>;
  }

  const sorted = [...data].sort((a, b) => {
    const av = (a as Record<string, unknown>)[sortBy] as number;
    const bv = (b as Record<string, unknown>)[sortBy] as number;
    return order === "desc" ? bv - av : av - bv;
  });

  const toggleSort = (col: string) => {
    if (sortBy === col) setOrder(order === "desc" ? "asc" : "desc");
    else { setSortBy(col); setOrder("desc"); }
  };

  const SortIcon = ({ col }: { col: string }) => {
    if (sortBy !== col) return null;
    return order === "desc" ? <ChevronDown className="inline h-3.5 w-3.5 text-blue-400" /> : <ChevronUp className="inline h-3.5 w-3.5 text-blue-400" />;
  };

  const top10 = sorted.slice(0, 10).map((m) => ({ name: m.manager.replace(" PORTFÖY YÖNETİMİ A.Ş.", ""), value: m.total_aum }));

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Briefcase className="h-6 w-6 text-blue-400" />
        <h1 className="text-xl font-extrabold tracking-tight">Yönetici Analizi</h1>
        <span className="text-sm text-zinc-400">· {data.length} portföy yönetim şirketi</span>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="glass p-5 lg:col-span-1">
          <h3 className="mb-4 text-xs font-bold uppercase tracking-wider text-zinc-400">AUM Dağılımı (Top 10)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={top10} cx="50%" cy="50%" innerRadius={50} outerRadius={90} paddingAngle={2} dataKey="value" label={({ name }) => name}>
                {top10.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip formatter={(v: number) => formatTL(v)} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="glass overflow-hidden lg:col-span-2">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-[#0a1020]">
                <tr className="text-left text-[0.7rem] uppercase tracking-wider text-zinc-500">
                  <th className="px-5 py-3">Yönetici</th>
                  <th className="cursor-pointer px-3 py-3 text-right" onClick={() => toggleSort("fund_count")}>Fon <SortIcon col="fund_count" /></th>
                  <th className="cursor-pointer px-3 py-3 text-right" onClick={() => toggleSort("total_aum")}>AUM <SortIcon col="total_aum" /></th>
                  <th className="cursor-pointer px-3 py-3 text-right" onClick={() => toggleSort("market_share")}>Pay % <SortIcon col="market_share" /></th>
                  <th className="cursor-pointer px-3 py-3 text-right" onClick={() => toggleSort("total_net_flow")}>Net Akış <SortIcon col="total_net_flow" /></th>
                  <th className="cursor-pointer px-3 py-3 text-right" onClick={() => toggleSort("average_return")}>Ort. Getiri <SortIcon col="average_return" /></th>
                  <th className="cursor-pointer px-3 py-3 text-right" onClick={() => toggleSort("total_investors")}>Yatırımcı <SortIcon col="total_investors" /></th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((m) => (
                  <tr key={m.manager} className="border-t border-white/3 hover:bg-white/3">
                    <td className="max-w-[250px] truncate px-5 py-3 text-xs font-medium text-zinc-200">{m.manager}</td>
                    <td className="px-3 py-3 text-right text-xs">{m.fund_count}</td>
                    <td className="px-3 py-3 text-right text-xs font-semibold">{formatTL(m.total_aum)}</td>
                    <td className="px-3 py-3 text-right text-xs text-zinc-400">{m.market_share}%</td>
                    <td className={`px-3 py-3 text-right text-xs font-bold ${m.total_net_flow >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{formatTL(m.total_net_flow)}</td>
                    <td className={`px-3 py-3 text-right text-xs font-bold ${pctColor(m.average_return)}`}>{formatPct(m.average_return)}</td>
                    <td className="px-3 py-3 text-right text-xs text-zinc-400">{formatNumber(m.total_investors)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
