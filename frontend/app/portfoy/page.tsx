"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import useSWR, { mutate } from "swr";
import {
  usePortfolioSummary,
  usePortfolioTransactions,
  usePortfolioAllocation,
  usePortfolioAlerts,
  usePortfolioNotifications,
  usePortfolioPerformance,
  createPortfolioAlert,
  deletePortfolioAlert,
  runInvestmentSimulation,
  useFunds,
  getAiFundInterpretation,
  getAiPortfolioReview,
  bulkImportTransactions,
} from "@/lib/api";
import {
  formatTL,
  formatNumber,
  formatPct,
  formatPrice,
  riskColor,
  riskLabel,
  riskSliceColor,
  pctColor,
} from "@/lib/formatters";
import Skeleton from "@/components/ui/Skeleton";
import Badge from "@/components/ui/Badge";
import Link from "next/link";
import GlossaryTerm from "@/components/ui/GlossaryTerm";
import {
  Plus,
  Trash2,
  Download,
  Upload,
  Calendar,
  PieChart as PieIcon,
  Briefcase,
  TrendingUp,
  TrendingDown,
  X,
  Search,
  Bell,
  CheckCircle,
  HelpCircle,
  BarChart3,
  Percent,
  Play,
  RotateCcw,
  Sparkles,
  Info,
  ChevronRight,
  Shield,
} from "lucide-react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";

const ALLOCATION_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#f43f5e", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"];

// Quiz Questions
const QUIZ_QUESTIONS = [
  {
    id: 1,
    question: "Yatırım yaparken birincil önceliğiniz hangisidir?",
    options: [
      { text: "Paramın değerini korumak ve minimum risk almak (Ana Para Koruması)", score: 1 },
      { text: "Makul oranda risk alarak enflasyon üzerinde dengeli büyüme sağlamak", score: 3 },
      { text: "Yüksek getiri elde etmek amacıyla yüksek volatiliteyi kabul etmek", score: 5 },
    ],
  },
  {
    id: 2,
    question: "Yatırım yaptığınız fonun kısa vadede %15 değer kaybetmesi durumunda ne yaparsınız?",
    options: [
      { text: "Kaygılanıp daha fazla zarar etmemek için hemen satarım", score: 1 },
      { text: "Fiyatın düzelmesini beklerim ve sabırlı olurum", score: 3 },
      { text: "Fırsat olarak görüp daha düşük fiyattan ek alım yaparım", score: 5 },
    ],
  },
  {
    id: 3,
    question: "Bu yatırımı hangi süre boyunca elinizde tutmayı planlıyorsunuz?",
    options: [
      { text: "Kısa Vadeli (< 6 Ay)", score: 1 },
      { text: "Orta Vadeli (6 Ay - 2 Yıl)", score: 3 },
      { text: "Uzun Vadeli (> 2 Yıl)", score: 5 },
    ],
  },
  {
    id: 4,
    question: "Finansal piyasalar ve yatırım araçları konusundaki bilgi seviyeniz nedir?",
    options: [
      { text: "Yeni başlayanım, sadece mevduat ve düşük riskli araçları biliyorum", score: 1 },
      { text: "Orta düzeyde bilgiye sahibim, yatırım fonlarını takip ediyorum", score: 3 },
      { text: "Uzman seviyesindeyim, hisse senedi ve türev araçları aktif kullanıyorum", score: 5 },
    ],
  },
  {
    id: 5,
    question: "Aylık tasarruflarınızın ne kadarını riskli yatırım fonlarına yönlendirebilirsiniz?",
    options: [
      { text: "En fazla %10'unu, gerisini güvenli limanlarda tutarım", score: 1 },
      { text: "%10 ile %40 arasını yönlendirebilirim", score: 3 },
      { text: "%40'tan fazlasını yüksek getiri potansiyeli için yatırabilirim", score: 5 },
    ],
  },
];

