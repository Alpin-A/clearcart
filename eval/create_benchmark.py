"""
Generate benchmark query set for offline evaluation.
Retrieves top 20 results per query; relevance fields left null for hand-labeling.

Run:
    python -m eval.create_benchmark --config config/settings.yaml
"""
import argparse
import json
import logging
import time
from pathlib import Path

import pyarrow.parquet as pq
import yaml
from dotenv import load_dotenv

from search.retrieve import load_retrieval_components, retrieve

log = logging.getLogger(__name__)

QUERIES = [
    # Tier 1 — Simple
    {"id": 1,  "tier": 1, "query": "wireless earbuds under $50"},
    {"id": 2,  "tier": 1, "query": "over ear headphones"},
    {"id": 3,  "tier": 1, "query": "noise cancelling headphones"},
    {"id": 4,  "tier": 1, "query": "bluetooth headphones under $100"},
    {"id": 5,  "tier": 1, "query": "wired headphones"},
    # Tier 2 — Medium
    {"id": 6,  "tier": 2, "query": "noise cancelling headphones under $200 for studying"},
    {"id": 7,  "tier": 2, "query": "wireless earbuds for running under $50"},
    {"id": 8,  "tier": 2, "query": "over ear headphones long battery life under $100"},
    {"id": 9,  "tier": 2, "query": "comfortable headphones for long listening sessions"},
    {"id": 10, "tier": 2, "query": "headphones with good microphone for calls"},
    {"id": 11, "tier": 2, "query": "kids headphones with volume limit under $30"},
    {"id": 12, "tier": 2, "query": "wired headphones for studio recording"},
    {"id": 13, "tier": 2, "query": "true wireless earbuds with good bass"},
    # Tier 3 — Hard
    {"id": 14, "tier": 3, "query": "noise cancelling headphones under $200 for studying, avoid comfort complaints"},
    {"id": 15, "tier": 3, "query": "wireless earbuds for running under $50, waterproof, good bass"},
    {"id": 16, "tier": 3, "query": "over ear headphones under $150, long battery, comfortable for glasses wearers"},
    {"id": 17, "tier": 3, "query": "headphones for sleeping, lightweight, comfortable, under $50"},
    {"id": 18, "tier": 3, "query": "studio headphones flat frequency response under $200"},
    {"id": 19, "tier": 3, "query": "kids headphones durable under $30, volume limit, foldable"},
    {"id": 20, "tier": 3, "query": "gaming headset with good microphone under $100, comfortable for long sessions"},
]


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--output", default="eval/benchmark_queries.json")
    parser.add_argument("--top-k", type=int, default=20)
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    log.info("Loading product titles")
    products_df = pq.read_table("data/processed/products_clean.parquet").to_pandas()
    title_lookup: dict[str, str] = dict(
        zip(products_df["parent_asin"], products_df["title"])
    )

    log.info("Loading retrieval components")
    bm25_index, model, faiss_index, embedding_ids = load_retrieval_components(cfg)

    output: dict = {"queries": []}

    for entry in QUERIES:
        qid, query = entry["id"], entry["query"]
        log.info("[%2d/20] %s", qid, query)

        t0 = time.perf_counter()
        raw = retrieve(query, bm25_index, model, faiss_index, embedding_ids, top_k=args.top_k)
        latency_ms = (time.perf_counter() - t0) * 1000

        results = [
            {
                "rank": rank,
                "asin": asin,
                "title": title_lookup.get(asin, "Unknown"),
                "rrf_score": round(score, 6),
                "relevance": None,
            }
            for rank, (asin, score) in enumerate(raw, start=1)
        ]

        output["queries"].append(
            {
                "id": qid,
                "tier": entry["tier"],
                "query": query,
                "latency_ms": round(latency_ms, 1),
                "results": results,
            }
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    log.info("Wrote %d queries to %s", len(output["queries"]), out_path)

    assert len(output["queries"]) == 20
    for q in output["queries"]:
        assert len(q["results"]) == args.top_k, f"Query {q['id']}: {len(q['results'])} results"
        assert all(r["relevance"] is None for r in q["results"])
    log.info("All assertions passed.")


if __name__ == "__main__":
    main()
