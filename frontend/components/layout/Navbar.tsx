"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BarChart3,
  Search,
  TrendingUp,
  Droplets,
  Briefcase,
  AlertTriangle,
  MessageCircle,
  Sun,
  Moon,
  ArrowRightLeft,
  Menu,
  X,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/bugun", label: "Bugün", icon: BarChart3 },
  { href: "/fonlar", label: "Fon Tarayıcı", icon: Search },
  { href: "/karsilastir", label: "Karşılaştırma", icon: ArrowRightLeft },
  { href: "/portfoy", label: "Portföyüm", icon: Briefcase },
  { href: "/nakit-akisi", label: "Nakit Akışı", icon: Droplets },
  { href: "/yoneticiler", label: "Yöneticiler", icon: Briefcase },
  { href: "/anomaliler", label: "Anomaliler", icon: AlertTriangle },
  { href: "/sosyal", label: "Sosyal", icon: MessageCircle },
];

export default function Navbar() {
  const pathname = usePathname();
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const isLight = document.documentElement.classList.contains("light");
    setTheme(isLight ? "light" : "dark");
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    if (nextTheme === "light") {
      document.documentElement.classList.add("light");
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    } else {
      document.documentElement.classList.add("dark");
      document.documentElement.classList.remove("light");
      localStorage.setItem("theme", "dark");
    }
  };

  const navLinkClass = (href: string) => {
    const active = pathname === href || pathname.startsWith(href + "/");
    return `flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
      active
        ? "bg-blue-500/15 text-blue-400 shadow-[0_0_12px_rgba(59,130,246,0.15)]"
        : "text-zinc-400 hover:bg-white/5 hover:text-white"
    }`;
  };

  return (
    <header className="sticky top-0 z-50 border-b border-white/6 bg-[#050a15]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between px-4 md:px-6">
        <Link href="/bugun" className="flex items-center gap-2.5">
          <TrendingUp className="h-6 w-6 text-emerald-400" />
          <span className="bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-lg font-extrabold tracking-tight text-transparent">
            TEFAS Platform
          </span>
          <span className="ml-1.5 inline-flex h-2 w-2 rounded-full bg-emerald-500 live-dot" />
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} className={navLinkClass(item.href)}>
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2 md:gap-4">
          <button
            onClick={toggleTheme}
            className="rounded-lg p-2 text-zinc-400 hover:bg-white/5 hover:text-white transition-all cursor-pointer"
            aria-label="Temayı Değiştir"
          >
            {theme === "dark" ? (
              <Sun className="h-5 w-5 text-amber-400" />
            ) : (
              <Moon className="h-5 w-5 text-indigo-500" />
            )}
          </button>

          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="rounded-lg p-2 text-zinc-400 hover:bg-white/5 hover:text-white transition-all cursor-pointer md:hidden"
            aria-label="Menüyü aç"
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="hidden text-xs text-zinc-500 lg:block">
            Powered by FastAPI + Next.js
          </div>
        </div>
      </div>

      {mobileOpen && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm md:hidden"
            aria-label="Menüyü kapat"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="fixed inset-y-0 right-0 z-[70] flex w-[min(100vw-3rem,320px)] flex-col border-l border-white/10 bg-[#050a15]/98 backdrop-blur-xl md:hidden">
            <div className="flex items-center justify-between border-b border-white/8 px-4 py-4">
              <span className="text-sm font-bold text-white">Menü</span>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="rounded-lg p-2 text-zinc-400 hover:bg-white/5 hover:text-white cursor-pointer"
                aria-label="Menüyü kapat"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={navLinkClass(item.href)}
                    onClick={() => setMobileOpen(false)}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </aside>
        </>
      )}
    </header>
  );
}
