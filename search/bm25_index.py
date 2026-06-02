"""
Inputs:  data/processed/products_clean.parquet
         data/aggregates/product_aggregates.parquet
Output:  indexes/bm25_index.pkl

Run:
    python -m search.bm25_index --config config/settings.yaml

Sanity check:
    from search.bm25_index import BM25Index
    from pathlib import Path
    index = BM25Index.load(Path("indexes/bm25_index.pkl"))
    results = index.search("noise cancelling headphones under 200")
    print(f"Results: {len(results)}")
    print(results[:5])

    import pyarrow.parquet as pq
    df = pq.read_table("data/processed/products_clean.parquet").to_pandas()
    lookup = df.set_index("parent_asin")["title"].to_dict()
    for asin, score in results[:5]:
        print(f"  {score:.4f}  {lookup.get(asin, 'Unknown')[:70]}")
"""
import argparse
import json
import logging
import pickle
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import yaml
from dotenv import load_dotenv
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from rank_bm25 import BM25Okapi

log = logging.getLogger(__name__)

DOMAIN_ABBREVS = {"anc", "anr", "tws", "eq", "db", "hz"}
_STOPWORDS: set[str] | None = None


def _get_stopwords() -> set[str]:
    global _STOPWORDS
    if _STOPWORDS is None:
        _STOPWORDS = set(stopwords.words("english")) - DOMAIN_ABBREVS
    return _STOPWORDS


def tokenize(text: str) -> list[str]:
    sw = _get_stopwords()
    tokens = word_tokenize(text.lower())
    return [
        t for t in tokens
        if (t.isalpha() and len(t) >= 2) or t in DOMAIN_ABBREVS
        if t not in sw or t in DOMAIN_ABBREVS
    ]


def _build_doc(row: pd.Series, agg_row: pd.Series | None) -> str:
    parts = [
        row.get("title", "") or "",
        row.get("features_text", "") or "",
        row.get("description_text", "") or "",
        row.get("brand", "") or "",
    ]
    if agg_row is not None:
        for field in ("top_pros", "top_cons"):
            raw = agg_row.get(field)
            if raw:
                try:
                    phrases = json.loads(raw)
                    parts.extend(phrases)
                except (json.JSONDecodeError, TypeError):
                    pass
    return " ".join(p for p in parts if p)


class BM25Index:
    product_ids: list[str]
    bm25: BM25Okapi

    def build(self, products_df: pd.DataFrame, aggregates_df: pd.DataFrame) -> None:
        agg_index = aggregates_df.set_index("parent_asin") if not aggregates_df.empty else pd.DataFrame()

        corpus: list[list[str]] = []
        self.product_ids = []
        total_tokens = 0

        for _, row in products_df.iterrows():
            asin = row["parent_asin"]
            agg_row = agg_index.loc[asin] if asin in agg_index.index else None
            doc = _build_doc(row, agg_row)
            tokens = tokenize(doc)
            corpus.append(tokens)
            self.product_ids.append(asin)
            total_tokens += len(tokens)

        self.bm25 = BM25Okapi(corpus)
        avg_tokens = total_tokens / len(corpus) if corpus else 0.0
        log.info("Indexed %d products, avg %.1f tokens/doc", len(corpus), avg_tokens)

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        tokens = tokenize(query)
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(
            ((self.product_ids[i], float(scores[i])) for i in range(len(scores))),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(asin, score) for asin, score in ranked[:top_k] if score > 0]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        log.info("Saved BM25 index to %s", path)

    @classmethod
    def load(cls, path: Path) -> "BM25Index":
        import sys
        # If the index was built by running this file directly, pickle stored
        # the class as __main__.BM25Index. Inject cls so it resolves.
        main = sys.modules.get("__main__")
        if main and not hasattr(main, "BM25Index"):
            main.BM25Index = cls
        with open(path, "rb") as f:
            index = pickle.load(f)
        log.info("Loaded BM25 index from %s (%d products)", path, len(index.product_ids))
        return index


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
    index_path = Path(cfg["search"]["bm25_index_path"])

    log.info("Loading products from %s", products_path)
    products_df = pq.read_table(products_path).to_pandas()
    log.info("Loaded %d products", len(products_df))

    log.info("Loading aggregates from %s", aggregates_path)
    aggregates_df = pq.read_table(aggregates_path).to_pandas()
    log.info("Loaded %d aggregates", len(aggregates_df))

    index = BM25Index()
    log.info("Building BM25 index")
    index.build(products_df, aggregates_df)

    index.save(index_path)


if __name__ == "__main__":
    main()
