"use client";

import { useSocial } from "@/lib/api";
import Skeleton from "@/components/ui/Skeleton";
import { formatTL, formatPct, pctColor } from "@/lib/formatters";
import Link from "next/link";
import { MessageCircle } from "lucide-react";

export default function SosyalPage() {
  const { data, isLoading } = useSocial();

  if (isLoading || !data) {
    return <div className="mx-auto max-w-[1600px] p-6"><Skeleton count={6} /></div>;
  }

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-6">
      <div className="flex items-center gap-3">
        <MessageCircle className="h-6 w-6 text-blue-400" />
        <div>
          <h1 className="text-xl font-extrabold tracking-tight">Sosyal Trendler</h1>
          <p className="text-sm text-zinc-400">Fintwit'ten yapay zeka ile tespit edilen trendler · {data.date}</p>
        </div>
      </div>

      {data.trends.length === 0 ? (
        <div className="glass p-10 text-center text-sm text-zinc-500">
          Henüz sosyal trend bulunamadı.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.trends.map((t) => (
            <div key={t.code} className="glass overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:shadow-lg">
              <div className="flex items-center justify-between border-b border-white/6 px-5 py-4">
                <Link
                  href={`/fon/${t.code}`}
                  className="rounded-md bg-blue-500/10 px-3 py-1.5 font-mono text-sm font-bold text-blue-400 transition-colors hover:bg-blue-500/20"
                >
                  {t.code}
                </Link>
                <span className="rounded-xl bg-gradient-to-r from-amber-500/20 to-orange-500/20 px-3 py-1 text-xs font-extrabold text-amber-400">
                  Skor: {t.score}
                </span>
              </div>
              <div className="space-y-3 p-5">
                <p className="text-xs font-medium text-zinc-300">{t.name}</p>
                <p className="text-xs leading-relaxed text-zinc-400">{t.reason}</p>
                <div className="flex items-center gap-4 text-[0.7rem] text-zinc-500">
                  <span>Sinyal: <span className="font-bold text-zinc-300">{t.stat}</span></span>
                  {t.fund_pct_change != null && (
                    <span>
                      Fiyat:{" "}
                      <span className={`font-bold ${pctColor(t.fund_pct_change)}`}>
                        {formatPct(t.fund_pct_change)}
                      </span>
                    </span>
                  )}
                  {t.fund_net_flow != null && (
                    <span>Akış: <span className="font-bold">{formatTL(t.fund_net_flow)}</span></span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
