"""
Stream Electronics reviews from Amazon Reviews 2023.
Filters to target ASINs from cleaned products and writes a Parquet sample.

Run:
    python -m ingestion.stream_reviews --config config/settings.yaml
"""

import argparse
import logging
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from datasets import load_dataset
from dotenv import load_dotenv

log = logging.getLogger(__name__)

SCHEMA = pa.schema([
    pa.field("parent_asin", pa.string()),
    pa.field("rating", pa.float32()),
    pa.field("review_title", pa.string()),
    pa.field("text", pa.string()),
    pa.field("word_count", pa.int32()),
    pa.field("helpful_vote", pa.int32()),
    pa.field("verified_purchase", pa.bool_()),
    pa.field("timestamp", pa.int64()),
])


def load_config(path: str) -> dict:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return raw["reviews"]


def load_target_asins(products_path: str) -> set[str]:
    table = pq.read_table(products_path, columns=["parent_asin"])
    asins = set(table.column("parent_asin").to_pylist())
    log.info("Loaded %d target ASINs from %s", len(asins), products_path)
    return asins


def safe_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float):
        return None
    return str(value).strip() or None


def clean_record(record: dict, min_review_length: int) -> dict | None:
    text = safe_str(record.get("text"))
    if not text or len(text) < min_review_length:
        return None

    raw_rating = record.get("rating")
    rating = None if (raw_rating is None or isinstance(raw_rating, float) and raw_rating != raw_rating) else float(raw_rating)

    raw_vote = record.get("helpful_vote")
    helpful_vote = 0 if (raw_vote is None or isinstance(raw_vote, float)) else int(raw_vote)

    raw_vp = record.get("verified_purchase")
    verified_purchase = False if (raw_vp is None or isinstance(raw_vp, float)) else bool(raw_vp)

    raw_ts = record.get("timestamp")
    timestamp = None if (raw_ts is None or isinstance(raw_ts, float) and raw_ts != raw_ts) else int(raw_ts)

    return {
        "parent_asin": record["parent_asin"],
        "rating": rating,
        "review_title": safe_str(record.get("title")),
        "text": text,
        "word_count": len(text.split()),
        "helpful_vote": helpful_vote,
        "verified_purchase": verified_purchase,
        "timestamp": timestamp,
    }


def stream_reviews(cfg: dict, target_asins: set[str]) -> tuple[list[dict], int]:
    target_count = cfg["target_review_count"]
    max_examine = cfg["max_records_to_examine"]
    per_product_cap = cfg["max_reviews_per_product"]
    min_length = cfg["min_review_length"]
    log_every = cfg["log_every_n_examined"]

    log.info(
        "Streaming raw_review_Electronics — target %d reviews, cap %d/product, max %d examined",
        target_count,
        per_product_cap,
        max_examine,
    )

    dataset = load_dataset(
        "McAuley-Lab/Amazon-Reviews-2023",
        "raw_review_Electronics",
        split="full",
        streaming=True,
    )

    needed_cols = ["parent_asin", "rating", "title", "text", "helpful_vote", "verified_purchase", "timestamp"]
    dataset = dataset.select_columns(needed_cols)

    collected: list[dict] = []
    per_product_counts: dict[str, int] = {}
    n_examined = 0

    for record in dataset:
        n_examined += 1

        if n_examined % log_every == 0:
            log.info(
                "Examined %d records, collected %d reviews, %d products covered",
                n_examined,
                len(collected),
                len(per_product_counts),
            )

        if n_examined > max_examine:
            log.info("Reached max_records_to_examine (%d)", max_examine)
            break

        asin = record.get("parent_asin")
        if not asin or asin not in target_asins:
            continue

        if per_product_counts.get(asin, 0) >= per_product_cap:
            continue

        cleaned = clean_record(record, min_length)
        if cleaned is None:
            continue

        collected.append(cleaned)
        per_product_counts[asin] = per_product_counts.get(asin, 0) + 1

        if len(collected) >= target_count:
            log.info(
                "Reached target of %d reviews after examining %d records",
                target_count,
                n_examined,
            )
            break

    return collected, n_examined


def write_parquet(records: list[dict], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(records, schema=SCHEMA)
    pq.write_table(table, output_path)
    log.info("Wrote %d rows to %s", len(records), output_path)


def print_summary(records: list[dict], n_examined: int, output_path: str) -> None:
    per_product: dict[str, int] = {}
    for r in records:
        asin = r["parent_asin"]
        per_product[asin] = per_product.get(asin, 0) + 1

    avg_per_product = sum(per_product.values()) / len(per_product) if per_product else 0

    print("\n--- Review Stream Summary ---")
    print(f"  Records examined    : {n_examined:,}")
    print(f"  Reviews collected   : {len(records):,}")
    print(f"  Products covered    : {len(per_product):,}")
    print(f"  Avg reviews/product : {avg_per_product:.1f}")
    print(f"  Output              : {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream Electronics reviews.")
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to settings.yaml",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    load_dotenv()

    cfg = load_config(args.config)

    target_asins = load_target_asins("data/processed/products_clean.parquet")

    records, n_examined = stream_reviews(cfg, target_asins)

    if not records:
        log.error("No reviews collected. Check ASIN overlap and dataset config.")
        sys.exit(1)

    write_parquet(records, cfg["output_path"])
    print_summary(records, n_examined, cfg["output_path"])


if __name__ == "__main__":
    main()