export default function PortfolioPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"portfolio" | "simulator" | "risk" | "alerts">("portfolio");

  // Load Session ID from localStorage on mount (suppressing SSR mismatch)
  useEffect(() => {
    const saved = localStorage.getItem("tefas_portfolio_session");
    if (saved) {
      setSessionId(saved);
    } else {
      const newId = Math.random().toString(36).substring(2, 15);
      localStorage.setItem("tefas_portfolio_session", newId);
      setSessionId(newId);
    }
  }, []);

  // API Hooks
  const { data: summaryData, isLoading: isSummaryLoading } = usePortfolioSummary(sessionId);
  const { data: txData, isLoading: isTxLoading } = usePortfolioTransactions(sessionId);
  const { data: allocData, isLoading: isAllocLoading } = usePortfolioAllocation(sessionId);
  const { data: alertsData, isLoading: isAlertsLoading } = usePortfolioAlerts(sessionId);
  const { data: notificationsData, mutate: mutateNotifications } = usePortfolioNotifications(sessionId);
  const { data: perfData, isLoading: isPerfLoading } = usePortfolioPerformance(sessionId);

  // States: Transaction Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [txType, setTxType] = useState<"BUY" | "SELL">("BUY");
  const [searchQuery, setSearchQuery] = useState("");
  const [fundCode, setFundCode] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const [units, setUnits] = useState("");
  const [price, setPrice] = useState("");
  const [date, setDate] = useState("");

  // States: Alert Manager
  const [alertFundCode, setAlertFundCode] = useState("");
  const [alertSearchQuery, setAlertSearchQuery] = useState("");
  const [showAlertDropdown, setShowAlertDropdown] = useState(false);
  const [alertThreshold, setAlertThreshold] = useState("");
  const [isAlertSubmitting, setIsAlertSubmitting] = useState(false);

  // States: Notification Tray (Bell dropdown)
  const [isBellOpen, setIsBellOpen] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const csvInputRef = useRef<HTMLInputElement>(null);
  const prevNotifCount = useRef(0);

  // States: Simulator
  const [simFundCode, setSimFundCode] = useState("");
  const [simSearchQuery, setSimSearchQuery] = useState("");
  const [showSimDropdown, setShowSimDropdown] = useState(false);
  const [simAmount, setSimAmount] = useState("10000");
  const [simStartDate, setSimStartDate] = useState("2025-01-01");
  const [simResult, setSimResult] = useState<any>(null);
  const [isSimLoading, setIsSimLoading] = useState(false);

  // States: Risk Profiler Quiz
  const [quizStep, setQuizStep] = useState(0); // 0: intro, 1..5: questions, 6: results
  const [quizScores, setQuizScores] = useState<number[]>([]);
  const [recommendedFunds, setRecommendedFunds] = useState<any[]>([]);

  // States: Yapay Zeka (AI) Modülü (Faz 4)
  const [isAiReviewLoading, setIsAiReviewLoading] = useState(false);
  const [aiReviewStep, setAiReviewStep] = useState("");
  const [aiReviewResult, setAiReviewResult] = useState<string | null>(null);

  const [isAiFundLoading, setIsAiFundLoading] = useState(false);
  const [aiFundResult, setAiFundResult] = useState<string | null>(null);
  const [selectedAiFundCode, setSelectedAiFundCode] = useState<string | null>(null);
  const [isAiFundModalOpen, setIsAiFundModalOpen] = useState(false);

  // Dynamic user risk profile calculation from quiz scores
  const currentRiskProfile = useMemo(() => {
    if (quizScores.length === 0) return "Belirtilmedi";
    const totalScore = quizScores.reduce((a, b) => a + b, 0);
    if (totalScore <= 8) return "Temkinli / Düşük Riskli";
    if (totalScore > 18) return "Agresif / Yüksek Riskli";
    return "Dengeli / Orta Riskli";
  }, [quizScores]);


  // Search funds for autocomplete lists
  const { data: searchResults } = useFunds({ search: searchQuery, page_size: 5 });
  const { data: alertSearchResults } = useFunds({ search: alertSearchQuery, page_size: 5 });
  const { data: simSearchResults } = useFunds({ search: simSearchQuery, page_size: 5 });

  // Fetch individual fund price when transaction form fund changes
  useEffect(() => {
    if (!fundCode) return;
    const fetchLatestPrice = async () => {
      try {
        const res = await fetch(`/api/fund/${fundCode}`);
        if (res.ok) {
          const detail = await res.json();
          const lastPoint = detail.history?.[detail.history.length - 1];
          if (lastPoint && lastPoint.price) {
            setPrice(String(lastPoint.price));
          }
        }
      } catch (err) {
        console.error("Fiyat alınamadı", err);
      }
    };
    fetchLatestPrice();
  }, [fundCode]);

  // Set today as default date on load (suppress hydration warnings)
  useEffect(() => {
    setDate(new Date().toISOString().split("T")[0]);
  }, []);

  // Toast when new price alerts trigger on poll
  useEffect(() => {
    const count = activeTriggeredNotifications.length;
    if (count > prevNotifCount.current && prevNotifCount.current > 0) {
      setToastMsg(`${count - prevNotifCount.current} yeni fiyat alarmı tetiklendi`);
      const t = setTimeout(() => setToastMsg(null), 5000);
      return () => clearTimeout(t);
    }
    prevNotifCount.current = count;
  }, [activeTriggeredNotifications.length]);

  // Handlers: Yapay Zeka (AI) Modülü (Faz 4)
  const handleAiPortfolioReview = async () => {
    if (!sessionId) return;
    setIsAiReviewLoading(true);
    setAiReviewResult(null);

    // Dynamic animated step-by-step loading state
    setAiReviewStep("📊 Portföy pozisyonları analiz ediliyor...");
    const t1 = setTimeout(() => setAiReviewStep("💰 Varlık dağılım oranları çıkarılıyor..."), 1500);
    const t2 = setTimeout(() => setAiReviewStep("🧠 Gemini AI ile portföy sağlık incelemesi yapılıyor..."), 3000);

    try {
      const res = await getAiPortfolioReview(sessionId);
      setAiReviewResult(res.analysis || "Analiz raporu boş döndü.");
    } catch (err: any) {
      console.error(err);
      setAiReviewResult("### ⚠️ Hata\nAnaliz üretilirken bir hata oluştu. Lütfen `.env` dosyanızda `GEMINI_API_KEY` değişkeninin tanımlı olduğunu ve internet bağlantınızı kontrol edin.");
    } finally {
      clearTimeout(t1);
      clearTimeout(t2);
      setIsAiReviewLoading(false);
      setAiReviewStep("");
    }
  };

  const handleAiFundInterpretation = async (code: string) => {
    setSelectedAiFundCode(code);
    setIsAiFundModalOpen(true);
    setIsAiFundLoading(true);
    setAiFundResult(null);

    try {
      const res = await getAiFundInterpretation(code, currentRiskProfile);
      setAiFundResult(res.analysis || "Analiz boş döndü.");
    } catch (err: any) {
      console.error(err);
      setAiFundResult("### ⚠️ Hata\nYapay zeka fon analizi üretilirken bir hata oluştu. Lütfen `.env` dosyanızda `GEMINI_API_KEY` değişkeninin tanımlı olduğunu ve internet bağlantınızı kontrol edin.");
    } finally {
      setIsAiFundLoading(false);
    }
  };

  // Handlers: Transaction
  const handleAddTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fundCode || !units || !price) {
      alert("Lütfen tüm alanları doldurun.");
      return;
    }

    try {
      const res = await fetch("/api/portfolio/transaction", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          code: fundCode.toUpperCase(),
          tx_type: txType,
          date,
          units: parseFloat(units),
          unit_price: parseFloat(price),
        }),
      });

      if (res.ok) {
        setFundCode("");
        setSearchQuery("");
        setUnits("");
        setPrice("");
        setIsModalOpen(false);

        mutate(`/api/portfolio/summary?session_id=${sessionId}`);
        mutate(`/api/portfolio/transactions?session_id=${sessionId}`);
        mutate(`/api/portfolio/allocation?session_id=${sessionId}`);
        mutate(`/api/portfolio/performance?session_id=${sessionId}`);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteTransaction = async (txId: number) => {
    if (!confirm("Bu işlemi silmek istediğinize emin misiniz?")) return;

    try {
      const res = await fetch(`/api/portfolio/transaction/${txId}`, {
        method: "DELETE",
      });

      if (res.ok) {
        mutate(`/api/portfolio/summary?session_id=${sessionId}`);
        mutate(`/api/portfolio/transactions?session_id=${sessionId}`);
        mutate(`/api/portfolio/allocation?session_id=${sessionId}`);
        mutate(`/api/portfolio/performance?session_id=${sessionId}`);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleExportCSV = () => {
    if (!txData?.transactions || txData.transactions.length === 0) return;

    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "Islem ID,Fon Kodu,Islem Tipi,Tarih,Adet,Birim Fiyat (TL),Toplam Tutar (TL)\n";

    txData.transactions.forEach((tx: any) => {
      csvContent += `${tx.id},${tx.code},${tx.tx_type === "BUY" ? "ALIS" : "SATIS"},${tx.date},${tx.units},${tx.unit_price},${(tx.units * tx.unit_price).toFixed(4)}\n`;
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `portfoy_islem_raporu_${new Date().toISOString().split("T")[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Handlers: Alert Manager
  const handleAddAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!alertFundCode || !alertThreshold || !sessionId) {
      alert("Lütfen fon kodunu ve eşik değerini doldurun.");
      return;
    }

    setIsAlertSubmitting(true);
    try {
      await createPortfolioAlert(
        sessionId,
        alertFundCode.toUpperCase(),
        parseFloat(alertThreshold)
      );
      setAlertFundCode("");
      setAlertSearchQuery("");
      setAlertThreshold("");
      mutate(`/api/portfolio/alerts?session_id=${sessionId}`);
      mutateNotifications(); // Refresh live notifications immediately
    } catch (err) {
      console.error("Alarm kuralı eklenemedi", err);
    } finally {
      setIsAlertSubmitting(false);
    }
  };

  const handleDeleteAlert = async (alertId: number) => {
    try {
      await deletePortfolioAlert(alertId);
      mutate(`/api/portfolio/alerts?session_id=${sessionId}`);
      mutateNotifications();
    } catch (err) {
      console.error("Alarm kuralı silinemedi", err);
    }
  };

  // Handlers: Simulator
  const handleRunSimulator = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!simFundCode || !simAmount || !simStartDate) {
      alert("Lütfen tüm alanları doldurun.");
      return;
    }

    setIsSimLoading(true);
    setSimResult(null);
    try {
      const data = await runInvestmentSimulation(
        simFundCode.toUpperCase(),
        parseFloat(simAmount),
        simStartDate
      );
      setSimResult(data);
    } catch (err) {
      console.error("Simülasyon hatası", err);
    } finally {
      setIsSimLoading(false);
    }
  };

  // Handlers: Risk Profiler Quiz
  const handleQuizAnswer = (score: number) => {
    const nextScores = [...quizScores, score];
    setQuizScores(nextScores);

    if (quizStep < QUIZ_QUESTIONS.length) {
      setQuizStep(quizStep + 1);
    }

    // If it was the last question, evaluate results
    if (quizStep === QUIZ_QUESTIONS.length) {
      const totalScore = nextScores.reduce((a, b) => a + b, 0);
      let profile = "Dengeli";
      let recs = [];

      if (totalScore <= 9) {
        profile = "Defansif / Temkinli";
        // Recommended Low Risk Funds
        recs = [
          { code: "TTA", name: "İş Portföy Altın Fonu", cat: "Kıymetli Madenler", yield: "Orta-Yüksek İstikrar" },
          { code: "TI1", name: "İş Portföy Para Piyasası Fonu", cat: "Para Piyasası", yield: "Düşük Risk, Düzenli Getiri" },
          { code: "HCV", name: "Halk Portföy Borçlanma Araçları Fonu", cat: "Borçlanma Araçları", yield: "Dengeli Sabit Getiri" },
        ];
      } else if (totalScore <= 18) {
        profile = "Dengeli / Moderate";
        recs = [
          { code: "HCV", name: "Halk Portföy Eurobond Borçlanma Araçları", cat: "Döviz / Eurobond", yield: "Dengeli Döviz Getirisi" },
          { code: "TI1", name: "İş Portföy BIST 30 Endeksi Fonu", cat: "Hisse Senedi / Endeks", yield: "BIST Trend Takibi" },
          { code: "TTA", name: "İş Portföy Altın Katılım Fonu", cat: "Kıymetli Madenler", yield: "Altın Koruma" },
        ];
      } else {
        profile = "Agresif / Büyüme Odaklı";
        recs = [
          { code: "MAC", name: "Marmara Capital Portföy Hisse Senedi Fonu", cat: "Hisse Senedi (Yoğun)", yield: "Yüksek Getiri Potansiyeli" },
          { code: "YAS", name: "Yapı Kredi Portföy Koç Holding İştirakleri", cat: "Hisse Senedi (Yoğun)", yield: "Öncü Holding Büyümesi" },
          { code: "TTA", name: "İş Portföy Altın Fonu", cat: "Kıymetli Madenler", yield: "Yüksek Oynaklık" },
        ];
      }

      setRecommendedFunds(recs);
      setQuizStep(6); // Show results view
    }
  };

  const handleResetQuiz = () => {
    setQuizStep(0);
    setQuizScores([]);
    setRecommendedFunds([]);
  };

  // Helper to determine risk score 1-7 for a fund based on name/code
  const getFundRiskScore = (name: string, code: string): number => {
    const n = (name || "").toUpperCase();
    const c = (code || "").toUpperCase();
    if (n.includes("PARA PİYASASI") || n.includes("KISA VADELİ") || c === "TI1") {
      return 1;
    }
    if (n.includes("BORÇLANMA") || n.includes("KIRA") || c === "HCV") {
      return 3;
    }
    if (n.includes("ALTIN") || n.includes("GÜMÜŞ") || n.includes("KIYMETLİ") || c === "TTA") {
      return 5;
    }
    if (n.includes("HİSSE") || n.includes("BİST") || ["MAC", "YAS", "KLH", "BMU"].includes(c)) {
      return 7;
    }
    return 4; // balanced / mid risk
  };

  // Helper to determine estimated annual management fee % based on category/name
  const getFundManagementFee = (name: string, code: string): number => {
    const n = (name || "").toUpperCase();
    const c = (code || "").toUpperCase();
    if (n.includes("PARA PİYASASI") || n.includes("KISA VADELİ") || c === "TI1") {
      return 0.75;
    }
    if (n.includes("HİSSE") || n.includes("BİST") || ["MAC", "YAS", "KLH", "BMU"].includes(c)) {
      return 2.25;
    }
    return 1.50; // balanced / debt instrument fee
  };

  // Blended Portfolio Metrics
  const blendedMetrics = useMemo(() => {
    if (!summaryData?.holdings || summaryData.holdings.length === 0) {
      return { riskScore: 0, feeRate: 0 };
    }
    let totalValue = 0;
    let weightedRisk = 0;
    let weightedFee = 0;

    summaryData.holdings.forEach((h: any) => {
      const val = h.current_value || 0;
      totalValue += val;
      weightedRisk += val * getFundRiskScore(h.name, h.code);
      weightedFee += val * getFundManagementFee(h.name, h.code);
    });

    if (totalValue === 0) return { riskScore: 0, feeRate: 0 };
    return {
      riskScore: weightedRisk / totalValue,
      feeRate: weightedFee / totalValue,
    };
  }, [summaryData?.holdings]);

  const hasHoldings = summaryData?.holdings && summaryData.holdings.length > 0;
  const activeTriggeredNotifications = notificationsData?.notifications || [];

  return (
    <div className="mx-auto max-w-[1600px] space-y-6 p-6">
      {/* Top Floating Glass Bar for Header & Live Notifications */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/6 pb-6 relative z-30">
        <div>
          <h1 className="text-xl font-extrabold tracking-tight flex items-center gap-2">
            <Briefcase className="h-5.5 w-5.5 text-blue-500" />
            Portföy & Analiz Platformu
          </h1>
          <p className="text-xs text-zinc-400">
            Ağırlıklı ortalama maliyetinizi izleyin, getiri simüle edin, akıllı risk testi yapın ve limit alarmları kurun.
          </p>
        </div>

        <div className="flex items-center gap-3 self-end md:self-auto">
          {/* Notifications Zil Icon Dropdown */}
          <div className="relative">
            <button
              onClick={() => setIsBellOpen(!isBellOpen)}
              className="relative rounded-xl border border-white/8 bg-white/3 p-2.5 text-zinc-400 hover:bg-white/5 hover:text-white transition-all cursor-pointer"
            >
              <Bell className="h-4.5 w-4.5" />
              {activeTriggeredNotifications.length > 0 && (
                <span className="absolute -top-1.5 -right-1.5 flex h-4.5 w-4.5 items-center justify-center rounded-full bg-rose-500 text-[9px] font-extrabold text-white animate-bounce shadow-lg shadow-rose-500/30">
                  {activeTriggeredNotifications.length}
                </span>
              )}
            </button>

            {/* Bell Dropdown Tray (Glassmorphism list) */}
            {isBellOpen && (
              <div className="absolute right-0 mt-2.5 w-80 rounded-2xl border border-white/10 bg-[#0d1426]/95 backdrop-blur-2xl p-4 shadow-2xl z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                <div className="flex items-center justify-between border-b border-white/8 pb-2 mb-3">
                  <span className="text-xs font-extrabold text-white flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5 text-yellow-400" />
                    Tetiklenen Alarmlar
                  </span>
                  <span className="text-[10px] text-zinc-400 font-mono">En Son Seans</span>
                </div>

                <div className="space-y-2.5 max-h-[250px] overflow-y-auto">
                  {activeTriggeredNotifications.length > 0 ? (
                    activeTriggeredNotifications.map((notif: any) => (
                      <div
                        key={notif.rule_id}
                        className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-2.5 text-left text-xs space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-rose-400 bg-rose-500/10 px-1.5 py-0.5 rounded text-[10px]">
                            {notif.code}
                          </span>
                          <span className="text-[10px] text-zinc-500 font-medium">{notif.date}</span>
                        </div>
                        <p className="text-zinc-300 text-[11px] leading-relaxed font-normal">
                          <span className="font-bold text-white">{notif.name}</span> fonu dünkü seansı{" "}
                          <span className="font-extrabold text-rose-400">{formatPct(notif.pct_change)}</span> getiri ile
                          kapatarak kurduğunuz <span className="font-bold">{notif.threshold > 0 ? `+${notif.threshold}%` : `${notif.threshold}%`}</span> alarmını aştı!
                        </p>
                        <div className="flex justify-between items-center text-[10px] text-zinc-500 font-medium">
                          <span>Fiyat: {formatPrice(notif.current_price)}</span>
                          <button
                            onClick={() => handleDeleteAlert(notif.rule_id)}
                            className="text-zinc-500 hover:text-rose-400 transition-colors flex items-center gap-0.5 cursor-pointer font-bold"
                          >
                            Alarımı Sil
                          </button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="py-6 text-center text-[11px] text-zinc-500 italic space-y-1">
                      <CheckCircle className="h-5 w-5 text-zinc-600 mx-auto mb-1" />
                      Tetiklenen aktif alarm bulunmuyor.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 rounded-xl bg-blue-500 px-4 py-2.5 text-xs font-bold text-white transition-all hover:bg-blue-600 hover:shadow-[0_0_15px_rgba(59,130,246,0.3)] cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            İşlem Ekle
          </button>
        </div>
      </div>

      {/* Modern High-Fidelity Tab Bar */}
      <div className="flex items-center gap-1.5 border-b border-white/4 pb-1 overflow-x-auto whitespace-nowrap scrollbar-none">
        {[
          { id: "portfolio", label: "Portföyüm", icon: <Briefcase className="h-4 w-4" /> },
          { id: "simulator", label: "Getiri Simülatörü", icon: <BarChart3 className="h-4 w-4" /> },
          { id: "risk", label: "Risk Testi ve Öneriler", icon: <Sparkles className="h-4 w-4" /> },
          { id: "alerts", label: "Alarm Yönetimi", icon: <Bell className="h-4 w-4" /> },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id as any)}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition-all cursor-pointer border ${
              activeTab === t.id
                ? "bg-blue-500 border-blue-500 text-white shadow-lg shadow-blue-500/20"
                : "border-transparent text-zinc-400 hover:text-white hover:bg-white/3"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Panels */}

      {/* ── TAB 1: PORTFOLIO ────────────────────────────────────────── */}
      {activeTab === "portfolio" && (
        <div className="space-y-6">
          {/* KPI Cards */}
          {isSummaryLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Skeleton count={1} className="h-28" />
              <Skeleton count={1} className="h-28" />
              <Skeleton count={1} className="h-28" />
              <Skeleton count={1} className="h-28" />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="glass p-5 space-y-2">
                <span className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Toplam Portföy Değeri</span>
                <div className="text-2xl font-extrabold text-white">
                  {formatTL(summaryData?.summary?.total_value)}
                </div>
                <div className="text-[10px] text-zinc-500 font-medium">
                  Güncel TEFAS fiyatları ile hesaplanmıştır.
                </div>
              </div>

              <div className="glass p-5 space-y-2">
                <span className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Toplam Maliyet</span>
                <div className="text-2xl font-extrabold text-zinc-300">
                  {formatTL(summaryData?.summary?.total_cost)}
                </div>
                <div className="text-[10px] text-zinc-500 font-medium">
                  Weighted Average Cost baz alınmıştır.
                </div>
              </div>

              <div className="glass p-5 space-y-2">
                <span className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Toplam Kâr / Zarar</span>
                <div className={`text-2xl font-extrabold flex items-baseline gap-2 ${pctColor(summaryData?.summary?.total_profit)}`}>
                  <span>{formatTL(summaryData?.summary?.total_profit)}</span>
                  <span className="text-sm font-semibold">({formatPct(summaryData?.summary?.total_profit_pct)})</span>
                </div>
                <div className="flex items-center gap-1.5 text-[10px] font-medium text-zinc-500">
                  {summaryData?.summary?.total_profit >= 0 ? (
                    <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <TrendingDown className="h-3.5 w-3.5 text-rose-400" />
                  )}
                  Net getiri durumu.
                </div>
              </div>

              <div className="glass p-5 space-y-2">
                <span className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Günlük P&L Değişimi</span>
                <div className={`text-2xl font-extrabold ${pctColor(summaryData?.summary?.daily_profit)}`}>
                  {formatTL(summaryData?.summary?.daily_profit)}
                </div>
                <div className="text-[10px] text-zinc-500 font-medium">
                  Dünkü TEFAS fiyatlarına göre bugünkü net P&L.
                </div>
              </div>
            </div>
          )}

          {/* Blended Portfolio Metrics Summary Bar */}
          {!isSummaryLoading && hasHoldings && (
            <div className="glass p-4.5 flex flex-wrap items-center justify-between gap-4 animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="flex items-center gap-2 text-xs font-semibold text-zinc-400">
                <Shield className="h-4 w-4 text-emerald-400" />
                <span>Ağırlıklı Portföy Risk Seviyesi:</span>
                <span className="font-extrabold text-white bg-white/5 border border-white/8 px-2 py-0.5 rounded-lg font-mono">
                  {blendedMetrics.riskScore.toFixed(1)} / 7.0
                </span>
                <span className="text-[10px] text-zinc-500 font-medium">
                  ({blendedMetrics.riskScore <= 2.5 ? "Düşük Risk" : blendedMetrics.riskScore <= 5.0 ? "Orta Risk" : "Yüksek Risk"})
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs font-semibold text-zinc-400">
                <Percent className="h-4 w-4 text-blue-400" />
                <span>Ağırlıklı Yıllık Yönetim Ücreti:</span>
                <span className="font-extrabold text-white bg-white/5 border border-white/8 px-2 py-0.5 rounded-lg font-mono font-bold">
                  %{blendedMetrics.feeRate.toFixed(2)}
                </span>
                <span className="text-[10px] text-zinc-500 font-medium">(Ağırlıklı Oran)</span>
              </div>
            </div>
          )}

          {/* Main Layout Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Holdings & Transaction Tables */}
            <div className="lg:col-span-2 space-y-6">
              {/* Historical Performance Timeline Chart */}
              {!isSummaryLoading && hasHoldings && (
                <div className="glass p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <TrendingUp className="h-4 w-4 text-emerald-400" />
                      Portföy Değer Gelişimi (Son 30 Gün)
                    </h3>
                    <span className="text-[10px] text-zinc-500 font-medium">Günlük Değer ve Yatırılan Sermaye Kıyası</span>
                  </div>

                  {isPerfLoading ? (
                    <div className="h-64 flex items-center justify-center">
                      <Skeleton count={1} className="w-full h-full" />
                    </div>
                  ) : perfData?.performance && perfData.performance.length > 0 ? (
                    <div className="h-64 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={perfData.performance} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                          <defs>
                            <linearGradient id="perfValueGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                          <XAxis 
                            dataKey="date" 
                            stroke="rgba(255,255,255,0.3)" 
                            fontSize={10}
                            tickLine={false}
                            tickFormatter={(date) => {
                              const parts = date.split('-');
                              return parts.length === 3 ? `${parts[2]}/${parts[1]}` : date;
                            }}
                          />
                          <YAxis 
                            stroke="rgba(255,255,255,0.3)" 
                            fontSize={10} 
                            tickLine={false}
                            tickFormatter={(val) => formatTL(val)}
                          />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: "#0d1426",
                              border: "1px solid rgba(255,255,255,0.08)",
                              borderRadius: "12px",
                            }}
                            labelClassName="text-xs text-zinc-400 font-bold"
                            formatter={(value: any, name: any) => {
                              if (name === "value") return [formatTL(value), "Portföy Değeri"];
                              if (name === "cost") return [formatTL(value), "Yatırılan Sermaye"];
                              if (name === "profit") return [formatTL(value), "Toplam Kâr/Zarar"];
                              return [value, name];
                            }}
                          />
                          <Area 
                            type="monotone" 
                            dataKey="value" 
                            stroke="#3b82f6" 
                            strokeWidth={2}
                            fillOpacity={1} 
                            fill="url(#perfValueGrad)" 
                          />
                          <Area 
                            type="monotone" 
                            dataKey="cost" 
                            stroke="rgba(255,255,255,0.4)" 
                            strokeWidth={1.5}
                            strokeDasharray="4 4"
                            fill="none" 
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="h-64 flex flex-col items-center justify-center text-center text-zinc-500 text-xs italic space-y-2 border border-dashed border-white/6 rounded-2xl">
                      <TrendingUp className="h-8 w-8 text-zinc-600" />
                      <span>Portföy gelişim grafiğini görmek için işlem ekleyin.</span>
                    </div>
                  )}
                </div>
              )}

              {/* AI Portfolio Review Card */}
              {!isSummaryLoading && hasHoldings && (
                <div className="relative overflow-hidden rounded-2xl border border-purple-500/20 bg-gradient-to-r from-purple-900/10 via-indigo-900/10 to-blue-900/10 backdrop-blur-xl p-6 shadow-2xl space-y-5 animate-in fade-in duration-300">
                  {/* Glowing dynamic background light */}
                  <div className="absolute top-0 right-0 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
                  
                  <div className="flex flex-wrap items-center justify-between gap-4 relative z-10">
                    <div className="space-y-1">
                      <h3 className="text-base font-extrabold text-white flex items-center gap-2 tracking-tight">
                        <Sparkles className="h-5 w-5 text-purple-400 animate-pulse" />
                        <span>Yapay Zeka Portföy Analizi (Gemini AI)</span>
                        <span className="text-[9px] uppercase tracking-wider font-extrabold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                          PREMIUM
                        </span>
                      </h3>
                      <p className="text-xs text-zinc-400 font-medium">
                        Portföy çeşitlendirmesini, maliyet durumunu ve risk uyumluluğunu yapay zeka ile anında denetleyin.
                      </p>
                    </div>
                    
                    <button
                      onClick={handleAiPortfolioReview}
                      disabled={isAiReviewLoading}
                      className={`relative overflow-hidden px-5 py-2.5 rounded-xl text-xs font-bold text-white shadow-lg shadow-purple-500/20 transition-all duration-300 transform active:scale-95 cursor-pointer flex items-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 border border-purple-400/20 ${
                        isAiReviewLoading ? "opacity-75 cursor-not-allowed animate-pulse" : "hover:shadow-purple-500/40 hover:scale-[1.02]"
                      }`}
                    >
                      <Sparkles className={`h-4 w-4 ${isAiReviewLoading ? "animate-spin" : ""}`} />
                      {isAiReviewLoading ? "Analiz Ediliyor..." : "Akıllı İnceleme Başlat"}
                    </button>
                  </div>

                  {/* Loading sequence */}
                  {isAiReviewLoading && (
                    <div className="p-8 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col items-center justify-center space-y-4 relative z-10 animate-pulse">
                      <div className="relative">
                        <div className="w-10 h-10 rounded-full border-2 border-purple-500/20 border-t-purple-400 animate-spin" />
                        <Sparkles className="h-4 w-4 text-purple-400 absolute inset-0 m-auto animate-bounce" />
                      </div>
                      <div className="space-y-1 text-center">
                        <p className="text-xs font-bold text-purple-300 animate-pulse">{aiReviewStep}</p>
                        <p className="text-[10px] text-zinc-500 font-medium">Bu işlem ortalama 5-10 saniye sürmektedir.</p>
                      </div>
                    </div>
                  )}

                  {/* Markdown Results card */}
                  {aiReviewResult && !isAiReviewLoading && (
                    <div className="relative z-10 rounded-xl bg-black/30 border border-white/5 p-5.5 space-y-4 max-h-[500px] overflow-y-auto custom-scrollbar animate-in slide-in-from-top-4 duration-300">
                      <div className="flex items-center justify-between border-b border-white/10 pb-3">
                        <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider">
                          Gemini 1.5 Flash Tarafından Üretilen Yatırımcı Analizi
                        </span>
                        <button
                          onClick={() => setAiReviewResult(null)}
                          className="text-zinc-500 hover:text-white transition-colors cursor-pointer text-xs font-semibold"
                        >
                          Temizle
                        </button>
                      </div>
                      
                      {/* Stylized markdown rendering */}
                      <div className="text-zinc-200 text-xs leading-relaxed space-y-4.5 font-medium whitespace-pre-line selection:bg-purple-500/30">
                        {aiReviewResult}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Holdings */}
              <div className="glass p-5 space-y-4">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Briefcase className="h-4 w-4 text-blue-400" />
                  Aktif Varlıklarım
                </h3>

                {isSummaryLoading ? (
                  <Skeleton count={4} />
                ) : hasHoldings ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-white/6 text-zinc-400 font-semibold uppercase tracking-wider text-[10px]">
                          <th className="pb-3">Fon</th>
                          <th className="pb-3">Adet</th>
                          <th className="pb-3">Ort. Maliyet</th>
                          <th className="pb-3">Son Fiyat</th>
                          <th className="pb-3">Maliyet (TL)</th>
                          <th className="pb-3">Güncel Değer</th>
                          <th className="pb-3 text-right">Kâr/Zarar</th>
                          <th className="pb-3 text-right">AI Analiz</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summaryData.holdings.map((h: any) => (
                          <tr key={h.code} className="border-b border-white/4 hover:bg-white/2 transition-colors">
                            <td className="py-3 font-semibold text-white">
                              <Link href={`/fon/${h.code}`} className="hover:text-blue-400 transition-colors">
                                <span className="font-mono font-bold text-blue-400 mr-2">{h.code}</span>
                                <span className="text-[11px] text-zinc-400 line-clamp-1 max-w-[150px] inline-block align-middle">{h.name}</span>
                              </Link>
                            </td>
                            <td className="py-3 font-mono text-zinc-300">{formatNumber(h.units)}</td>
                            <td className="py-3 font-mono text-zinc-300">{formatPrice(h.avg_cost)}</td>
                            <td className="py-3 font-mono text-zinc-300">{formatPrice(h.current_price)}</td>
                            <td className="py-3 font-mono text-zinc-400">{formatTL(h.total_cost)}</td>
                            <td className="py-3 font-mono font-bold text-white">{formatTL(h.current_value)}</td>
                            <td className="py-3">
                              <div className={`font-bold flex flex-col items-end ${pctColor(h.profit)}`}>
                                <span>{formatTL(h.profit)}</span>
                                <span className="text-[10px] font-semibold">({formatPct(h.profit_pct)})</span>
                              </div>
                            </td>
                            <td className="py-3 text-right">
                              <button
                                onClick={() => handleAiFundInterpretation(h.code)}
                                className="px-2.5 py-1 rounded-md text-[10px] font-extrabold bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 hover:border-purple-500/40 text-purple-300 transition-all duration-200 flex items-center gap-1 ml-auto cursor-pointer"
                              >
                                <Sparkles className="h-3.5 w-3.5 text-purple-400" />
                                Yapay Zeka
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-12 text-zinc-500 text-xs italic">
                    Aktif varlığınız bulunmuyor. İşlem Ekle butonunu kullanarak ekleyebilirsiniz.
                  </div>
                )}
              </div>

              {/* Transactions Log */}
              <div className="glass p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-indigo-400" />
                    İşlem Geçmişi
                  </h3>
                  <button
                    onClick={handleExportCSV}
                    disabled={!txData?.transactions || txData.transactions.length === 0}
                    className="flex items-center gap-1.5 rounded-lg border border-white/8 bg-white/3 px-3 py-1.5 text-[11px] font-bold text-zinc-300 transition-all hover:bg-white/5 hover:text-white disabled:opacity-40 cursor-pointer"
                  >
                    <Download className="h-3.5 w-3.5" />
                    CSV İndir
                  </button>
                </div>

                {isTxLoading ? (
                  <Skeleton count={4} />
                ) : txData?.transactions && txData.transactions.length > 0 ? (
                  <div className="overflow-x-auto max-h-[350px] overflow-y-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-white/6 text-zinc-400 font-semibold uppercase tracking-wider text-[10px] sticky top-0 bg-[#0d1426]/95 backdrop-blur z-10">
                          <th className="pb-3">Tarih</th>
                          <th className="pb-3">Fon</th>
                          <th className="pb-3">İşlem</th>
                          <th className="pb-3">Adet</th>
                          <th className="pb-3">Birim Fiyat</th>
                          <th className="pb-3">Tutar (TL)</th>
                          <th className="pb-3 text-right">İşlem</th>
                        </tr>
                      </thead>
                      <tbody>
                        {txData.transactions.map((tx: any) => (
                          <tr key={tx.id} className="border-b border-white/4 hover:bg-white/2 transition-colors">
                            <td className="py-2.5 font-mono text-zinc-400">{tx.date}</td>
                            <td className="py-2.5 font-semibold text-white">
                              <span className="font-mono font-bold text-blue-400 mr-2">{tx.code}</span>
                              <span className="text-[10px] text-zinc-500 max-w-[130px] line-clamp-1 inline-block align-middle">{tx.name}</span>
                            </td>
                            <td className="py-2.5">
                              <Badge className={tx.tx_type === "BUY" ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" : "bg-rose-500/10 border-rose-500/30 text-rose-400"}>
                                {tx.tx_type === "BUY" ? "ALIS" : "SATIS"}
                              </Badge>
                            </td>
                            <td className="py-2.5 font-mono text-zinc-300">{formatNumber(tx.units)}</td>
                            <td className="py-2.5 font-mono text-zinc-300">{formatPrice(tx.unit_price)}</td>
                            <td className="py-2.5 font-mono text-zinc-300">{formatTL(tx.units * tx.unit_price)}</td>
                            <td className="py-2.5 text-right">
                              <button
                                onClick={() => handleDeleteTransaction(tx.id)}
                                className="rounded-lg p-1.5 text-zinc-500 hover:bg-rose-500/10 hover:text-rose-400 transition-colors cursor-pointer"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-12 text-zinc-500 text-xs italic">
                    Kayıtlı işlem geçmişi bulunmuyor.
                  </div>
                )}
              </div>
            </div>

            {/* Asset Allocation Donut Chart */}
            <div className="space-y-6">
              <div className="glass p-5 space-y-4">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <PieIcon className="h-4 w-4 text-emerald-400" />
                  Portföy Varlık Dağılımı
                </h3>

                {isAllocLoading ? (
                  <div className="h-64 flex items-center justify-center">
                    <Skeleton count={1} className="w-full h-full" />
                  </div>
                ) : allocData?.allocation && allocData.allocation.length > 0 ? (
                  <div className="space-y-6">
                    <div className="h-[220px] w-full relative">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={allocData.allocation}
                            dataKey="value"
                            nameKey="category"
                            cx="50%"
                            cy="50%"
                            innerRadius={60}
                            outerRadius={85}
                            paddingAngle={2}
                          >
                            {allocData.allocation.map((entry: any, index: number) => (
                              <Cell key={`cell-${index}`} fill={ALLOCATION_COLORS[index % ALLOCATION_COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{
                              backgroundColor: "#0d1426",
                              border: "1px solid rgba(255,255,255,0.08)",
                              borderRadius: "12px",
                            }}
                            formatter={(val: number) => [formatTL(val), "Değer"]}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>

                    <div className="space-y-3.5">
                      {allocData.allocation.map((item: any, idx: number) => (
                        <div key={item.category} className="space-y-1">
                          <div className="flex justify-between items-center text-xs font-semibold text-zinc-400">
                            <div className="flex items-center gap-2">
                              <div
                                className="h-2.5 w-2.5 rounded-full"
                                style={{ backgroundColor: ALLOCATION_COLORS[idx % ALLOCATION_COLORS.length] }}
                              ></div>
                              <span>{item.category}</span>
                            </div>
                            <div className="flex gap-2 items-baseline">
                              <span className="text-[10px] text-zinc-500">{formatTL(item.value)}</span>
                              <span className="text-white text-[11px] font-extrabold">({formatPct(item.percentage)})</span>
                            </div>
                          </div>
                          <div className="h-1 w-full rounded-full bg-white/5 overflow-hidden">
                            <div
                              className="h-full"
                              style={{
                                width: `${item.percentage}%`,
                                backgroundColor: ALLOCATION_COLORS[idx % ALLOCATION_COLORS.length],
                              }}
                            ></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-16 text-zinc-500 text-xs italic">
                    Portföy dağılımını görmek için işlem ekleyin.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 2: GETİRİ SİMÜLATÖRÜ ─────────────────────────────────── */}
      {activeTab === "simulator" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Simulation Input Form */}
          <div className="glass p-6 space-y-4 h-fit">
            <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
              <Calendar className="h-4.5 w-4.5 text-blue-400" />
              Tarihsel Getiri Simülatörü
            </h3>
            <p className="text-[11px] text-zinc-400 leading-relaxed font-normal">
              Geçmişte belirli bir fona X TL yatırsaydınız, bugün ne kadar kâr elde edeceğinizi hesaplayın ve BIST100, Altın, Döviz ile kıyaslayın.
            </p>

            <form onSubmit={handleRunSimulator} className="space-y-4 text-xs">
              {/* Autocomplete Select */}
              <div className="space-y-1.5 relative">
                <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Yatırım Yapılacak Fon</label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
                  <input
                    type="text"
                    value={simSearchQuery}
                    onChange={(e) => {
                      setSimSearchQuery(e.target.value);
                      setSimFundCode(e.target.value.toUpperCase());
                      setShowSimDropdown(true);
                    }}
                    onFocus={() => setShowSimDropdown(true)}
                    placeholder="Fon kodu yazın (örn: HCV)..."
                    className="w-full rounded-xl border border-white/8 bg-white/3 py-2.5 pl-9 pr-4 text-white outline-none focus:border-blue-500"
                    required
                  />
                </div>

                {showSimDropdown && simSearchQuery.trim().length > 0 && (
                  <div className="absolute left-0 right-0 top-full mt-1.5 z-50 rounded-xl border border-white/10 bg-[#0d1426] p-1.5 shadow-2xl max-h-[160px] overflow-y-auto">
                    {simSearchResults?.funds && simSearchResults.funds.length > 0 ? (
                      simSearchResults.funds.map((f) => (
                        <button
                          key={f.code}
                          type="button"
                          onClick={() => {
                            setSimFundCode(f.code);
                            setSimSearchQuery(f.code);
                            setShowSimDropdown(false);
                          }}
                          className="flex w-full items-center justify-between rounded-lg p-2 text-left text-[11px] transition-colors hover:bg-white/5 cursor-pointer"
                        >
                          <div>
                            <span className="font-mono font-bold text-blue-400 mr-2">{f.code}</span>
                            <span className="text-zinc-300 font-medium line-clamp-1">{f.name}</span>
                          </div>
                        </button>
                      ))
                    ) : (
                      <div className="p-2 text-zinc-500">Sonuç bulunamadı</div>
                    )}
                  </div>
                )}
              </div>

              {/* Amount */}
              <div className="space-y-1.5">
                <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Yatırım Tutarı (TL)</label>
                <input
                  type="number"
                  value={simAmount}
                  onChange={(e) => setSimAmount(e.target.value)}
                  placeholder="Yatırım miktarı (örn: 10000)..."
                  className="w-full rounded-xl border border-white/8 bg-white/3 py-2.5 px-3.5 text-white outline-none focus:border-blue-500"
                  required
                />
              </div>

              {/* Date */}
              <div className="space-y-1.5">
                <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Başlangıç Tarihi</label>
                <input
                  type="date"
                  value={simStartDate}
                  onChange={(e) => setSimStartDate(e.target.value)}
                  className="w-full rounded-xl border border-white/8 bg-white/3 py-2.5 px-3.5 text-white outline-none focus:border-blue-500"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={isSimLoading}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-blue-500 py-3 font-bold text-white transition-all hover:bg-blue-600 disabled:opacity-50 cursor-pointer"
              >
                <Play className="h-4 w-4" />
                {isSimLoading ? "Simüle Ediliyor..." : "Simülasyonu Başlat"}
              </button>
            </form>
          </div>

          {/* Simulation Output results */}
          <div className="lg:col-span-2 space-y-6">
            {simResult ? (
              simResult.status === "error" ? (
                <div className="glass p-8 text-center text-rose-400 font-semibold space-y-2">
                  <X className="h-8 w-8 mx-auto" />
                  <p>{simResult.message}</p>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Results Overview */}
                  <div className="glass p-5 space-y-4">
                    <span className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Yatırım Büyümesi</span>
                    <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                      <div>
                        <div className="text-3xl font-extrabold text-white">
                          {formatTL(simResult.fund.end_value)}
                        </div>
                        <p className="text-[10px] text-zinc-400 mt-1 font-medium leading-relaxed">
                          <span className="font-mono text-blue-400">{simResult.fund.code}</span> kodu ile{" "}
                          <span className="font-bold text-white">{simResult.fund.start_date}</span> tarihinde yatırdığınız{" "}
                          <span className="font-bold text-white">{formatTL(simResult.fund.amount)}</span> tutar,{" "}
                          <span className="font-bold text-white">{simResult.fund.end_date}</span> tarihine kadar{" "}
                          <span className="font-mono text-zinc-300">({formatNumber(simResult.fund.units)} adet)</span> büyüme sağladı.
                        </p>
                      </div>

                      <div className="text-right">
                        <div className={`text-2xl font-extrabold flex items-baseline gap-1.5 justify-end ${pctColor(simResult.fund.profit)}`}>
                          <span>+{formatTL(simResult.fund.profit)}</span>
                          <span className="text-sm font-semibold">({formatPct(simResult.fund.profit_pct)})</span>
                        </div>
                        <span className="text-[10px] text-zinc-500 font-medium">Toplam Net Getiri</span>
                      </div>
                    </div>
                  </div>

                  {/* Benchmark Comparisons */}
                  <div className="glass p-5 space-y-4">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                      Alternatif Yatırım Kıyaslaması (P&L)
                    </h3>
                    <p className="text-[10px] text-zinc-500 leading-relaxed font-normal">
                      Aynı tutarı diğer enstrümanlara yatırsaydınız bugünkü toplam P&L tablonuz ne olurdu?
                    </p>

                    <div className="space-y-4">
                      {/* Selected Fund Bar */}
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs font-semibold text-zinc-400">
                          <span className="text-blue-400 font-bold">Fonunuz ({simResult.fund.code})</span>
                          <div className="flex gap-2">
                            <span>{formatTL(simResult.fund.end_value)}</span>
                            <span className="text-emerald-400">({formatPct(simResult.fund.profit_pct)})</span>
                          </div>
                        </div>
                        <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
                          <div className="h-full bg-blue-500 rounded-full" style={{ width: "100%" }}></div>
                        </div>
                      </div>

                      {/* Benchmarks Bars */}
                      {simResult.benchmarks.map((b: any, index: number) => {
                        const isHigher = b.value > simResult.fund.end_value;
                        const pctOfFund = Math.min(100, (b.value / simResult.fund.end_value) * 100);
                        return (
                          <div key={b.name} className="space-y-1">
                            <div className="flex justify-between text-xs font-semibold text-zinc-400">
                              <span>{b.name}</span>
                              <div className="flex gap-2">
                                <span className={isHigher ? "text-zinc-200" : "text-zinc-400"}>
                                  {formatTL(b.value)}
                                </span>
                                <span className={pctColor(b.profit_pct)}>
                                  ({formatPct(b.profit_pct)})
                                </span>
                              </div>
                            </div>
                            <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
                              <div
                                className="h-full rounded-full transition-all duration-500"
                                style={{
                                  width: `${pctOfFund}%`,
                                  backgroundColor: index === 0 ? "#eab308" : index === 1 ? "#ec4899" : "#64748b",
                                }}
                              ></div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )
            ) : (
              <div className="glass p-16 text-center space-y-4">
                <BarChart3 className="h-12 w-12 text-zinc-600 mx-auto animate-pulse" />
                <h3 className="text-sm font-bold text-zinc-400">Yatırım Verisi Simüle Edilmeye Hazır</h3>
                <p className="text-xs text-zinc-500 max-w-sm mx-auto leading-relaxed font-normal">
                  Soldaki paneli kullanarak fon, tutar ve başlangıç tarihi seçin. Sistem seans veritabanını tarayarak kıyaslamaları getirecektir.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB 3: RISK TESTI VE ONERILER ───────────────────────────── */}
      {activeTab === "risk" && (
        <div className="max-w-3xl mx-auto glass p-6 md:p-8 space-y-6">
          <div className="flex items-center gap-2 border-b border-white/6 pb-4">
            <Sparkles className="h-5 w-5 text-yellow-400" />
            <div>
              <h2 className="text-sm font-bold text-white">Akıllı Risk Profil Testi</h2>
              <p className="text-[11px] text-zinc-500">5 kısa soru ile kendinize en uygun yatırım fonu grubunu keşfedin.</p>
            </div>
          </div>

          {/* Intro Screen */}
          {quizStep === 0 && (
            <div className="text-center py-8 space-y-6">
              <div className="relative inline-block">
                <div className="absolute inset-0 rounded-full bg-blue-500/25 blur-xl animate-pulse"></div>
                <HelpCircle className="relative h-14 w-14 text-blue-500 mx-auto" />
              </div>
              <div className="space-y-2">
                <h3 className="text-sm font-extrabold text-white">Yatırımcı Profilinizi Tanıyın</h3>
                <p className="text-xs text-zinc-400 max-w-md mx-auto leading-relaxed">
                  TEFAS piyasasında 1 riskli (en dengeli) ile 7 riskli (en volatil) arasında yüzlerce fon bulunur. Bu test risk töleransınızı ve vadenizi ölçerek size en verimli 3 fonu önerecektir.
                </p>
              </div>
              <button
                onClick={() => setQuizStep(1)}
                className="rounded-xl bg-blue-500 px-6 py-2.5 text-xs font-bold text-white transition-all hover:bg-blue-600 cursor-pointer"
              >
                Risk Testine Başla
              </button>
            </div>
          )}

          {/* Question Screen */}
          {quizStep >= 1 && quizStep <= QUIZ_QUESTIONS.length && (
            <div className="space-y-6">
              {/* Progress Bar */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                  <span>Soru {quizStep} / {QUIZ_QUESTIONS.length}</span>
                  <span>{Math.round(((quizStep - 1) / QUIZ_QUESTIONS.length) * 100)}% Tamamlandı</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
                  <div
                    className="h-full bg-blue-500 transition-all duration-300"
                    style={{ width: `${((quizStep) / QUIZ_QUESTIONS.length) * 100}%` }}
                  ></div>
                </div>
              </div>

              {/* Question Text */}
              <h3 className="text-sm font-extrabold text-zinc-200">
                {QUIZ_QUESTIONS[quizStep - 1].question}
              </h3>

              {/* Options */}
              <div className="space-y-3">
                {QUIZ_QUESTIONS[quizStep - 1].options.map((opt, i) => (
                  <button
                    key={i}
                    onClick={() => handleQuizAnswer(opt.score)}
                    className="w-full flex items-center justify-between rounded-xl border border-white/8 bg-white/3 p-4 text-left text-xs font-medium text-zinc-300 hover:border-blue-500/40 hover:bg-blue-500/5 hover:text-white transition-all cursor-pointer group"
                  >
                    <span>{opt.text}</span>
                    <ChevronRight className="h-4 w-4 text-zinc-500 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Results Screen */}
          {quizStep === 6 && (
            <div className="space-y-6">
              {/* Determined Profile Result Badge */}
              <div className="rounded-2xl border border-blue-500/30 bg-blue-500/5 p-6 text-center space-y-3 relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-r from-blue-500/5 to-emerald-500/5 pointer-events-none"></div>
                <Sparkles className="h-8 w-8 text-yellow-400 mx-auto animate-pulse" />
                <span className="text-[10px] font-bold text-blue-400 uppercase tracking-wider block">Yatırımcı Profiliniz</span>
                <h3 className="text-lg font-extrabold text-white">{quizScores.reduce((a, b) => a + b, 0) <= 9 ? "Muhafazakar / Temkinli" : quizScores.reduce((a, b) => a + b, 0) <= 18 ? "Dengeli / Moderate" : "Agresif / Büyüme Odaklı"}</h3>
                <p className="text-xs text-zinc-400 max-w-md mx-auto leading-relaxed font-normal">
                  Yapılan analiz sonucunda risk puanınız: <span className="font-bold text-white">{quizScores.reduce((a, b) => a + b, 0)} / 25</span>. Bu puan sizin kısa vadeli kayıplara dayanıklı olduğunuzu ancak büyüme potansiyelini kaçırmak istemediğinizi göstermektedir.
                </p>
              </div>

              {/* Recommended Funds Listing */}
              <div className="space-y-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                  Profilinizle Uyumlu 3 Fon Önerisi
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {recommendedFunds.map((rec) => (
                    <div
                      key={rec.code}
                      className="rounded-xl border border-white/6 bg-white/2 p-4 flex flex-col justify-between space-y-3 hover:border-white/10 transition-all"
                    >
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="rounded-lg bg-blue-500/10 px-2 py-0.5 font-mono text-xs font-bold text-blue-400">
                            {rec.code}
                          </span>
                          <span className="text-[9px] text-zinc-500 font-semibold">{rec.cat}</span>
                        </div>
                        <h5 className="text-[11px] font-extrabold text-zinc-200 line-clamp-2 leading-relaxed">{rec.name}</h5>
                      </div>
                      <div className="border-t border-white/4 pt-2.5 mt-auto flex items-center justify-between">
                        <span className="text-[10px] text-zinc-500">{rec.yield}</span>
                        <Link
                          href={`/fon/${rec.code}`}
                          className="text-[10px] font-bold text-blue-400 hover:text-white transition-colors flex items-center gap-0.5"
                        >
                          Detaylar
                          <ChevronRight className="h-3.5 w-3.5" />
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Reset Button */}
              <div className="text-center pt-2">
                <button
                  onClick={handleResetQuiz}
                  className="rounded-xl border border-white/8 bg-white/3 px-4 py-2 text-xs font-bold text-zinc-400 hover:bg-white/5 hover:text-white transition-all cursor-pointer flex items-center gap-1.5 mx-auto"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Testi Tekrarla
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 4: ALARM YONETIMI ──────────────────────────────────── */}
      {activeTab === "alerts" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Add Alarm Form */}
          <div className="glass p-6 space-y-4 h-fit">
            <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
              <Bell className="h-4.5 w-4.5 text-blue-400" />
              Yeni Fiyat Alarmı Kur
            </h3>
            <p className="text-[11px] text-zinc-400 leading-relaxed font-normal">
              Bir fon günlük bazda belirlediğiniz yüzde değişim eşiğini (artış veya azalış) aştığında anında tetiklenecek bildirimler kurun.
            </p>

            <form onSubmit={handleAddAlert} className="space-y-4 text-xs">
              {/* Autocomplete Select */}
              <div className="space-y-1.5 relative">
                <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Fon Seçimi</label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
                  <input
                    type="text"
                    value={alertSearchQuery}
                    onChange={(e) => {
                      setAlertSearchQuery(e.target.value);
                      setAlertFundCode(e.target.value.toUpperCase());
                      setShowAlertDropdown(true);
                    }}
                    onFocus={() => setShowAlertDropdown(true)}
                    placeholder="Fon kodu yazın (örn: HCV)..."
                    className="w-full rounded-xl border border-white/8 bg-white/3 py-2.5 pl-9 pr-4 text-white outline-none focus:border-blue-500"
                    required
                  />
                </div>

                {showAlertDropdown && alertSearchQuery.trim().length > 0 && (
                  <div className="absolute left-0 right-0 top-full mt-1.5 z-50 rounded-xl border border-white/10 bg-[#0d1426] p-1.5 shadow-2xl max-h-[160px] overflow-y-auto">
                    {alertSearchResults?.funds && alertSearchResults.funds.length > 0 ? (
                      alertSearchResults.funds.map((f) => (
                        <button
                          key={f.code}
                          type="button"
                          onClick={() => {
                            setAlertFundCode(f.code);
                            setAlertSearchQuery(f.code);
                            setShowAlertDropdown(false);
                          }}
                          className="flex w-full items-center justify-between rounded-lg p-2 text-left text-[11px] transition-colors hover:bg-white/5 cursor-pointer"
                        >
                          <div>
                            <span className="font-mono font-bold text-blue-400 mr-2">{f.code}</span>
                            <span className="text-zinc-300 font-medium line-clamp-1">{f.name}</span>
                          </div>
                        </button>
                      ))
                    ) : (
                      <div className="p-2 text-zinc-500">Sonuç bulunamadı</div>
                    )}
                  </div>
                )}
              </div>

              {/* Threshold */}
              <div className="space-y-1.5">
                <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">
                  Değişim Eşiği (%)
                </label>
                <input
                  type="number"
                  step="any"
                  value={alertThreshold}
                  onChange={(e) => setAlertThreshold(e.target.value)}
                  placeholder="örn: +2.5 veya -1.5"
                  className="w-full rounded-xl border border-white/8 bg-white/3 py-2.5 px-3.5 text-white outline-none focus:border-blue-500"
                  required
                />
                <span className="text-[9px] text-zinc-500 block leading-relaxed font-normal">
                  Pozitif değerler fiyat artışlarını (+2.5%), negatif değerler ise fiyat düşüşlerini (-1.5%) izler.
                </span>
              </div>

              <button
                type="submit"
                disabled={isAlertSubmitting}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-blue-500 py-3 font-bold text-white transition-all hover:bg-blue-600 disabled:opacity-50 cursor-pointer"
              >
                <Plus className="h-4 w-4" />
                {isAlertSubmitting ? "Kaydediliyor..." : "Alarm Kuralı Ekle"}
              </button>
            </form>
          </div>

          {/* Active Rules List */}
          <div className="lg:col-span-2 glass p-6 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-emerald-400" />
              Aktif Alarm Kurallarım
            </h3>

            {isAlertsLoading ? (
              <Skeleton count={4} />
            ) : alertsData?.alerts && alertsData.alerts.length > 0 ? (
              <div className="space-y-2 max-h-[450px] overflow-y-auto pr-1">
                {alertsData.alerts.map((al: any) => (
                  <div
                    key={al.id}
                    className="flex items-center justify-between rounded-xl border border-white/6 bg-white/2 p-4 transition-all hover:bg-white/4"
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono font-bold text-blue-400">{al.code}</span>
                        <span className="text-xs text-zinc-400 font-semibold">{al.name || "Bilinmeyen Fon"}</span>
                      </div>
                      <p className="text-[11px] text-zinc-400 leading-normal font-normal">
                        Günlük seans kapanış değişimi{" "}
                        <span className={`font-extrabold ${al.threshold > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {al.threshold > 0 ? `>= +${al.threshold}%` : `<= ${al.threshold}%`}
                        </span>{" "}
                        olduğunda uyar.
                      </p>
                    </div>
                    <button
                      onClick={() => handleDeleteAlert(al.id)}
                      className="rounded-lg p-2 text-zinc-500 hover:bg-rose-500/10 hover:text-rose-400 transition-all cursor-pointer"
                    >
                      <Trash2 className="h-4.5 w-4.5" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-16 text-zinc-500 text-xs italic space-y-1 leading-relaxed">
                <Bell className="h-8 w-8 mx-auto text-zinc-700 mb-1 animate-pulse" />
                Aktif olarak tanımlanmış fiyat değişim alarmınız bulunmuyor.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Transaction Manager Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass w-full max-w-md p-6 space-y-4 animate-in fade-in zoom-in duration-200">
            <div className="flex items-center justify-between border-b border-white/8 pb-3">
              <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
                <Plus className="h-4.5 w-4.5 text-blue-500" />
                Yeni İşlem Ekle
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-zinc-400 hover:text-white transition-colors cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleAddTransaction} className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">İşlem Tipi</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setTxType("BUY")}
                    className={`rounded-lg py-2 font-bold transition-all cursor-pointer text-center border ${
                      txType === "BUY"
                        ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-400"
                        : "bg-white/3 border-white/8 text-zinc-400 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    Alış
                  </button>
                  <button
                    type="button"
                    onClick={() => setTxType("SELL")}
                    className={`rounded-lg py-2 font-bold transition-all cursor-pointer text-center border ${
                      txType === "SELL"
                        ? "bg-rose-500/10 border-rose-500/40 text-rose-400"
                        : "bg-white/3 border-white/8 text-zinc-400 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    Satış
                  </button>
                </div>
              </div>

              <div className="space-y-1.5 relative">
                <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Fon Seçimi</label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setFundCode(e.target.value.toUpperCase());
                      setShowDropdown(true);
                    }}
                    onFocus={() => setShowDropdown(true)}
                    placeholder="Fon kodunu yazın (örn: HCV)..."
                    className="w-full rounded-xl border border-white/8 bg-white/3 py-2 pl-9 pr-4 text-white outline-none focus:border-blue-500"
                    required
                  />
                </div>

                {showDropdown && searchQuery.trim().length > 0 && (
                  <div className="absolute left-0 right-0 top-full mt-1.5 z-50 rounded-xl border border-white/10 bg-[#0d1426] p-1.5 shadow-2xl max-h-[160px] overflow-y-auto">
                    {searchResults?.funds && searchResults.funds.length > 0 ? (
                      searchResults.funds.map((f) => (
                        <button
                          key={f.code}
                          type="button"
                          onClick={() => {
                            setFundCode(f.code);
                            setSearchQuery(f.code);
                            setShowDropdown(false);
                          }}
                          className="flex w-full items-center justify-between rounded-lg p-2 text-left text-[11px] transition-colors hover:bg-white/5 cursor-pointer"
                        >
                          <div>
                            <span className="font-mono font-bold text-blue-400 mr-2">{f.code}</span>
                            <span className="text-zinc-300 font-medium line-clamp-1">{f.name}</span>
                          </div>
                        </button>
                      ))
                    ) : (
                      <div className="p-2 text-zinc-500">Sonuç bulunamadı</div>
                    )}
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">İşlem Tarihi</label>
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="w-full rounded-xl border border-white/8 bg-white/3 py-2 px-3 text-white outline-none focus:border-blue-500"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Adet (Birim)</label>
                  <input
                    type="number"
                    step="any"
                    value={units}
                    onChange={(e) => setUnits(e.target.value)}
                    placeholder="Adet girin..."
                    className="w-full rounded-xl border border-white/8 bg-white/3 py-2 px-3 text-white outline-none focus:border-blue-500"
                    required
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-400">Birim Fiyat (TL)</label>
                  <input
                    type="number"
                    step="any"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    placeholder="Birim Fiyat..."
                    className="w-full rounded-xl border border-white/8 bg-white/3 py-2 px-3 text-white outline-none focus:border-blue-500"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full rounded-xl bg-blue-500 py-2.5 font-bold text-white transition-all hover:bg-blue-600 cursor-pointer"
              >
                İşlem Kaydet
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Yapay Zeka Fon Analizi Modal */}
      {isAiFundModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="glass w-full max-w-2xl p-6 space-y-4 animate-in zoom-in duration-200 max-h-[90vh] flex flex-col relative overflow-hidden">
            {/* Glowing background light */}
            <div className="absolute -top-10 -right-10 w-40 h-40 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />
            
            <div className="flex items-center justify-between border-b border-white/8 pb-3 shrink-0 relative z-10">
              <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
                <Sparkles className="h-4.5 w-4.5 text-purple-400 animate-pulse" />
                <span>{selectedAiFundCode} Fon Yapay Zeka Analizi</span>
                <span className="text-[9px] uppercase tracking-wider font-extrabold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  GEMINI AI
                </span>
              </h3>
              <button
                onClick={() => {
                  setIsAiFundModalOpen(false);
                  setAiFundResult(null);
                  setSelectedAiFundCode(null);
                }}
                className="text-zinc-400 hover:text-white transition-colors cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar pr-1.5 space-y-4 relative z-10 py-2">
              {isAiFundLoading ? (
                <div className="py-16 flex flex-col items-center justify-center space-y-4 animate-pulse">
                  <div className="relative">
                    <div className="w-10 h-10 rounded-full border-2 border-purple-500/20 border-t-purple-400 animate-spin" />
                    <Sparkles className="h-4 w-4 text-purple-400 absolute inset-0 m-auto animate-bounce" />
                  </div>
                  <div className="space-y-1 text-center">
                    <p className="text-xs font-bold text-purple-300">Yapay Zeka Analiz Raporu Hazırlanıyor...</p>
                    <p className="text-[10px] text-zinc-500 font-medium">Bu işlem ortalama 3-5 saniye sürmektedir.</p>
                  </div>
                </div>
              ) : aiFundResult ? (
                <div className="text-zinc-200 text-xs leading-relaxed space-y-4.5 font-medium whitespace-pre-line selection:bg-purple-500/30">
                  {aiFundResult}
                </div>
              ) : (
                <div className="text-center py-12 text-zinc-500 text-xs italic">
                  Analiz verisi bulunamadı.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
