"""
Compute NDCG@10, MRR, Recall@20, and latency metrics from hand-labeled benchmark.

Run:
    python -m eval.benchmark
"""
import json
import math
import statistics
from pathlib import Path

BENCHMARK_PATH = Path("eval/benchmark_queries.json")
RESULTS_PATH = Path("eval/benchmark_results.json")

TIER_NAMES = {1: "simple", 2: "medium", 3: "hard"}


def dcg_at_k(relevances: list[int], k: int) -> float:
    return sum(
        (2 ** rel - 1) / math.log2(i + 2)
        for i, rel in enumerate(relevances[:k])
    )


def ndcg_at_k(results: list[dict], k: int) -> float:
    relevances = [r["relevance"] for r in results]
    ideal = sorted(relevances, reverse=True)
    idcg = dcg_at_k(ideal, k)
    if idcg == 0:
        return 0.0
    return dcg_at_k(relevances, k) / idcg


def mrr(results: list[dict]) -> float:
    for r in results:
        if r["relevance"] >= 1:
            return 1.0 / r["rank"]
    return 0.0


def recall_at_k(results: list[dict], k: int) -> float:
    total_relevant = sum(1 for r in results if r["relevance"] >= 1)
    if total_relevant == 0:
        return 0.0
    retrieved_relevant = sum(1 for r in results[:k] if r["relevance"] >= 1)
    return retrieved_relevant / total_relevant


def percentile(values: list[float], p: float) -> float:
    sorted_vals = sorted(values)
    idx = (len(sorted_vals) - 1) * p / 100
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def main() -> None:
    with open(BENCHMARK_PATH) as f:
        data = json.load(f)

    queries = data["queries"]

    tier_ndcg: dict[int, list[float]] = {1: [], 2: [], 3: []}
    all_ndcg, all_mrr, all_recall, all_latency = [], [], [], []

    for q in queries:
        results = q["results"]
        ndcg = ndcg_at_k(results, 10)
        rr = mrr(results)
        rec = recall_at_k(results, 20)
        lat = q["latency_ms"]

        all_ndcg.append(ndcg)
        all_mrr.append(rr)
        all_recall.append(rec)
        all_latency.append(lat)
        tier_ndcg[q["tier"]].append(ndcg)

    p50 = percentile(all_latency, 50)
    p95 = percentile(all_latency, 95)
    tier_counts = {t: len(v) for t, v in tier_ndcg.items()}

    sep = "─" * 30
    print()
    print("=== ClearCart Benchmark Results ===")
    print()
    print("System: Hybrid BM25 + Semantic (RRF)")
    print(
        f"Queries: {len(queries)} "
        f"(Tier 1: {tier_counts[1]}, Tier 2: {tier_counts[2]}, Tier 3: {tier_counts[3]})"
    )
    print()
    print(f"{'Metric':<16} {'Value':>12}")
    print(sep)
    print(f"{'NDCG@10':<16} {statistics.mean(all_ndcg):>12.3f}")
    print(f"{'MRR':<16} {statistics.mean(all_mrr):>12.3f}")
    print(f"{'Recall@20':<16} {statistics.mean(all_recall):>12.3f}")
    print(f"{'p50 Latency':<16} {p50:>9.1f} ms")
    print(f"{'p95 Latency':<16} {p95:>9.1f} ms")
    print()
    print("NDCG@10 by tier:")
    for tier, name in TIER_NAMES.items():
        mean = statistics.mean(tier_ndcg[tier]) if tier_ndcg[tier] else 0.0
        print(f"  Tier {tier} ({name}): {mean:.3f}")

    results_out = {
        "system": "Hybrid BM25 + Semantic (RRF)",
        "queries_total": len(queries),
        "tier_counts": {str(t): c for t, c in tier_counts.items()},
        "metrics": {
            "ndcg_at_10": round(statistics.mean(all_ndcg), 4),
            "mrr": round(statistics.mean(all_mrr), 4),
            "recall_at_20": round(statistics.mean(all_recall), 4),
            "p50_latency_ms": round(p50, 1),
            "p95_latency_ms": round(p95, 1),
        },
        "ndcg_at_10_by_tier": {
            str(t): round(statistics.mean(v), 4) if v else 0.0
            for t, v in tier_ndcg.items()
        },
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results_out, f, indent=2)

    print(f"\nResults saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
