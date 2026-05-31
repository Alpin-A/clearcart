# ClearCart

Most shopping platforms rank by sponsorship and star averages. ClearCart
ranks by fit — matching products to what you actually asked for using
review evidence, price signals, and learned ranking.

A hybrid search and learning-to-rank engine built over Amazon review data.

> 🔄 Currently under active development — M3 in progress

---

## The Problem

Most platforms know what sponsors paid, not what you need. A query like:

> "noise-cancelling headphones under $200 for studying, long battery
> life, avoid comfort complaints"

contains a price constraint, a use-case, a feature requirement, and a
negative preference. Most platforms collapse these into a keyword search
and sort by popularity. ClearCart treats it as a structured retrieval
and ranking problem.

---

## System Architecture

> Architecture diagram coming after core pipeline is complete.

**Pipeline stages:**

1. **Ingestion** — Stream product metadata and reviews from Amazon
   Reviews 2023 (McAuley Lab) via HuggingFace. Filter to a target
   category using a leaf-category allowlist.

2. **Cleaning** — Normalize types, handle missing fields, flatten
   structured fields, build search-ready text representations.

3. **Aggregation** — Compute per-product review signals: evidence
   score, rating confidence, complaint rate, top pros/cons.

4. **Indexing** — BM25 lexical index + semantic embedding index
   (sentence-transformers + FAISS).

5. **Retrieval** — Hybrid retrieval using reciprocal rank fusion over
   BM25 and semantic candidates.

6. **Ranking** — Rule-based fit scoring (V1) (price/battery/use-case
   attribute matching), LightGBM LambdaRank (V2).

7. **API + UI** — FastAPI backend, Next.js frontend with evidence panels
   and fit score display.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Ingestion | Python, HuggingFace `datasets` (streaming) |
| Storage | Parquet (pipeline), SQLite (metadata), FAISS (vectors) |
| Search | BM25 (`rank-bm25`), sentence-transformers |
| Ranking | Rule-based (V1), LightGBM LambdaRank (V2) |
| Backend | FastAPI |
| Frontend | Next.js, TypeScript, Tailwind, shadcn/ui |
| Evaluation | NDCG@10, MRR, Recall@K, latency benchmarks |

---

## Dataset

**Source:** [Amazon Reviews 2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023)
(McAuley Lab, UCSD)

**Category:** Electronics → Headphones / Audio

**Scale:**
| Milestone | Products | Reviews |
|---|---|---|
| M1 (current) | 500 sample | N/A |
| M2 | 10K | 100K |
| M3 | 50K | 500K |

---

## Evaluation

> Benchmark results added after evaluation pipeline is complete.

Planned metrics across BM25 / semantic / hybrid / LTR variants:

| System | NDCG@10 | MRR | Recall@20 | p95 Latency |
|---|---|---|---|---|
| BM25 only | — | — | — | — |
| Semantic only | — | — | — | — |
| Hybrid (RRF) | — | — | — | — |
| Hybrid + LTR | — | — | — | — |

---

## Build Status

| Milestone | Status |
|---|---|
| M1 — Data ingestion foundation      | ✅ Complete |
| M2 — Cleaning + review aggregation  | ✅ Complete |
| M3 — BM25 + semantic search         | ✅ Complete |
| M4 — Ranking + API                  | 🔄 In progress |
| M5 — Frontend + evaluation | ⬜ Planned |

---

## Running Locally

```bash
cd clearcart
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m ingestion.stream_products --config config/settings.yaml
```

---

## Design Decisions

Design decisions are documented as they are made. Current decisions:

**Category filtering uses a leaf-category allowlist, not keyword matching.**
Keyword matching against the `categories` field produces too many false
positives — accessories, cables, and skins are filed under headphone
categories by Amazon. Matching against the leaf category (last element)
with an explicit allowlist is more precise and stable.

---

## References

- Ni et al., [Justifying Recommendations using Distantly-Labeled Reviews](https://aclanthology.org/D19-1018/) (EMNLP 2019)
- Hou et al., [Bridging Language and Items for Retrieval and Recommendation](https://arxiv.org/abs/2403.03952) (Amazon Reviews 2023)
