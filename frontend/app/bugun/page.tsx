"use client";

import { useDashboard } from "@/lib/api";
import { formatTL, formatNumber, formatPct, pctColor } from "@/lib/formatters";
import StatCard from "@/components/ui/StatCard";
import Skeleton from "@/components/ui/Skeleton";
import Link from "next/link";
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Users,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { useState } from "react";

const PERIOD_LABELS: Record<string, string> = {
  "3gun": "3 Gün",
  "1hafta": "1 Hafta",
  "2hafta": "2 Hafta",
  "1ay": "1 Ay",
};

export default function BugunPage() {
  const { data, isLoading } = useDashboard();
  const [period, setPeriod] = useState("1hafta");

  if (isLoading || !data) {
    return (
      <div className="mx-auto max-w-[1600px] p-6">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="glass p-5">
              <Skeleton count={2} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-6">
      {/* Date header */}
      <div className="flex items-center gap-3">
        <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500 live-dot" />
        <span className="text-sm text-zinc-400">
          Son güncelleme: <span className="font-semibold text-white">{data.last_date}</span>
        </span>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Toplam Fon"
          value={formatNumber(data.total_funds)}
          sub="Aktif işlem gören"
          icon={<BarChart3 className="h-5 w-5" />}
          color="blue"
        />
        <StatCard
          label="Toplam Giriş"
          value={formatTL(data.total_inflow)}
          sub="Bugünkü net giriş"
          icon={<TrendingUp className="h-5 w-5" />}
          color="green"
        />
        <StatCard
          label="Toplam Çıkış"
          value={formatTL(data.total_outflow)}
          sub="Bugünkü net çıkış"
          icon={<TrendingDown className="h-5 w-5" />}
          color="red"
        />
        <StatCard
          label="Net Akış"
          value={formatTL(data.total_inflow + data.total_outflow)}
          sub="Giriş − Çıkış"
          icon={<Users className="h-5 w-5" />}
          color={data.total_inflow + data.total_outflow >= 0 ? "green" : "red"}
        />
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: Top Returns + Top Losers */}
        <div className="space-y-6 lg:col-span-2">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {/* Top Returns */}
            <div className="glass overflow-hidden">
              <div className="flex items-center gap-2 border-b border-white/6 px-5 py-4">
                <ArrowUpRight className="h-4 w-4 text-emerald-400" />
                <h2 className="text-sm font-bold">En Çok Yükselen</h2>
                <span className="ml-auto rounded-md bg-white/5 px-2 py-0.5 text-[0.7rem] text-zinc-400">
                  {data.top_returns.length}
                </span>
              </div>
              <div className="max-h-[420px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[0.7rem] uppercase tracking-wider text-zinc-500">
                      <th className="px-5 py-2.5">Kod</th>
                      <th className="px-3 py-2.5">İsim</th>
                      <th className="px-3 py-2.5 text-right">Değişim</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_returns.slice(0, 10).map((f) => (
                      <tr
                        key={f.code}
                        className="border-t border-white/3 transition-colors hover:bg-white/3"
                      >
                        <td className="px-5 py-2.5">
                          <Link
                            href={`/fon/${f.code}`}
                            className="rounded-md bg-blue-500/10 px-2 py-1 font-mono text-xs font-bold text-blue-400 transition-colors hover:bg-blue-500/20"
                          >
                            {f.code}
                          </Link>
                        </td>
                        <td className="max-w-[180px] truncate px-3 py-2.5 text-xs text-zinc-300">
                          {f.name}
                        </td>
                        <td className={`px-3 py-2.5 text-right text-xs font-bold ${pctColor(f.pct_change)}`}>
                          {formatPct(f.pct_change)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Top Losers */}
            <div className="glass overflow-hidden">
              <div className="flex items-center gap-2 border-b border-white/6 px-5 py-4">
                <ArrowDownRight className="h-4 w-4 text-rose-400" />
                <h2 className="text-sm font-bold">En Çok Düşen</h2>
              </div>
              <div className="max-h-[420px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[0.7rem] uppercase tracking-wider text-zinc-500">
                      <th className="px-5 py-2.5">Kod</th>
                      <th className="px-3 py-2.5">İsim</th>
                      <th className="px-3 py-2.5 text-right">Değişim</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_losers.slice(0, 10).map((f) => (
                      <tr
                        key={f.code}
                        className="border-t border-white/3 transition-colors hover:bg-white/3"
                      >
                        <td className="px-5 py-2.5">
                          <Link
                            href={`/fon/${f.code}`}
                            className="rounded-md bg-blue-500/10 px-2 py-1 font-mono text-xs font-bold text-blue-400 transition-colors hover:bg-blue-500/20"
                          >
                            {f.code}
                          </Link>
                        </td>
                        <td className="max-w-[180px] truncate px-3 py-2.5 text-xs text-zinc-300">
                          {f.name}
                        </td>
                        <td className={`px-3 py-2.5 text-right text-xs font-bold ${pctColor(f.pct_change)}`}>
                          {formatPct(f.pct_change)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Top Inflows / Outflows */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div className="glass overflow-hidden">
              <div className="flex items-center gap-2 border-b border-white/6 px-5 py-4">
                <TrendingUp className="h-4 w-4 text-emerald-400" />
                <h2 className="text-sm font-bold">En Çok Para Girişi</h2>
              </div>
              <div className="max-h-[380px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[0.7rem] uppercase tracking-wider text-zinc-500">
                      <th className="px-5 py-2.5">Kod</th>
                      <th className="px-3 py-2.5 text-right">Net Akış</th>
                      <th className="px-3 py-2.5 text-right">Değişim</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_inflows.slice(0, 10).map((f) => (
                      <tr key={f.code} className="border-t border-white/3 transition-colors hover:bg-white/3">
                        <td className="px-5 py-2.5">
                          <Link href={`/fon/${f.code}`} className="rounded-md bg-blue-500/10 px-2 py-1 font-mono text-xs font-bold text-blue-400 hover:bg-blue-500/20">
                            {f.code}
                          </Link>
                        </td>
                        <td className="px-3 py-2.5 text-right text-xs font-semibold text-emerald-400">{formatTL(f.net_flow)}</td>
                        <td className={`px-3 py-2.5 text-right text-xs font-bold ${pctColor(f.pct_change)}`}>{formatPct(f.pct_change)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="glass overflow-hidden">
              <div className="flex items-center gap-2 border-b border-white/6 px-5 py-4">
                <TrendingDown className="h-4 w-4 text-rose-400" />
                <h2 className="text-sm font-bold">En Çok Para Çıkışı</h2>
              </div>
              <div className="max-h-[380px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[0.7rem] uppercase tracking-wider text-zinc-500">
                      <th className="px-5 py-2.5">Kod</th>
                      <th className="px-3 py-2.5 text-right">Net Akış</th>
                      <th className="px-3 py-2.5 text-right">Değişim</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_outflows.slice(0, 10).map((f) => (
                      <tr key={f.code} className="border-t border-white/3 transition-colors hover:bg-white/3">
                        <td className="px-5 py-2.5">
                          <Link href={`/fon/${f.code}`} className="rounded-md bg-blue-500/10 px-2 py-1 font-mono text-xs font-bold text-blue-400 hover:bg-blue-500/20">
                            {f.code}
                          </Link>
                        </td>
                        <td className="px-3 py-2.5 text-right text-xs font-semibold text-rose-400">{formatTL(f.net_flow)}</td>
                        <td className={`px-3 py-2.5 text-right text-xs font-bold ${pctColor(f.pct_change)}`}>{formatPct(f.pct_change)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Periodic Performance */}
          <div className="glass overflow-hidden">
            <div className="flex items-center gap-2 border-b border-white/6 px-5 py-4">
              <BarChart3 className="h-4 w-4 text-blue-400" />
              <h2 className="text-sm font-bold">Periyodik Performans</h2>
              <div className="ml-auto flex gap-1.5">
                {Object.entries(PERIOD_LABELS).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setPeriod(key)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                      period === key
                        ? "bg-blue-500 text-white shadow-md shadow-blue-500/25"
                        : "bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="max-h-[400px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[0.7rem] uppercase tracking-wider text-zinc-500">
                    <th className="px-5 py-2.5">#</th>
                    <th className="px-3 py-2.5">Kod</th>
                    <th className="px-3 py-2.5">İsim</th>
                    <th className="px-3 py-2.5 text-right">Fiyat</th>
                    <th className="px-3 py-2.5 text-right">Değişim</th>
                    <th className="px-3 py-2.5 text-right">AUM</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.periodic[period] || []).map((f, i) => (
                    <tr key={f.code} className="border-t border-white/3 hover:bg-white/3">
                      <td className="px-5 py-2.5 text-xs text-zinc-500">{i + 1}</td>
                      <td className="px-3 py-2.5">
                        <Link href={`/fon/${f.code}`} className="rounded-md bg-blue-500/10 px-2 py-1 font-mono text-xs font-bold text-blue-400 hover:bg-blue-500/20">
                          {f.code}
                        </Link>
                      </td>
                      <td className="max-w-[200px] truncate px-3 py-2.5 text-xs text-zinc-300">{f.name}</td>
                      <td className="px-3 py-2.5 text-right text-xs">{f.price?.toFixed(4)}</td>
                      <td className={`px-3 py-2.5 text-right text-xs font-bold ${pctColor(f.pct_change)}`}>{formatPct(f.pct_change)}</td>
                      <td className="px-3 py-2.5 text-right text-xs text-zinc-400">{formatTL(f.market_cap)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right sidebar: Alerts + Social */}
        <div className="space-y-6">
          {/* Recent Alerts */}
          <div className="glass overflow-hidden">
            <div className="flex items-center gap-2 border-b border-white/6 px-5 py-4">
              <span className="text-lg">🚨</span>
              <h2 className="text-sm font-bold">Son Anomaliler</h2>
              <Link
                href="/anomaliler"
                className="ml-auto text-xs text-blue-400 hover:underline"
              >
                Tümünü gör →
              </Link>
            </div>
            <div className="max-h-[350px] space-y-2 overflow-y-auto p-4">
              {data.recent_alerts.length === 0 ? (
                <p className="text-xs text-zinc-500">Henüz anomali yok</p>
              ) : (
                data.recent_alerts.slice(0, 8).map((a, i) => (
                  <div
                    key={i}
                    className="rounded-xl border border-white/4 bg-white/2 p-3 transition-colors hover:border-white/8"
                  >
                    <div className="flex items-center justify-between">
                      <Link
                        href={`/fon/${a.code}`}
                        className="font-mono text-xs font-bold text-blue-400"
                      >
                        {a.code}
                      </Link>
                      <span className="text-[0.65rem] text-zinc-500">{a.date}</span>
                    </div>
                    <p className="mt-1 text-[0.72rem] leading-relaxed text-zinc-400">
                      {a.message}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Social Trends */}
          <div className="glass overflow-hidden">
            <div className="flex items-center gap-2 border-b border-white/6 px-5 py-4">
              <span className="text-lg">🐦</span>
              <h2 className="text-sm font-bold">Sosyal Trendler</h2>
              <Link
                href="/sosyal"
                className="ml-auto text-xs text-blue-400 hover:underline"
              >
                Tümünü gör →
              </Link>
            </div>
            <div className="max-h-[350px] space-y-2 overflow-y-auto p-4">
              {data.social_trends.length === 0 ? (
                <p className="text-xs text-zinc-500">Trend bulunamadı</p>
              ) : (
                data.social_trends.slice(0, 6).map((t, i) => (
                  <div
                    key={i}
                    className="rounded-xl border border-white/4 bg-white/2 p-3 transition-colors hover:border-white/8"
                  >
                    <div className="flex items-center justify-between">
                      <Link
                        href={`/fon/${t.code}`}
                        className="font-mono text-xs font-bold text-blue-400"
                      >
                        {t.code}
                      </Link>
                      <span className="rounded-md bg-amber-500/15 px-1.5 py-0.5 text-[0.65rem] font-bold text-amber-400">
                        Skor: {t.score}
                      </span>
                    </div>
                    <p className="mt-1 text-[0.72rem] leading-relaxed text-zinc-400">
                      {t.reason}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
