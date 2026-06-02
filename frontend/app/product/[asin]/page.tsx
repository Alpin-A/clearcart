"use client";

import { useState, useEffect, Suspense } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getProduct, ProductDetail } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

function fitScoreColor(score: number) {
  if (score >= 70) return "text-green-700";
  if (score >= 50) return "text-yellow-700";
  return "text-red-700";
}

function TopBar() {
  const router = useRouter();
  const [inputValue, setInputValue] = useState("");

  function handleSearch() {
    const trimmed = inputValue.trim();
    if (trimmed) router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleSearch();
  }

  return (
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
  );
}

function SkeletonPage() {
  return (
    <div className="flex flex-col md:flex-row gap-6 items-start">
      <div className="flex-[2] min-w-0 w-full flex flex-col gap-4">
        <Skeleton className="h-3 w-24 bg-stone-100" />
        <Skeleton className="h-3 w-32 bg-stone-100" />
        <Skeleton className="h-8 w-3/4 bg-stone-100" />
        <Skeleton className="h-3 w-48 bg-stone-100" />
        <Skeleton className="h-12 w-24 bg-stone-100" />
        <div className="flex flex-col gap-2 pt-4 border-t border-stone-100">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="h-3 w-36 bg-stone-100 shrink-0" />
              <Skeleton className="flex-1 h-1 bg-stone-100" />
              <Skeleton className="h-3 w-8 bg-stone-100" />
            </div>
          ))}
        </div>
      </div>
      <div className="flex-1 w-full">
        <div className="bg-white border border-stone-200 p-4 flex flex-col gap-3">
          <Skeleton className="h-3 w-28 bg-stone-100" />
          <Skeleton className="h-8 w-16 bg-stone-100" />
          <Skeleton className="h-2 w-full bg-stone-100" />
          <div className="grid grid-cols-2 gap-3 pt-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i}>
                <Skeleton className="h-3 w-16 bg-stone-100 mb-1" />
                <Skeleton className="h-4 w-12 bg-stone-100" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function EvidencePanel({ product }: { product: ProductDetail }) {
  return (
    <div className="bg-white border border-stone-200 p-4 sticky top-6">
      <p className="text-xs font-mono text-stone-400 uppercase tracking-widest mb-3">
        Review Evidence
      </p>

      {/* evidence score + bar */}
      <div className="mb-4">
        <div className="flex items-baseline gap-1.5 mb-1.5">
          <span className="font-mono text-2xl font-bold text-stone-900">
            {product.evidence_score.toFixed(2)}
          </span>
          <span className="text-xs text-stone-400">/ 1.00 evidence score</span>
        </div>
        <div className="w-full h-2 bg-stone-100">
          <div
            className="h-2 bg-orange-500"
            style={{ width: `${Math.min(product.evidence_score * 100, 100).toFixed(1)}%` }}
          />
        </div>
      </div>

      {/* 2x2 stats grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 mb-4 pb-4 border-b border-stone-100">
        <div>
          <p className="text-xs text-stone-400">Reviews</p>
          <p className="font-mono text-sm text-stone-900">
            {product.review_count.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-stone-400">Avg rating</p>
          <p className="font-mono text-sm text-stone-900">
            {product.avg_rating != null ? `★ ${product.avg_rating.toFixed(1)}` : "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-stone-400">Negative rate</p>
          <p className="font-mono text-sm text-stone-900">
            {(product.complaint_rate * 100).toFixed(0)}%
          </p>
        </div>
        <div>
          <p className="text-xs text-stone-400">Evidence</p>
          <p className="font-mono text-sm text-stone-900">
            {product.evidence_score.toFixed(2)}
          </p>
        </div>
      </div>

      {/* pros */}
      <div className="mb-4">
        <p className="text-xs text-stone-400 uppercase tracking-widest mb-1.5">Common Pros</p>
        {product.top_pros.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {product.top_pros.map((pro) => (
              <li key={pro} className="text-sm text-stone-600">
                ✓ {pro}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-stone-400 italic">Not enough review data</p>
        )}
      </div>

      {/* cons + warning */}
      <div className="mb-4">
        <p className="text-xs text-stone-400 uppercase tracking-widest mb-1.5">Common Cons</p>
        {product.top_cons.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {product.top_cons.map((con) => (
              <li key={con} className="text-sm text-stone-600">
                ✗ {con}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-stone-400 italic">Not enough review data</p>
        )}
        {product.complaint_rate > 0.25 && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-xs p-2 mt-2">
            ⚠ {Math.round(product.complaint_rate * 100)}% of reviews are negative
          </div>
        )}
      </div>

      {/* matched signals */}
      {product.matched_preferences.length > 0 && (
        <div>
          <p className="text-xs text-stone-400 uppercase tracking-widest mb-1.5">
            Matched Signals
          </p>
          <div className="flex flex-wrap gap-1">
            {product.matched_preferences.map((pref) => (
              <span
                key={pref}
                className="text-xs border border-stone-200 text-stone-500 px-2 py-0.5 rounded-sm"
              >
                {pref}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ProductPage() {
  const { asin } = useParams<{ asin: string }>();
  const router = useRouter();
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!asin) return;
    setLoading(true);
    setNotFound(false);
    getProduct(asin)
      .then(setProduct)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [asin]);

  const scoreColor = product ? fitScoreColor(product.fit_score) : "";

  const features = product?.features_text
    ? product.features_text
        .replace(/^\[|\]$/g, "")
        .split(/'\s*\n\s*'/)
        .map((f) => f.replace(/^'|'$/g, "").trim())
        .filter(Boolean)
        .slice(0, 6)
    : [];

  const rawDescription = product?.description_text ?? "";
  const description =
    rawDescription && !rawDescription.startsWith("[")
      ? rawDescription.length > 400
        ? rawDescription.slice(0, 400) + "..."
        : rawDescription
      : "";

  return (
    <div className="min-h-screen bg-stone-50">
      <TopBar />

      <div className="max-w-5xl mx-auto px-6 py-6">
        {loading && <SkeletonPage />}

        {notFound && (
          <p className="text-sm text-stone-500 text-center mt-12">Product not found.</p>
        )}

        {product && (
          <div className="flex flex-col md:flex-row gap-6 items-start">
            {/* left column */}
            <div className="flex-[2] min-w-0 w-full">
              {/* back link */}
              <button
                onClick={() => router.back()}
                className="text-xs text-stone-400 hover:text-stone-600 transition-colors mb-4 block"
              >
                ← Back to results
              </button>

              {/* brand + category */}
              <p className="text-xs font-mono text-stone-400 uppercase tracking-wide">
                {[product.brand, product.main_category].filter(Boolean).join(" · ")}
              </p>

              {/* title */}
              <h1 className="text-2xl font-bold text-stone-900 leading-snug mt-1 mb-3">
                {product.title}
              </h1>

              {/* metadata row */}
              <div className="flex flex-wrap items-center gap-x-2 font-mono text-sm text-stone-500 mb-4">
                <span>
                  {product.has_price && product.price != null
                    ? `$${product.price.toFixed(2)}`
                    : "Price unknown"}
                </span>
                {product.avg_rating != null && (
                  <>
                    <span>·</span>
                    <span>★ {product.avg_rating.toFixed(1)}</span>
                  </>
                )}
                <span>·</span>
                <span>{product.review_count.toLocaleString()} reviews</span>
              </div>

              {/* fit score */}
              <div className="mb-2">
                <p className="text-xs text-stone-400 uppercase tracking-widest font-mono mb-1">
                  Fit Score
                </p>
                <div className="flex items-baseline gap-2">
                  <span className={`text-4xl font-mono font-bold ${scoreColor}`}>
                    {product.fit_score.toFixed(1)}
                  </span>
                  <span className="text-stone-400 text-lg font-mono">/ 100</span>
                </div>
              </div>

              {/* score breakdown */}
              <div className="flex flex-col gap-2.5 mt-5 pt-4 border-t border-stone-100">
                <p className="text-xs font-mono text-stone-400 uppercase tracking-widest mb-1">
                  Score Breakdown
                </p>
                {[
                  { label: "Retrieval relevance", value: null },
                  { label: "Evidence score",      value: product.evidence_score * 100 },
                  { label: "Price fit",           value: product.price_fit != null ? product.price_fit * 100 : null },
                  { label: "Rating confidence",   value: product.rating_confidence != null ? product.rating_confidence * 100 : null },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center gap-3">
                    <span className="text-xs text-stone-400 w-36 shrink-0">{label}</span>
                    <div className="flex-1 h-1 bg-stone-100">
                      {value != null && (
                        <div
                          className="h-1 bg-orange-500"
                          style={{ width: `${Math.min(value, 100).toFixed(1)}%` }}
                        />
                      )}
                    </div>
                    <span className="font-mono text-xs text-stone-600 w-8 text-right">
                      {value != null ? value.toFixed(1) : "—"}
                    </span>
                  </div>
                ))}
              </div>

              {/* features */}
              {features.length > 0 && (
                <div className="mt-6 pt-4 border-t border-stone-100">
                  <p className="text-xs font-mono text-stone-400 uppercase tracking-widest mb-2">
                    Product Features
                  </p>
                  <ul className="flex flex-col gap-1">
                    {features.map((f, i) => (
                      <li key={i} className="text-sm text-stone-600">
                        — {f}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* description */}
              {description && (
                <div className="mt-6 pt-4 border-t border-stone-100">
                  <p className="text-xs font-mono text-stone-400 uppercase tracking-widest mb-2">
                    Description
                  </p>
                  <p className="text-sm text-stone-600 leading-relaxed">{description}</p>
                </div>
              )}
            </div>

            {/* right column */}
            <div className="flex-1 w-full md:sticky md:top-6">
              <EvidencePanel product={product} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProductPageWrapper() {
  return (
    <Suspense>
      <ProductPage />
    </Suspense>
  );
}
