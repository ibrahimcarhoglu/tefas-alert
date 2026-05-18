"use client";

import { useFunds, useManagers } from "@/lib/api";
import { formatTL, formatNumber, formatPct, pctColor, riskColor, riskLabel } from "@/lib/formatters";
import Skeleton from "@/components/ui/Skeleton";
import Badge from "@/components/ui/Badge";
import Link from "next/link";
import { Search, Download, ChevronUp, ChevronDown, Filter, SlidersHorizontal, RotateCcw, Star, MessageCircle } from "lucide-react";
import { useState, useMemo } from "react";
import { useWatchlist } from "@/lib/watchlist";
import { useSocial } from "@/lib/api";

const CATEGORIES = [
  "Tümü", "Hisse Senedi", "Katılım", "Serbest", "Değişken",
  "Para Piyasası", "Borçlanma Araçları", "Kıymetli Madenler", "Fon Sepeti", "Diğer",
];

const RISK_LEVELS = [
  { value: "", label: "Tüm Riskler" },
  { value: "low", label: "Düşük (1-2)" },
  { value: "mid", label: "Orta (3-4)" },
  { value: "high", label: "Yüksek (5-7)" },
];

const RETURN_PERIODS = [
  { value: "1d", label: "1 Gün" },
  { value: "1w", label: "1 Hafta" },
  { value: "1m", label: "1 Ay" },
  { value: "3m", label: "3 Ay" },
  { value: "1y", label: "1 Yıl" },
];

const RETURN_PERIOD_LABELS: Record<string, string> = {
  "1d": "Günlük",
  "1w": "1H",
  "1m": "1A",
  "3m": "3A",
  "1y": "1Y",
};

