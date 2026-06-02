import json
import logging
import math
import pickle
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import faiss
import pyarrow.parquet as pq
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from search.bm25_index import BM25Index
from search.query_parser import parse
from search.rank import compute_fit_score, price_fit_score, rank_results, rating_confidence_score
from search.retrieve import retrieve

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

with open("config/settings.yaml") as f:
    cfg = yaml.safe_load(f)

_search_cfg = cfg["search"]
_backend_cfg = cfg.get("backend", {})
TOP_K_DEFAULT: int = _backend_cfg.get("top_k_default", 10)
TOP_K_MAX: int = _backend_cfg.get("top_k_max", 20)


def _nan_to_none(d: dict) -> dict:
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in d.items()}


class _BM25Unpickler(pickle.Unpickler):
    # BM25Index is pickled as __main__.BM25Index when built via CLI; remap to its real module path.

    def find_class(self, module: str, name: str):
        if module == "__main__" and name == "BM25Index":
            return BM25Index
        return super().find_class(module, name)


class _State:
    products_lookup: dict[str, dict] = {}
    aggregates_lookup: dict[str, dict] = {}
    bm25_index: BM25Index | None = None
    model: SentenceTransformer | None = None
    faiss_index: Any = None
    embedding_ids: list[str] = []


_state = _State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Loading products_clean.parquet")
    products_df = pq.read_table("data/processed/products_clean.parquet").to_pandas()
    _state.products_lookup = {r["parent_asin"]: _nan_to_none(r) for r in products_df.to_dict(orient="records")}
    log.info("Loaded %d products", len(_state.products_lookup))

    log.info("Loading product_aggregates.parquet")
    agg_df = pq.read_table("data/aggregates/product_aggregates.parquet").to_pandas()
    _state.aggregates_lookup = {r["parent_asin"]: _nan_to_none(r) for r in agg_df.to_dict(orient="records")}
    log.info("Loaded %d aggregates", len(_state.aggregates_lookup))

    log.info("Loading BM25 index from %s", _search_cfg["bm25_index_path"])
    with open(_search_cfg["bm25_index_path"], "rb") as f:
        _state.bm25_index = _BM25Unpickler(f).load()
    log.info("Loaded BM25 index (%d products)", len(_state.bm25_index.product_ids))

    log.info("Loading embedding model: %s", _search_cfg["embedding_model"])
    _state.model = SentenceTransformer(_search_cfg["embedding_model"])

    log.info("Loading FAISS index from %s", _search_cfg["faiss_index_path"])
    _state.faiss_index = faiss.read_index(str(Path(_search_cfg["faiss_index_path"])))

    log.info("Loading embedding IDs from %s", _search_cfg["embedding_ids_path"])
    with open(_search_cfg["embedding_ids_path"], "rb") as f:
        _state.embedding_ids = pickle.load(f)

    log.info("All components loaded — server ready")
    yield


app = FastAPI(lifespan=lifespan)


class SearchResult(BaseModel):
    asin: str
    title: str
    brand: str
    price: float | None
    has_price: bool
    avg_rating: float | None
    review_count: int
    fit_score: float
    evidence_score: float
    complaint_rate: float
    top_pros: list[str]
    top_cons: list[str]
    over_budget: bool
    matched_preferences: list[str]


class ProductDetail(SearchResult):
    rrf_score: float | None = None
    price_fit: float | None
    rating_confidence: float | None
    description_text: str
    features_text: str


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/search", response_model=list[SearchResult])
async def search(
    q: str,
    top_k: int = Query(default=TOP_K_DEFAULT, ge=1, le=TOP_K_MAX),
) -> list[SearchResult]:
    parsed = parse(q)

    rrf_results = retrieve(
        parsed.clean_query,
        _state.bm25_index,
        _state.model,
        _state.faiss_index,
        _state.embedding_ids,
        top_k=top_k * 2,
    )

    if parsed.brand_exclusions:
        rrf_results = [
            (asin, score)
            for asin, score in rrf_results
            if _state.products_lookup.get(asin, {}).get("brand", "").lower()
            not in parsed.brand_exclusions
        ]

    ranked = rank_results(rrf_results, _state.products_lookup, _state.aggregates_lookup, parsed.budget)

    if parsed.budget is not None:
        budget = parsed.budget
        ranked = [r for r in ranked if r["price"] is None or r["price"] <= budget * 1.05]

    return [
        SearchResult(
            **{k: v for k, v in r.items() if k in SearchResult.model_fields},
            matched_preferences=parsed.preferences,
        )
        for r in ranked[:top_k]
    ]


@app.get("/product/{asin}", response_model=ProductDetail)
async def get_product(asin: str) -> ProductDetail:
    product = _state.products_lookup.get(asin)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    aggregates = _state.aggregates_lookup.get(asin)

    if aggregates is not None:
        evidence_score = float(aggregates.get("evidence_score") or 0.3)
        complaint_rate = float(aggregates.get("complaint_rate") or 0.0)
        avg_rating = aggregates.get("avg_rating")
        review_count = int(aggregates.get("review_count") or 0)
        raw_pros = aggregates.get("top_pros", "[]")
        raw_cons = aggregates.get("top_cons", "[]")
    else:
        evidence_score = 0.3
        complaint_rate = 0.0
        avg_rating = product.get("average_rating")
        review_count = int(product.get("rating_number") or 0)
        raw_pros = "[]"
        raw_cons = "[]"

    price = product.get("price") if product.get("has_price") else None
    top_pros: list[str] = json.loads(raw_pros) if raw_pros else []
    top_cons: list[str] = json.loads(raw_cons) if raw_cons else []

    return ProductDetail(
        asin=asin,
        title=product.get("title", ""),
        brand=product.get("brand", ""),
        price=price,
        has_price=bool(product.get("has_price", False)),
        avg_rating=float(avg_rating) if avg_rating is not None else None,
        review_count=review_count,
        fit_score=compute_fit_score(asin, 1.0, 1.0, product, aggregates, None),
        evidence_score=evidence_score,
        complaint_rate=complaint_rate,
        top_pros=top_pros,
        top_cons=top_cons,
        over_budget=False,
        matched_preferences=[],
        rrf_score=None,
        price_fit=price_fit_score(price, None),
        rating_confidence=rating_confidence_score(avg_rating, review_count),
        description_text=product.get("description_text", ""),
        features_text=product.get("features_text", ""),
    )
