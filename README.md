# ClearCart

Most shopping platforms rank by sponsorship and star averages. ClearCart
ranks by fit — matching products to what you actually asked for using
review evidence, price signals, and learned ranking.

A hybrid search and learning-to-rank engine built over Amazon review data.

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

6. **Ranking** — Rule-based fit scoring combining retrieval score,
   evidence score, price fit, rating confidence, and complaint rate.

7. **API + UI** — FastAPI backend, Next.js frontend with evidence panels
   and fit score display.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Ingestion | Python, HuggingFace `datasets` (streaming) |
| Storage | Parquet (pipeline), FAISS (vectors) |
| Search | BM25 (`rank-bm25`), `sentence-transformers` (`all-MiniLM-L6-v2`) |
| Ranking | Rule-based fit scoring with 5 signals |
| Backend | FastAPI |
| Frontend | Next.js, TypeScript, Tailwind, shadcn/ui |
| Evaluation | NDCG@10, MRR, Recall@20, latency, LLM-as-judge |

---

## Dataset

**Source:** [Amazon Reviews 2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023)
(McAuley Lab, UCSD)

**Category:** Electronics → Headphones / Audio

| | Products | Reviews |
|---|---|---|
| Ingested | 4,996 | 66,254 |
| With aggregates | 4,062 | — |
| Avg reviews/product | — | 16.3 |

---

## Evaluation

Evaluated against 20 hand-labeled benchmark queries across three
difficulty tiers. Label quality validated via LLM-as-judge
inter-rater agreement.

| Metric | Value |
|---|---|
| NDCG@10 | 0.757 |
| MRR | 0.967 |
| Recall@20 | 1.000 |
| p50 Latency | 47.5ms |
| p95 Latency | 324.2ms |

**NDCG@10 by query complexity:**

| Tier | Description | Queries | NDCG@10 |
|---|---|---|---|
| 1 | Simple | 5 | 0.662 |
| 2 | Medium | 8 | 0.757 |
| 3 | Hard (multi-constraint) | 7 | 0.834 |

**Inter-rater agreement:** Cohen's κ = 0.45 (moderate) between
human labels and LLM-as-judge across 400 query-product pairs.

Tier 3 outperforms Tier 1 because specific multi-constraint queries
narrow the candidate space, making relevant results easier to surface.
Simple broad queries retrieve more borderline results, depressing NDCG.

---

## Build Status

| Milestone | Status |
|---|---|
| M1 — Data ingestion foundation | ✅ Complete |
| M2 — Cleaning + review aggregation | ✅ Complete |
| M3 — BM25 + semantic search | ✅ Complete |
| M4 — Ranking + API | ✅ Complete |
| M5 — Frontend + evaluation | ✅ Complete |

---

## Running Locally

```bash
git clone https://github.com/Alpin-A/clearcart.git
cd clearcart
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run ingestion pipeline
python -m ingestion.stream_products --config config/settings.yaml
python -m ingestion.clean_products
python -m ingestion.stream_reviews --config config/settings.yaml
python -m ingestion.clean_reviews --config config/settings.yaml
python -m ingestion.aggregate_reviews --config config/settings.yaml

# Build indexes
python -m search.bm25_index --config config/settings.yaml
python -m search.embed --config config/settings.yaml

# Start backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

---

## Design Decisions

**Category filtering uses a leaf-category allowlist, not keyword matching.**
Keyword matching against the `categories` field produces too many false
positives — accessories, cables, and skins are filed under headphone
categories by Amazon. Matching against the leaf category (last element)
with an explicit allowlist is more precise and stable.

**Hybrid retrieval uses Reciprocal Rank Fusion (RRF), not weighted score fusion.**
BM25 and cosine similarity scores are on different scales and normalizing
them introduces arbitrary decisions. RRF combines rankings directly using
`1/(k+rank)` — robust, parameter-free, and consistent with the original
Cormack et al. (2009) formulation.

**Review evidence score replaces raw star rating as the primary quality signal.**
A product with 4.8 stars and 6 reviews ranks above a product with 4.3
stars and 2,000 reviews on most platforms. Evidence score weights review
length, helpful vote rate, verified purchase rate, and domain specificity
to produce a more reliable quality signal.

**Rating confidence uses log-weighted normalization, not raw averages.**
`rating_confidence = (avg_rating - 1) / 4 * log(review_count + 1) / log(101)`
This penalizes products with few reviews even if their average is high,
which is the correct behavior for ranking under uncertainty.

---

## References

- Ni et al., [Justifying Recommendations using Distantly-Labeled Reviews](https://aclanthology.org/D19-1018/) (EMNLP 2019)
- Hou et al., [Bridging Language and Items for Retrieval and Recommendation](https://arxiv.org/abs/2403.03952) (Amazon Reviews 2023)
- Cormack et al., [Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods](https://dl.acm.org/doi/10.1145/1571941.1572114) (SIGIR 2009)