export default function FonlarPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("Tümü");
  const [risk, setRisk] = useState("");
  const [manager, setManager] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [returnPeriod, setReturnPeriod] = useState("1d");
  const [maxFee, setMaxFee] = useState("");
  const [sortBy, setSortBy] = useState("net_flow");
  const [order, setOrder] = useState("desc");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const { watchlist, isFavorite, toggleFavorite } = useWatchlist();
  const { data: watchlistSocial } = useSocial(
    showFavoritesOnly && watchlist.length > 0 ? watchlist : undefined
  );
  const { data: managersList } = useManagers();

  const params = useMemo(() => {
    const codesParam = showFavoritesOnly
      ? (watchlist.length > 0 ? watchlist.join(",") : "NONE")
      : undefined;

    return {
      search,
      category: category === "Tümü" ? "" : category,
      risk,
      manager,
      codes: codesParam,
      return_period: returnPeriod,
      ...(maxFee ? { max_fee: maxFee } : {}),
      sort_by: sortBy === "pct_change" && returnPeriod !== "1d" ? "period_return" : sortBy,
      order,
      page,
      page_size: pageSize,
    };
  }, [search, category, risk, manager, showFavoritesOnly, watchlist, returnPeriod, maxFee, sortBy, order, page]);

  const { data, isLoading } = useFunds(params);

  const toggleSort = (col: string) => {
    if (sortBy === col) {
      setOrder(order === "desc" ? "asc" : "desc");
    } else {
      setSortBy(col);
      setOrder("desc");
    }
    setPage(1);
  };

  const SortIcon = ({ col }: { col: string }) => {
    if (sortBy !== col) return null;
    return order === "desc" ? (
      <ChevronDown className="inline h-3.5 w-3.5 text-blue-400" />
    ) : (
      <ChevronUp className="inline h-3.5 w-3.5 text-blue-400" />
    );
  };

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  const handleExportCSV = () => {
    if (!data) return;
    const retLabel = RETURN_PERIOD_LABELS[returnPeriod] || "Getiri";
    const headers = ["Kod", "İsim", "Fiyat", `${retLabel} %`, "Yönetim Ücreti %", "Net Akış", "Yatırımcı", "AUM", "Kategori", "Risk"];
    const rows = data.funds.map((f) => [
      f.code,
      f.name,
      f.price,
      returnPeriod === "1d" ? f.pct_change : f.period_return,
      f.management_fee ?? "",
      f.net_flow,
      f.num_investors,
      f.market_cap,
      f.category,
      f.risk,
    ]);
    const csv = "\uFEFF" + [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tefas_fonlar_${data.last_date}.csv`;
    // Excel uyumlu UTF-8 BOM ile dışa aktarım
    a.click();
  };

  const resetFilters = () => {
    setSearch("");
    setCategory("Tümü");
    setRisk("");
    setManager("");
    setReturnPeriod("1d");
    setMaxFee("");
    setPage(1);
  };

  const displayReturn = (f: { pct_change: number | null; period_return?: number | null }) =>
    returnPeriod === "1d" ? f.pct_change : f.period_return;

  return (
    <div className="mx-auto max-w-[1600px] space-y-5 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-extrabold tracking-tight">Fon Tarayıcı</h1>
          <p className="mt-1 text-sm text-zinc-400">
            {data ? `${data.total} fon listeleniyor · ${data.last_date}` : "Yükleniyor..."}
          </p>
        </div>
        <button
          onClick={handleExportCSV}
          className="flex items-center gap-1.5 rounded-lg bg-white/5 px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:bg-white/10"
        >
          <Download className="h-4 w-4" />
          Excel (CSV) İndir
        </button>
      </div>

      {/* Watchlist social news */}
      {showFavoritesOnly && watchlist.length > 0 && (
        <div className="glass p-5 space-y-3">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <MessageCircle className="h-4 w-4 text-blue-400" />
            İzleme Listesi — Sosyal Haberler
          </h2>
          {watchlistSocial?.trends && watchlistSocial.trends.length > 0 ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {watchlistSocial.trends.map((t) => (
                <Link
                  key={t.code}
                  href={`/fon/${t.code}`}
                  className="rounded-xl border border-white/6 bg-white/2 p-4 hover:border-blue-500/30 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-xs font-bold text-blue-400">{t.code}</span>
                    <span className="text-[10px] text-amber-400 font-bold">Skor {t.score}</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 line-clamp-2">{t.reason}</p>
                  {t.fund_pct_change != null && (
                    <p className={`text-xs font-bold mt-2 ${pctColor(t.fund_pct_change)}`}>
                      {formatPct(t.fund_pct_change)}
                    </p>
                  )}
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-500 italic">
              İzleme listenizdeki fonlar için bugün sosyal trend kaydı yok.
            </p>
          )}
        </div>
      )}

      {/* Filters Bar */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search Box */}
          <div className="relative flex-1 min-w-[280px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="Fon ara (kod veya isim)..."
              className="w-full rounded-xl border border-white/8 bg-white/3 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 outline-none transition-all focus:border-blue-500 focus:shadow-[0_0_15px_rgba(59,130,246,0.2)]"
            />
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setShowFavoritesOnly(!showFavoritesOnly);
                setPage(1);
              }}
              className={`flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all border cursor-pointer ${
                showFavoritesOnly
                  ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
                  : "bg-white/5 border-white/8 text-zinc-300 hover:bg-white/10"
              }`}
            >
              <Star className={`h-4 w-4 ${showFavoritesOnly ? "fill-amber-400 text-amber-400" : ""}`} />
              İzleme Listem
            </button>

            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all border cursor-pointer ${
                showFilters || risk || manager
                  ? "bg-blue-500/10 border-blue-500/30 text-blue-400"
                  : "bg-white/5 border-white/8 text-zinc-300 hover:bg-white/10"
              }`}
            >
              <SlidersHorizontal className="h-4 w-4" />
              Gelişmiş Filtreler {(risk || manager) && "•"}
            </button>

            {(search || category !== "Tümü" || risk || manager || showFavoritesOnly) && (
              <button
                onClick={() => {
                  resetFilters();
                  setShowFavoritesOnly(false);
                }}
                className="flex items-center gap-1.5 rounded-xl border border-white/8 bg-white/5 px-4 py-2.5 text-sm font-semibold text-zinc-400 transition-all hover:bg-white/10 hover:text-white cursor-pointer"
                title="Filtreleri Sıfırla"
              >
                <RotateCcw className="h-4 w-4" />
                Sıfırla
              </button>
            )}
          </div>
        </div>

        {/* Categories Tab Bar */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-1 scrollbar-none">
          <Filter className="h-4 w-4 text-zinc-500 shrink-0" />
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => { setCategory(cat); setPage(1); }}
              className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                category === cat
                  ? "bg-blue-500 text-white shadow-md shadow-blue-500/25"
                  : "bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-white"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Collapsible Advanced Filters Panel */}
        {showFilters && (
          <div className="glass p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 animate-count">
            {/* Return period */}
            <div className="space-y-2">
              <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Getiri Dönemi</label>
              <div className="flex flex-wrap gap-2">
                {RETURN_PERIODS.map((rp) => (
                  <button
                    key={rp.value}
                    onClick={() => { setReturnPeriod(rp.value); setPage(1); }}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                      returnPeriod === rp.value
                        ? "bg-blue-500/20 text-blue-400 border border-blue-500/40"
                        : "bg-white/5 text-zinc-400 border border-white/4 hover:bg-white/10"
                    }`}
                  >
                    {rp.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Max management fee */}
            <div className="space-y-2">
              <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">
                Maks. Yönetim Ücreti (%)
              </label>
              <input
                type="number"
                step="0.1"
                min="0"
                value={maxFee}
                onChange={(e) => { setMaxFee(e.target.value); setPage(1); }}
                placeholder="örn: 2.0 (tahmini)"
                className="w-full rounded-xl border border-white/8 bg-[#0b1020] px-3 py-2 text-xs text-white outline-none focus:border-blue-500"
              />
              <p className="text-[10px] text-zinc-500">Resmi ücret verisi yoksa kategori tahmini kullanılır.</p>
            </div>

            {/* Risk Selection */}
            <div className="space-y-2">
              <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Risk Seviyesi</label>
              <div className="flex flex-wrap gap-2">
                {RISK_LEVELS.map((rl) => (
                  <button
                    key={rl.value}
                    onClick={() => { setRisk(rl.value); setPage(1); }}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                      risk === rl.value
                        ? "bg-blue-500/20 text-blue-400 border border-blue-500/40 shadow-inner"
                        : "bg-white/5 text-zinc-400 border border-white/4 hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    {rl.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Asset Manager Dropdown */}
            <div className="space-y-2">
              <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Portföy Yöneticisi</label>
              <select
                value={manager}
                onChange={(e) => { setManager(e.target.value); setPage(1); }}
                className="w-full rounded-xl border border-white/8 bg-[#0b1020] px-3 py-2 text-xs text-white outline-none focus:border-blue-500 focus:shadow-[0_0_15px_rgba(59,130,246,0.15)]"
              >
                <option value="">Tüm Yöneticiler</option>
                {managersList?.map((m) => (
                  <option key={m.manager} value={m.manager}>
                    {m.manager}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="glass overflow-hidden">
        {isLoading ? (
          <Skeleton count={10} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#0a1020]">
                  <tr className="text-left text-[0.7rem] uppercase tracking-wider text-zinc-500">
                    <th className="w-10 px-3 py-3"></th>
                    <th className="px-5 py-3">Kod</th>
                    <th className="px-3 py-3">İsim</th>
                    <th className="cursor-pointer px-3 py-3 text-right" onClick={() => toggleSort("price")}>
                      Fiyat <SortIcon col="price" />
                    </th>
                    <th
                      className="cursor-pointer px-3 py-3 text-right"
                      onClick={() => toggleSort(returnPeriod === "1d" ? "pct_change" : "period_return")}
                    >
                      {RETURN_PERIOD_LABELS[returnPeriod] || "Getiri"}{" "}
                      <SortIcon col={returnPeriod === "1d" ? "pct_change" : "period_return"} />
                    </th>
                    <th className="px-3 py-3 text-right text-[0.65rem]">Ücret %</th>
                    <th className="cursor-pointer px-3 py-3 text-right" onClick={() => toggleSort("net_flow")}>
                      Net Akış <SortIcon col="net_flow" />
                    </th>
                    <th className="cursor-pointer px-3 py-3 text-right" onClick={() => toggleSort("num_investors")}>
                      Yatırımcı <SortIcon col="num_investors" />
                    </th>
                    <th className="cursor-pointer px-3 py-3 text-right" onClick={() => toggleSort("market_cap")}>
                      AUM <SortIcon col="market_cap" />
                    </th>
                    <th className="px-3 py-3 text-center">Kategori</th>
                    <th className="px-3 py-3 text-center">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.funds.map((f) => (
                    <tr key={f.code} className="border-t border-white/3 transition-colors hover:bg-white/3">
                      <td className="px-3 py-3">
                        <button
                          onClick={() => toggleFavorite(f.code)}
                          className="text-zinc-500 hover:text-amber-400 transition-colors cursor-pointer"
                        >
                          <Star
                            className={`h-4 w-4 ${
                              isFavorite(f.code) ? "fill-amber-400 text-amber-400" : "text-zinc-500"
                            }`}
                          />
                        </button>
                      </td>
                      <td className="px-5 py-3">
                        <Link
                          href={`/fon/${f.code}`}
                          className="rounded-md bg-blue-500/10 px-2 py-1 font-mono text-xs font-bold text-blue-400 transition-colors hover:bg-blue-500/20"
                        >
                          {f.code}
                        </Link>
                      </td>
                      <td className="max-w-[220px] truncate px-3 py-3 text-xs text-zinc-300">{f.name}</td>
                      <td className="px-3 py-3 text-right text-xs tabular-nums">{f.price?.toFixed(4)}</td>
                      <td className={`px-3 py-3 text-right text-xs font-bold tabular-nums ${pctColor(displayReturn(f))}`}>
                        {formatPct(displayReturn(f))}
                      </td>
                      <td className="px-3 py-3 text-right text-xs tabular-nums text-zinc-400">
                        {f.management_fee != null ? `%${f.management_fee.toFixed(2)}` : "veri yok"}
                      </td>
                      <td className={`px-3 py-3 text-right text-xs font-semibold tabular-nums ${f.net_flow && f.net_flow > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {formatTL(f.net_flow)}
                      </td>
                      <td className="px-3 py-3 text-right text-xs tabular-nums text-zinc-300">{formatNumber(f.num_investors)}</td>
                      <td className="px-3 py-3 text-right text-xs tabular-nums text-zinc-400">{formatTL(f.market_cap)}</td>
                      <td className="px-3 py-3 text-center">
                        <span className="rounded-md bg-white/5 px-2 py-0.5 text-[0.65rem] text-zinc-400">{f.category}</span>
                      </td>
                      <td className="px-3 py-3 text-center">
                        <Badge className={riskColor(f.risk)}>{riskLabel(f.risk)}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-white/6 px-5 py-3">
                <span className="text-xs text-zinc-500">
                  Sayfa {page} / {totalPages} · Toplam {data?.total} fon
                </span>
                <div className="flex gap-1.5">
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage(page - 1)}
                    className="rounded-lg bg-white/5 px-3 py-1.5 text-xs font-medium text-zinc-400 transition-colors hover:bg-white/10 disabled:opacity-30"
                  >
                    ← Önceki
                  </button>
                  <button
                    disabled={page >= totalPages}
                    onClick={() => setPage(page + 1)}
                    className="rounded-lg bg-white/5 px-3 py-1.5 text-xs font-medium text-zinc-400 transition-colors hover:bg-white/10 disabled:opacity-30"
                  >
                    Sonraki →
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
