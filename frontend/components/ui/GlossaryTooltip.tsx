"use client";

import React, { useState } from "react";
import { HelpCircle } from "lucide-react";

interface GlossaryTooltipProps {
  term: string;
  definition: string;
  children?: React.ReactNode;
}

export default function GlossaryTooltip({ term, definition, children }: GlossaryTooltipProps) {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <span
      className="relative inline-flex items-center gap-1 cursor-help group"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
    >
      <span className="inline-flex items-center gap-0.5 border-b border-dotted border-blue-400/40 hover:text-blue-400 hover:border-blue-400 transition-colors">
        {children || term}
      </span>
      <HelpCircle className="h-3.5 w-3.5 text-zinc-500 group-hover:text-blue-400 transition-colors" />

      {isVisible && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2.5 z-50 w-64 p-3 rounded-lg glass border border-blue-500/30 text-xs shadow-2xl animate-in fade-in slide-in-from-bottom-1 duration-150 text-left">
          <span className="block font-extrabold text-blue-400 mb-1 tracking-wide">{term}</span>
          <span className="block text-zinc-300 leading-relaxed font-normal whitespace-normal">{definition}</span>
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-white/10 dark:border-t-black/40"></span>
        </span>
      )}
    </span>
  );
}
