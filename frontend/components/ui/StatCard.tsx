"use client";

import { ReactNode } from "react";

interface Props {
  label: string;
  value: string;
  sub?: string;
  icon?: ReactNode;
  color?: "blue" | "green" | "red" | "orange";
}

const COLORS = {
  blue: "from-blue-500 to-blue-400",
  green: "from-emerald-500 to-emerald-400",
  red: "from-rose-500 to-rose-400",
  orange: "from-amber-500 to-amber-400",
};

export default function StatCard({ label, value, sub, icon, color = "blue" }: Props) {
  return (
    <div className="glass relative overflow-hidden p-5 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:shadow-black/20">
      {/* Top accent line */}
      <div className={`absolute left-0 right-0 top-0 h-[3px] bg-gradient-to-r ${COLORS[color]}`} />

      <div className="flex items-start justify-between">
        <div>
          <div className="mb-2 text-[0.7rem] font-bold uppercase tracking-wider text-zinc-400">
            {label}
          </div>
          <div className="animate-count text-2xl font-extrabold tracking-tight">{value}</div>
          {sub && (
            <div className="mt-1.5 text-xs text-zinc-400">{sub}</div>
          )}
        </div>
        {icon && (
          <div className="rounded-xl bg-white/5 p-2.5 text-zinc-400">{icon}</div>
        )}
      </div>
    </div>
  );
}
