"""
Inputs:  data/processed/products_clean.parquet
         data/aggregates/product_aggregates.parquet
Outputs: indexes/product_embeddings.npy
         indexes/faiss_index.bin
         indexes/embedding_ids.pkl

Run:
    python -m search.embed --config config/settings.yaml
"""
import argparse
import logging
import pickle
from pathlib import Path

import faiss
import numpy as np
import pyarrow.parquet as pq
import yaml
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from search.bm25_index import _build_doc

log = logging.getLogger(__name__)


def search(
    query: str,
    model: SentenceTransformer,
    faiss_index: faiss.Index,
    embedding_ids: list[str],
    top_k: int = 20,
) -> list[tuple[str, float]]:
    vec = model.encode([query], normalize_embeddings=True)
    scores, indices = faiss_index.search(vec.astype(np.float32), top_k)
    return [
        (embedding_ids[idx], float(scores[0][rank]))
        for rank, idx in enumerate(indices[0])
        if idx != -1
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
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    products_path = Path("data/processed/products_clean.parquet")
    aggregates_path = Path(cfg["aggregates"]["output_path"])
    search_cfg = cfg["search"]
    embeddings_path = Path(search_cfg["embeddings_path"])
    faiss_index_path = Path(search_cfg["faiss_index_path"])
    embedding_ids_path = Path(search_cfg["embedding_ids_path"])
    model_name = search_cfg["embedding_model"]

    log.info("Loading products from %s", products_path)
    products_df = pq.read_table(products_path).to_pandas()
    log.info("Loaded %d products", len(products_df))

    log.info("Loading aggregates from %s", aggregates_path)
    aggregates_df = pq.read_table(aggregates_path).to_pandas()
    log.info("Loaded %d aggregates", len(aggregates_df))

    agg_index = aggregates_df.set_index("parent_asin") if not aggregates_df.empty else {}

    log.info("Loading model: %s", model_name)
    model = SentenceTransformer(model_name)

    docs: list[str] = []
    embedding_ids: list[str] = []
    for _, row in products_df.iterrows():
        asin = row["parent_asin"]
        agg_row = agg_index.loc[asin] if asin in agg_index.index else None
        docs.append(_build_doc(row, agg_row))
        embedding_ids.append(asin)

    log.info("Encoding %d documents (batch_size=64)", len(docs))
    embeddings = model.encode(
        docs,
        batch_size=64,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    embeddings = embeddings.astype(np.float32)
    log.info("Encoding complete — shape: %s", embeddings.shape)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    log.info("FAISS index built: %d vectors, dim=%d", index.ntotal, dim)

    embeddings_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(embeddings_path, embeddings)
    faiss.write_index(index, str(faiss_index_path))
    with open(embedding_ids_path, "wb") as f:
        pickle.dump(embedding_ids, f)

    log.info("Saved embeddings → %s", embeddings_path)
    log.info("Saved FAISS index → %s", faiss_index_path)
    log.info("Saved embedding IDs → %s", embedding_ids_path)


if __name__ == "__main__":
    main()
