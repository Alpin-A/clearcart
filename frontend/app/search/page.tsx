"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { searchProducts, SearchResult } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

function parseBudget(query: string): string | null {
  const m = query.match(/under\s+\$?(\d+)/i);
  return m ? `$${m[1]}` : null;
}

function fitScoreColor(score: number) {
  if (score >= 70) return "text-green-700";
  if (score >= 50) return "text-yellow-700";
  return "text-red-700";
}

function SkeletonCard() {
  return (
    <div className="bg-white border border-stone-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <Skeleton className="h-4 w-8 bg-stone-100" />
        <Skeleton className="h-4 w-20 bg-stone-100" />
      </div>
      <Skeleton className="h-5 w-3/4 bg-stone-100 mb-2" />
      <Skeleton className="h-3 w-1/2 bg-stone-100 mb-3" />
      <Skeleton className="h-3 w-full bg-stone-100 mb-1" />
      <Skeleton className="h-3 w-5/6 bg-stone-100 mb-3" />
      <Skeleton className="h-1 w-full bg-stone-100" />
    </div>
  );
}

function ResultCard({
  result,
  rank,
  isLast,
}: {
  result: SearchResult;
  rank: number;
  isLast: boolean;
}) {
  const router = useRouter();
  const scoreColor = fitScoreColor(result.fit_score);

  return (
    <div
      onClick={() => router.push(`/product/${result.asin}`)}
      className={`bg-white border-x border-t border-stone-200 p-4 hover:border-stone-400 transition-colors cursor-pointer ${
        isLast ? "border-b border-stone-200" : "border-b border-stone-100"
      }`}
    >
      {/* rank + score */}
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-sm text-stone-400">#{rank}</span>
        <span className={`font-mono text-sm ${scoreColor}`}>
          {result.fit_score.toFixed(1)} / 100
        </span>
      </div>

      {/* title */}
      <Link
        href={`/product/${result.asin}`}
        onClick={(e) => e.stopPropagation()}
        className="font-semibold text-base text-stone-900 hover:text-orange-600 transition-colors line-clamp-2 block mb-1"
      >
        {result.title}
      </Link>

      {/* metadata */}
      <div className="flex flex-wrap items-center gap-x-2 text-xs text-stone-500 font-mono mb-2">
        {result.brand && <span>{result.brand}</span>}
        {result.brand && <span>·</span>}
        <span>
          {result.has_price && result.price != null
            ? `$${result.price.toFixed(2)}`
            : "Price unknown"}
        </span>
        {result.avg_rating != null && (
          <>
            <span>·</span>
            <span>★ {result.avg_rating.toFixed(1)}</span>
          </>
        )}
        <span>·</span>
        <span>{result.review_count.toLocaleString()} reviews</span>
        {result.over_budget && (
          <span className="text-red-500 font-sans">over budget</span>
        )}
      </div>

      {/* matched preferences badges */}
      {result.matched_preferences.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {result.matched_preferences.slice(0, 3).map((pref) => (
            <span
              key={pref}
              className="text-xs border border-stone-200 text-stone-500 px-2 py-0.5 rounded-sm"
            >
              {pref}
            </span>
          ))}
        </div>
      )}

      {/* pros */}
      {result.top_pros.length > 0 && (
        <div className="flex items-start gap-2 mb-1">
          <span className="text-xs text-stone-400 shrink-0 w-6">Pros</span>
          <span className="text-xs text-stone-600">
            ✓ {result.top_pros.slice(0, 3).join(", ")}
          </span>
        </div>
      )}

      {/* cons */}
      {result.top_cons.length > 0 && (
        <div className="flex items-start gap-2 mb-2">
          <span className="text-xs text-stone-400 shrink-0 w-6">Cons</span>
          <span className="text-xs text-stone-600">
            ✗ {result.top_cons.slice(0, 3).join(", ")}
          </span>
        </div>
      )}

      {/* evidence bar */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-stone-400 shrink-0">Evidence</span>
        <div className="flex-1 h-1 bg-stone-100">
          <div
            className="h-1 bg-orange-500"
            style={{
              width: `${Math.min(result.evidence_score * 100, 100).toFixed(1)}%`,
            }}
          />
        </div>
      </div>
    </div>
  );
}

