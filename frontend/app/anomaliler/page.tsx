"use client";

import { useAnomalies } from "@/lib/api";
import Skeleton from "@/components/ui/Skeleton";
import StatCard from "@/components/ui/StatCard";
import Link from "next/link";
import { AlertTriangle, Zap, Activity } from "lucide-react";

export default function AnomalilerPage() {
  const { data, isLoading } = useAnomalies(100);

  if (isLoading || !data) {
    return <div className="mx-auto max-w-[1600px] p-6"><Skeleton count={8} /></div>;
  }

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-6">
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-6 w-6 text-amber-400" />
        <h1 className="text-xl font-extrabold tracking-tight">Anomali Tespiti</h1>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Toplam Alarm" value={String(data.stats.total)} color="orange" icon={<AlertTriangle className="h-4 w-4" />} />
        <StatCard label="Ort. Z-Score" value={data.stats.avg_zscore.toFixed(2)} color="blue" icon={<Activity className="h-4 w-4" />} />
        <StatCard label="Max Z-Score" value={data.stats.max_zscore.toFixed(2)} color="red" icon={<Zap className="h-4 w-4" />} />
      </div>

      <div className="glass overflow-hidden">
        <div className="border-b border-white/6 px-5 py-4">
          <h2 className="text-sm font-bold">Anomali Logu</h2>
        </div>
        {data.alerts.length === 0 ? (
          <p className="p-6 text-sm text-zinc-500">Henüz anomali kaydı bulunmuyor.</p>
        ) : (
          <div className="max-h-[600px] space-y-2 overflow-y-auto p-4">
            {data.alerts.map((a, i) => (
              <div key={i} className="rounded-xl border border-white/4 bg-white/2 p-4 transition-colors hover:border-white/8">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Link href={`/fon/${a.code}`} className="rounded-md bg-blue-500/10 px-2 py-1 font-mono text-xs font-bold text-blue-400 hover:bg-blue-500/20">
                      {a.code}
                    </Link>
                    <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-[0.65rem] font-bold text-amber-400">{a.alert_type}</span>
                    {a.z_score && (
                      <span className="text-[0.65rem] text-zinc-500">Z: {a.z_score.toFixed(2)}</span>
                    )}
                  </div>
                  <span className="text-[0.65rem] text-zinc-500">{a.date}</span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-zinc-400">{a.message}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
