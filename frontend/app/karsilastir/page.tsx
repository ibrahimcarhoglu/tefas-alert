"use client";

import { useFunds, useFundDetail } from "@/lib/api";
import { formatTL, formatNumber, formatPct, formatPrice, riskColor, riskLabel, pctColor } from "@/lib/formatters";
import Skeleton from "@/components/ui/Skeleton";
import Badge from "@/components/ui/Badge";
import Link from "next/link";
import GlossaryTooltip from "@/components/ui/GlossaryTooltip";
import { Search, X, Plus, Star, ArrowLeft, ArrowRightLeft, Shield, BarChart3, Users, Landmark, Percent } from "lucide-react";
import { useState, useMemo, useEffect } from "react";
import { useWatchlist } from "@/lib/watchlist";

// Custom hook to fetch details for multiple funds
function useMultipleFundsDetails(codes: string[]) {
  const [details, setDetails] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (codes.length === 0) {
      setDetails([]);
      return;
    }

    const fetchAll = async () => {
      setIsLoading(true);
      try {
        const promises = codes.map(async (code) => {
          const res = await fetch(`/api/fund/${code}`);
          if (!res.ok) throw new Error();
          return res.json();
        });
        const results = await Promise.all(promises);
        setDetails(results);
      } catch (err) {
        console.error("Fon detayları alınamadı", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAll();
  }, [codes]);

  return { details, isLoading };
}

export default function KarsilastirPage() {
  const { watchlist } = useWatchlist();
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);

  // Search funds for autocomplete
  const { data: searchResults, isLoading: isSearchLoading } = useFunds({
    search: searchQuery,
    page_size: 5,
  });

  const { details, isLoading: isDetailsLoading } = useMultipleFundsDetails(selectedCodes);

  const addFund = (code: string) => {
    const upper = code.toUpperCase();
    if (selectedCodes.length >= 4) {
      alert("En fazla 4 fon karşılaştırabilirsiniz.");
      return;
    }
    if (selectedCodes.includes(upper)) return;
    setSelectedCodes([...selectedCodes, upper]);
    setSearchQuery("");
    setShowDropdown(false);
  };

  const removeFund = (code: string) => {
    setSelectedCodes(selectedCodes.filter((c) => c !== code));
  };

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/fonlar"
          className="rounded-lg bg-white/5 p-2 text-zinc-400 transition-colors hover:bg-white/10 hover:text-white"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-extrabold tracking-tight flex items-center gap-2">
            <ArrowRightLeft className="h-5 w-5 text-blue-500" />
            Fon Karşılaştırma
          </h1>
          <p className="text-sm text-zinc-400">
            En fazla 4 fonu yan yana detaylı metrikleriyle karşılaştırın.
          </p>
        </div>
      </div>

      {/* Control Panel */}
      <div className="glass p-5 grid grid-cols-1 md:grid-cols-2 gap-6 items-end">
        {/* Autocomplete Search Bar */}
        <div className="space-y-2 relative">
          <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Fon Ekle</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setShowDropdown(true);
              }}
              onFocus={() => setShowDropdown(true)}
              placeholder="Karşılaştırmak için fon arayın..."
              className="w-full rounded-xl border border-white/8 bg-white/3 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 outline-none transition-all focus:border-blue-500 focus:shadow-[0_0_15px_rgba(59,130,246,0.2)]"
            />
          </div>

          {/* Autocomplete Dropdown */}
          {showDropdown && searchQuery.trim().length > 0 && (
            <div className="absolute left-0 right-0 top-full mt-2 z-50 rounded-xl border border-white/10 bg-[#0d1426] p-2 shadow-2xl backdrop-blur-xl max-h-[300px] overflow-y-auto">
              {isSearchLoading ? (
                <div className="p-3 text-xs text-zinc-400 animate-pulse">Aranıyor...</div>
              ) : searchResults?.funds && searchResults.funds.length > 0 ? (
                searchResults.funds.map((f) => (
                  <button
                    key={f.code}
                    onClick={() => addFund(f.code)}
                    className="flex w-full items-center justify-between rounded-lg p-2.5 text-left text-xs transition-colors hover:bg-white/5 cursor-pointer"
                  >
                    <div>
                      <span className="font-mono font-bold text-blue-400 mr-2">{f.code}</span>
                      <span className="text-zinc-300 font-medium">{f.name}</span>
                    </div>
                    <Badge className={riskColor(f.risk)}>{riskLabel(f.risk)}</Badge>
                  </button>
                ))
              ) : (
                <div className="p-3 text-xs text-zinc-500">Fon bulunamadı.</div>
              )}
            </div>
          )}
        </div>

        {/* Watchlist Quick Import */}
        <div className="space-y-2">
          <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">İzleme Listemden Ekle</label>
          <div className="flex flex-wrap gap-2">
            {watchlist.length > 0 ? (
              watchlist.map((code) => {
                const isAdded = selectedCodes.includes(code);
                return (
                  <button
                    key={code}
                    onClick={() => (isAdded ? removeFund(code) : addFund(code))}
                    disabled={selectedCodes.length >= 4 && !isAdded}
                    className={`flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer border ${
                      isAdded
                        ? "bg-blue-500/10 border-blue-500/30 text-blue-400"
                        : "bg-white/5 border-white/8 text-zinc-400 hover:bg-white/10 hover:text-white disabled:opacity-30"
                    }`}
                  >
                    <Star className={`h-3 w-3 ${isAdded ? "fill-blue-400 text-blue-400" : ""}`} />
                    {code}
                  </button>
                );
              })
            ) : (
              <span className="text-xs text-zinc-500 italic flex items-center gap-1.5 py-1.5">
                <Star className="h-3 w-3" />
                İzleme listenizde fon bulunmuyor.
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Selected Chips */}
      {selectedCodes.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-zinc-500 mr-1 font-medium">Seçili Fonlar:</span>
          {selectedCodes.map((code) => (
            <span
              key={code}
              className="flex items-center gap-1.5 rounded-lg bg-blue-500/10 border border-blue-500/30 px-3 py-1.5 text-xs font-bold text-blue-400"
            >
              {code}
              <button
                onClick={() => removeFund(code)}
                className="text-blue-400 hover:text-white transition-colors cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Comparison Matrix */}
      {selectedCodes.length === 0 ? (
        <div className="glass p-12 text-center space-y-4">
          <ArrowRightLeft className="h-12 w-12 text-zinc-500 mx-auto animate-pulse" />
          <h3 className="text-sm font-bold text-zinc-300">Karşılaştıracak Fon Seçilmedi</h3>
          <p className="text-xs text-zinc-500 max-w-md mx-auto leading-relaxed">
            Yukarıdaki arama çubuğunu kullanarak veya izleme listenizden fonlar seçerek yan yana karşılaştırmaya başlayabilirsiniz.
          </p>
        </div>
      ) : isDetailsLoading ? (
        <div className="glass p-12">
          <Skeleton count={5} />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div className="min-w-[900px] grid" style={{ gridTemplateColumns: `200px repeat(${selectedCodes.length}, 1fr)` }}>
            {/* Header Row */}
            <div className="bg-[#0b1020] border-b border-r border-white/6 p-4 flex items-center font-bold text-xs text-zinc-400 uppercase tracking-wider">
              Metrikler
            </div>
            {details.map((f) => (
              <div key={f.code} className="bg-[#0d1426] border-b border-r border-white/6 p-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="rounded-lg bg-blue-500/15 px-2.5 py-1 font-mono text-sm font-extrabold text-blue-400">
                      {f.code}
                    </span>
                    <button
                      onClick={() => removeFund(f.code)}
                      className="text-zinc-500 hover:text-white transition-colors cursor-pointer"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  <h3 className="text-xs font-bold text-white line-clamp-2 leading-relaxed">{f.name}</h3>
                </div>
              </div>
            ))}

            {/* Price Row */}
            <div className="border-b border-r border-white/4 p-4 flex items-center text-xs font-semibold text-zinc-400">
              <Landmark className="h-4 w-4 mr-2 text-blue-400" /> Fiyat
            </div>
            {details.map((f) => {
              const lastPrice = f.history && f.history[f.history.length - 1]?.price;
              return (
                <div key={f.code} className="border-b border-r border-white/4 p-4 text-xs font-mono font-bold text-zinc-300">
                  {formatPrice(lastPrice)}
                </div>
              );
            })}

            {/* 30-Day Return Row */}
            <div className="border-b border-r border-white/4 p-4 flex items-center text-xs font-semibold text-zinc-400">
              <Percent className="h-4 w-4 mr-2 text-emerald-400" />
              <GlossaryTooltip
                term="30 Günlük Getiri"
                definition="Seçilen fonların son 30 gün içinde elde ettiği toplam kümülatif getiri oranlarını yan yana kıyaslar."
              />
            </div>
            {details.map((f) => {
              const last = f.history && f.history[f.history.length - 1];
              const first = f.history && f.history[0];
              const periodReturn = last && first && first.price
                ? ((last.price! - first.price) / first.price * 100)
                : 0;

              return (
                <div key={f.code} className={`border-b border-r border-white/4 p-4 text-xs font-bold ${pctColor(periodReturn)}`}>
                  {formatPct(periodReturn)}
                </div>
              );
            })}

            {/* Category Row */}
            <div className="border-b border-r border-white/4 p-4 flex items-center text-xs font-semibold text-zinc-400">
              <BarChart3 className="h-4 w-4 mr-2 text-indigo-400" /> Kategori
            </div>
            {details.map((f) => (
              <div key={f.code} className="border-b border-r border-white/4 p-4 text-xs">
                <span className="rounded-md bg-white/5 px-2 py-0.5 font-medium text-zinc-300">{f.category}</span>
              </div>
            ))}

            {/* Risk Level Row */}
            <div className="border-b border-r border-white/4 p-4 flex items-center text-xs font-semibold text-zinc-400">
              <Shield className="h-4 w-4 mr-2 text-rose-400" />
              <GlossaryTooltip
                term="Risk Seviyesi"
                definition="1 ile 7 arasında puanlanan, fonun fiyat dalgalanma (volatilite) derecesini ve risk kategorisini gösteren resmi TEFAS derecesidir."
              />
            </div>
            {details.map((f) => (
              <div key={f.code} className="border-b border-r border-white/4 p-4 text-xs">
                <Badge className={riskColor(f.risk)}>{riskLabel(f.risk)}</Badge>
              </div>
            ))}

            {/* Portfolio Manager Row */}
            <div className="border-b border-r border-white/4 p-4 flex items-center text-xs font-semibold text-zinc-400">
              <Users className="h-4 w-4 mr-2 text-amber-400" /> Kurucu / Yönetici
            </div>
            {details.map((f) => (
              <div key={f.code} className="border-b border-r border-white/4 p-4 text-xs text-zinc-400 font-medium">
                {f.manager}
              </div>
            ))}

            {/* Asset Allocation Row */}
            <div className="border-b border-r border-white/4 p-4 flex items-center text-xs font-semibold text-zinc-400">
              Varlık Dağılımı
            </div>
            {details.map((f) => {
              const allocEntries = Object.entries(f.allocation || {}).filter(([, v]) => v > 0);
              return (
                <div key={f.code} className="border-b border-r border-white/4 p-4 text-xs space-y-2.5">
                  {allocEntries.length > 0 ? (
                    allocEntries.map(([name, val]) => (
                      <div key={name} className="space-y-1">
                        <div className="flex justify-between text-[10px] font-semibold text-zinc-400">
                          <span>{name}</span>
                          <span>{formatPct(val)}</span>
                        </div>
                        <div className="h-1 w-full rounded-full bg-white/5 overflow-hidden">
                          <div className="h-full bg-blue-500" style={{ width: `${val}%` }}></div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <span className="text-[10px] text-zinc-500 italic">Veri bulunamadı.</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
