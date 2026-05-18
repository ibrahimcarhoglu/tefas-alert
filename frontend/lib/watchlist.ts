"use client";

import { useState, useEffect } from "react";

export function useWatchlist() {
  const [watchlist, setWatchlist] = useState<string[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem("tefas_watchlist");
    if (stored) {
      try {
        setWatchlist(JSON.parse(stored));
      } catch (e) {
        console.error(e);
      }
    }
  }, []);

  const isFavorite = (code: string) => watchlist.includes(code.toUpperCase());

  const toggleFavorite = (code: string) => {
    const upper = code.toUpperCase();
    let next: string[];
    if (watchlist.includes(upper)) {
      next = watchlist.filter((c) => c !== upper);
    } else {
      next = [...watchlist, upper];
    }
    setWatchlist(next);
    localStorage.setItem("tefas_watchlist", JSON.stringify(next));
  };

  return { watchlist, isFavorite, toggleFavorite };
}
