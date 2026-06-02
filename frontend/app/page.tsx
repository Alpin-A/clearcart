"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const EXAMPLE_QUERIES = [
  "noise cancelling headphones under $200 for studying",
  "wireless earbuds for running under $50",
  "wired headphones for studio recording",
  "kids headphones with volume limit under $30",
];

export default function HomePage() {
  const [query, setQuery] = useState("");
  const router = useRouter();

  function navigate(q: string) {
    router.push(`/search?q=${encodeURIComponent(q)}`);
  }

  function handleSubmit() {
    if (query.trim()) navigate(query.trim());
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleSubmit();
  }

  function handleChip(q: string) {
    setQuery(q);
    navigate(q);
  }

  return (
    <div className="min-h-screen bg-stone-50 flex flex-col items-center justify-center px-6">
      <div className="fade-in w-full max-w-2xl mx-auto flex flex-col gap-8">

        <span className="font-mono text-sm tracking-widest text-stone-400 uppercase">
          ClearCart
        </span>

        <div className="flex flex-col gap-1">
          <h1 className="text-4xl md:text-5xl font-bold text-stone-900 leading-tight">
            Find products by fit,<br />not by sponsorship.
          </h1>
          <p className="text-stone-500 text-sm max-w-lg mt-3 leading-relaxed">
            Hybrid search and ranking over Amazon review data.
            Results ranked by evidence, price fit, and review signals —
            not by ads.
          </p>
        </div>

        <div className="flex">
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="noise cancelling headphones under $200 for studying..."
            className="flex-1 h-12 px-4 bg-white border border-stone-300 border-r-0 text-stone-900 text-sm placeholder:text-stone-400 focus:outline-none focus:border-stone-900 transition-colors"
          />
          <button
            onClick={handleSubmit}
            className="h-12 bg-stone-900 text-white px-4 text-sm font-medium hover:bg-stone-800 transition-colors shrink-0"
          >
            Search
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {EXAMPLE_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => handleChip(q)}
              className="text-xs border border-stone-200 text-stone-500 px-3 py-1 rounded-sm hover:border-stone-400 hover:text-stone-700 transition-colors cursor-pointer"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      <footer className="absolute bottom-6 w-full text-center">
        <span className="text-xs text-stone-400">
          Built on Amazon Reviews 2023 · McAuley Lab · 5K products · 66K reviews
        </span>
      </footer>
    </div>
  );
}
