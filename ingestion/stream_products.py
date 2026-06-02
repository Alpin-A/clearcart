"""
Stream Electronics product metadata from Amazon Reviews 2023.
Filters to headphone/audio products and writes a Parquet sample.

Run:
    python -m ingestion.stream_products --config config/settings.yaml
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
load_dotenv()
log = logging.getLogger(__name__)


def load_config(path: str) -> dict:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return raw["ingestion"]


def is_audio_product(record: dict, audio_categories: set[str]) -> bool:
    """
    Leaf category (last element) must be in the audio_categories allowlist.
    Records with no category are skipped — they cannot be reliably classified
    without a title keyword fallback, which lets through accessories and stands.
    """
    raw_cats = record.get("categories") or []
    if isinstance(raw_cats, list) and raw_cats:
        return raw_cats[-1] in audio_categories
    return False


def extract_fields(record: dict, keep_fields: list[str]) -> dict:
    """
    Missing fields become None rather than raising KeyError.
    No type coercion here — that belongs in a cleaning step.
    """
    return {field: record.get(field) for field in keep_fields}


def stream_audio_products(cfg: dict) -> tuple[list[dict], int]:
    """Returns collected records and total number of records examined."""
    target = cfg["target_product_count"]
    keep_fields = cfg["keep_fields"]
    log_every = cfg["log_every_n_examined"]
    min_reviews = cfg["min_review_count"]
    audio_categories = set(cfg["audio_categories"])

    log.info(
        "Loading dataset in streaming mode: %s / %s",
        cfg["hf_dataset_name"],
        cfg["hf_config_name"],
    )

    dataset = load_dataset(
        cfg["hf_dataset_name"],
        cfg["hf_config_name"],
        split=cfg["hf_split"],
        streaming=True,
    )

    # Drop columns we never use (images, videos, …) before iteration so that
    # pyarrow's schema-cast step doesn't choke on nested list<struct> fields
    # whose declared type doesn't match the actual wire format.
    needed_cols = sorted({"parent_asin", "rating_number", "title", "categories", *keep_fields})
    dataset = dataset.select_columns(needed_cols)

    collected: list[dict] = []
    seen_asins: set[str] = set()
    n_examined = 0

    for record in dataset:
        n_examined += 1

        if n_examined % log_every == 0:
            log.info(
                "Examined %d records, kept %d audio products so far",
                n_examined,
                len(collected),
            )

        asin = record.get("parent_asin")
        if not asin or asin in seen_asins:
            continue

        review_count = record.get("rating_number") or 0
        if review_count < min_reviews:
            continue

        if not is_audio_product(record, audio_categories):
            continue

        seen_asins.add(asin)
        collected.append(extract_fields(record, keep_fields))

        if len(collected) >= target:
            log.info(
                "Reached target of %d products after examining %d records",
                target,
                n_examined,
            )
            break

    return collected, n_examined


def write_parquet(records: list[dict], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(records)
    pq.write_table(table, output_path)
    log.info("Wrote %d rows to %s", len(records), output_path)


def print_summary(records: list[dict], n_examined: int, output_path: str) -> None:
    titles = [r.get("title") or "(no title)" for r in records[:5]]
    print("\n--- Summary ---")
    print(f"  Records examined : {n_examined:,}")
    print(f"  Products kept    : {len(records):,}")
    print(f"  Output           : {output_path}")
    print("  Sample titles    :")
    for t in titles:
        print(f"    • {t[:90]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream audio product metadata.")
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to settings.yaml",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)

    records, n_examined = stream_audio_products(cfg)

    if not records:
        log.error("No audio products found. Check keyword list and dataset config.")
        sys.exit(1)

    write_parquet(records, cfg["output_path"])
    print_summary(records, n_examined, cfg["output_path"])


if __name__ == "__main__":
    main()