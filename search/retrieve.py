"""
Input:   indexes/bm25_index.pkl
         indexes/faiss_index.bin
         indexes/embedding_ids.pkl
         embedding model (all-MiniLM-L6-v2)
Output:  list of (asin, rrf_score) tuples

Run:
    python -m search.retrieve --query "noise cancelling headphones under 200" \
        --config config/settings.yaml
"""
import argparse
import logging
import pickle
from pathlib import Path

import faiss
import pyarrow.parquet as pq
import yaml
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from search.bm25_index import BM25Index
from search.embed import search as embed_search

log = logging.getLogger(__name__)


# rrf_k=60 is the standard default from Cormack et al. 2009.
def retrieve(
    query: str,
    bm25_index: BM25Index,
    model: SentenceTransformer,
    faiss_index,
    embedding_ids: list[str],
    top_k: int = 20,
    rrf_k: int = 60,
) -> list[tuple[str, float]]:
    bm25_results = bm25_index.search(query, top_k=top_k * 3)
    sem_results = embed_search(query, model, faiss_index, embedding_ids, top_k=top_k * 3)

    rrf_scores: dict[str, float] = {}
    for rank, (asin, _) in enumerate(bm25_results):
        rrf_scores[asin] = rrf_scores.get(asin, 0.0) + 1.0 / (rrf_k + rank)
    for rank, (asin, _) in enumerate(sem_results):
        rrf_scores[asin] = rrf_scores.get(asin, 0.0) + 1.0 / (rrf_k + rank)

    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]


def load_retrieval_components(cfg: dict) -> tuple:
    search_cfg = cfg["search"]

    bm25_path = Path(search_cfg["bm25_index_path"])
    log.info("Loading BM25 index from %s", bm25_path)
    bm25_index = BM25Index.load(bm25_path)

    model_name = search_cfg["embedding_model"]
    log.info("Loading embedding model: %s", model_name)
    model = SentenceTransformer(model_name)

    faiss_path = Path(search_cfg["faiss_index_path"])
    log.info("Loading FAISS index from %s", faiss_path)
    faiss_index = faiss.read_index(str(faiss_path))

    ids_path = Path(search_cfg["embedding_ids_path"])
    log.info("Loading embedding IDs from %s", ids_path)
    with open(ids_path, "rb") as f:
        embedding_ids = pickle.load(f)

    return bm25_index, model, faiss_index, embedding_ids


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--config", default="config/settings.yaml")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    log.info("Loading title lookup")
    products_df = pq.read_table("data/processed/products_clean.parquet").to_pandas()
    title_lookup: dict[str, str] = dict(zip(products_df["parent_asin"], products_df["title"]))

    bm25_index, model, faiss_index, embedding_ids = load_retrieval_components(cfg)

    log.info("Query: %r  top_k=%d", args.query, args.top_k)
    results = retrieve(
        args.query,
        bm25_index,
        model,
        faiss_index,
        embedding_ids,
        top_k=args.top_k,
    )

    print(f"\n{'Rank':<5} {'ASIN':<15} {'RRF Score':<12} Title")
    print("-" * 90)
    for rank, (asin, score) in enumerate(results, start=1):
        title = title_lookup.get(asin, "Unknown")[:60]
        print(f"{rank:<5} {asin:<15} {score:<12.6f} {title}")


if __name__ == "__main__":
    main()