function QuerySidebar({
  query,
  results,
}: {
  query: string;
  results: SearchResult[];
}) {
  const budget = parseBudget(query);
  const preferences = results[0]?.matched_preferences ?? [];

  return (
    <div className="bg-white border border-stone-200 p-4 text-sm">
      <p className="text-xs font-mono text-stone-400 uppercase tracking-widest mb-3">
        Query Analysis
      </p>
      <div className="flex flex-col gap-2.5">
        <div className="flex justify-between items-start gap-2">
          <span className="text-xs text-stone-400">Budget detected</span>
          <span className="font-mono text-xs text-stone-900">
            {budget ?? "Not specified"}
          </span>
        </div>
        {preferences.length > 0 && (
          <div className="flex flex-col gap-1">
            <span className="text-xs text-stone-400 mb-0.5">
              Preferences matched
            </span>
            {preferences.map((p) => (
              <span key={p} className="font-mono text-xs text-stone-600">
                — {p}
              </span>
            ))}
          </div>
        )}
        <div className="flex justify-between items-center border-t border-stone-100 pt-2">
          <span className="text-xs text-stone-400">Result count</span>
          <span className="font-mono text-xs text-stone-900">
            {results.length} results
          </span>
        </div>
      </div>
    </div>
  );
}

function SearchPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const q = searchParams.get("q") ?? "";
  const [inputValue, setInputValue] = useState(q);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setInputValue(q);
    if (!q) return;
    setLoading(true);
    setError(null);
    setResults(null);
    searchProducts(q)
      .then(setResults)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [q]);

  function handleSearch() {
    const trimmed = inputValue.trim();
    if (trimmed) router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleSearch();
  }

  return (
    <div className="min-h-screen bg-stone-50">
      {/* top bar */}
      <div className="bg-stone-50 border-b border-stone-200">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-4">
          <Link
            href="/"
            className="font-mono text-sm tracking-widest text-stone-400 uppercase shrink-0 hover:text-stone-600 transition-colors"
          >
            CLEARCART
          </Link>
          <div className="flex flex-1">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search products..."
              className="flex-1 h-10 px-4 bg-white border border-stone-300 border-r-0 text-stone-900 text-sm placeholder:text-stone-400 focus:outline-none focus:border-stone-900 transition-colors"
            />
            <button
              onClick={handleSearch}
              className="h-10 bg-stone-900 text-white px-4 text-sm font-medium hover:bg-stone-800 transition-colors shrink-0"
            >
              Search
            </button>
          </div>
        </div>
      </div>

      {/* content */}
      <div className="max-w-5xl mx-auto px-6 py-6">
        {loading && (
          <div className="flex flex-col md:flex-row gap-6 items-start">
            <div className="flex-[2] min-w-0 w-full">
              {Array.from({ length: 5 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
            <div className="flex-1 w-full">
              <div className="bg-white border border-stone-200 p-4">
                <Skeleton className="h-3 w-24 bg-stone-100 mb-4" />
                <Skeleton className="h-4 w-32 bg-stone-100 mb-2" />
                <Skeleton className="h-4 w-28 bg-stone-100 mb-2" />
                <Skeleton className="h-4 w-20 bg-stone-100" />
              </div>
            </div>
          </div>
        )}

        {error && <p className="text-sm text-red-500">{error}</p>}

        {results !== null && results.length === 0 && (
          <p className="text-sm text-stone-500 text-center mt-12">
            No results for this query.
          </p>
        )}

        {results !== null && results.length > 0 && (
          <div className="flex flex-col md:flex-row gap-6 items-start">
            <div className="flex-[2] min-w-0 w-full">
              {results.map((r, i) => (
                <ResultCard
                  key={r.asin}
                  result={r}
                  rank={i + 1}
                  isLast={i === results.length - 1}
                />
              ))}
            </div>
            <div className="flex-1 w-full md:sticky md:top-6">
              <QuerySidebar query={q} results={results} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SearchPageWrapper() {
  return (
    <Suspense>
      <SearchPage />
    </Suspense>
  );
}
