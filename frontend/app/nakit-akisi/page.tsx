"use client";

import { useCashflow } from "@/lib/api";
import { formatTL } from "@/lib/formatters";
import Skeleton from "@/components/ui/Skeleton";
import { Droplets } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie,
} from "recharts";

const PIE_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#f43f5e", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16", "#64748b"];

export default function NakitAkisiPage() {
  const { data, isLoading } = useCashflow(30);

  if (isLoading || !data) {
    return (
      <div className="mx-auto max-w-[1600px] p-6">
        <Skeleton count={6} />
      </div>
    );
  }

  const totalInflow = data.daily.reduce((s, d) => s + (d.inflow || 0), 0);
  const totalOutflow = data.daily.reduce((s, d) => s + (d.outflow || 0), 0);

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Droplets className="h-6 w-6 text-blue-400" />
        <div>
          <h1 className="text-xl font-extrabold tracking-tight">Nakit Akışı</h1>
          <p className="text-sm text-zinc-400">Son 30 günlük market toplam akışı · {data.last_date}</p>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="glass p-5">
          <div className="text-[0.7rem] font-bold uppercase tracking-wider text-zinc-400">Toplam Giriş</div>
          <div className="mt-2 text-2xl font-extrabold text-emerald-400">{formatTL(totalInflow)}</div>
        </div>
        <div className="glass p-5">
          <div className="text-[0.7rem] font-bold uppercase tracking-wider text-zinc-400">Toplam Çıkış</div>
          <div className="mt-2 text-2xl font-extrabold text-rose-400">{formatTL(totalOutflow)}</div>
        </div>
        <div className="glass p-5">
          <div className="text-[0.7rem] font-bold uppercase tracking-wider text-zinc-400">Net</div>
          <div className={`mt-2 text-2xl font-extrabold ${totalInflow + totalOutflow >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {formatTL(totalInflow + totalOutflow)}
          </div>
        </div>
      </div>

      {/* Daily Bar Chart */}
      <div className="glass p-5">
        <h3 className="mb-4 text-xs font-bold uppercase tracking-wider text-zinc-400">
          Günlük Net Akış
        </h3>
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={data.daily}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "#64748b" }}
              tickFormatter={(d: string) => d.slice(5)}
            />
            <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickFormatter={(v: number) => `${(v / 1e9).toFixed(1)}B`} />
            <Tooltip
              contentStyle={{
                background: "rgba(15,23,42,0.95)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 12,
                fontSize: 12,
              }}
              formatter={(v: number) => formatTL(v)}
            />
            <Bar dataKey="net" radius={[4, 4, 0, 0]}>
              {data.daily.map((d, i) => (
                <Cell key={i} fill={d.net >= 0 ? "#10b981" : "#f43f5e"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Category breakdown */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="glass p-5">
          <h3 className="mb-4 text-xs font-bold uppercase tracking-wider text-zinc-400">
            Kategori Bazında Akış (Son Gün)
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={data.by_category.filter((c) => c.net_flow > 0)}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={90}
                paddingAngle={2}
                dataKey="net_flow"
                label={({ category, net_flow }) => `${category}: ${formatTL(net_flow)}`}
              >
                {data.by_category.filter((c) => c.net_flow > 0).map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) => formatTL(v)} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="glass overflow-hidden">
          <div className="border-b border-white/6 px-5 py-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400">
              Kategori Detayları
            </h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[0.7rem] uppercase tracking-wider text-zinc-500">
                <th className="px-5 py-2.5">Kategori</th>
                <th className="px-3 py-2.5 text-right">Net Akış</th>
              </tr>
            </thead>
            <tbody>
              {data.by_category.map((c) => (
                <tr key={c.category} className="border-t border-white/3">
                  <td className="px-5 py-2.5 text-xs text-zinc-300">{c.category}</td>
                  <td className={`px-3 py-2.5 text-right text-xs font-bold ${c.net_flow >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {formatTL(c.net_flow)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
