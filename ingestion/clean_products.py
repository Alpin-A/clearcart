"""
Inputs:  data/raw/products_sample.parquet
Outputs: data/processed/products_clean.parquet
"""
import logging
import re
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

log = logging.getLogger(__name__)

RAW_PATH = Path("data/raw/products_sample.parquet")
OUTPUT_PATH = Path("data/processed/products_clean.parquet")

MIN_TITLE_LENGTH = 10

SCHEMA = pa.schema([
    pa.field("parent_asin", pa.string()),
    pa.field("title", pa.string()),
    pa.field("brand", pa.string()),
    pa.field("price", pa.float64()),
    pa.field("has_price", pa.bool_()),
    pa.field("average_rating", pa.float64()),
    pa.field("rating_number", pa.int64()),
    pa.field("description_text", pa.string()),
    pa.field("features_text", pa.string()),
    pa.field("search_text", pa.string()),
    pa.field("main_category", pa.string()),
])


def parse_price(raw: str | None) -> float | None:
    """
    Parse price string to float.
    Returns None for missing, zero, or unparseable values.
    The source encodes missing as the string 'None'.
    """
    if not isinstance(raw, str) or not raw or raw == "None":
        return None
    try:
        value = float(re.sub(r"[^\d.]", "", raw))
        return value if value > 0 else None
    except ValueError:
        return None


def flatten_list_field(value) -> str:
    """
    Join a list-of-strings field into a single string.
    Returns empty string for None or unexpected types.
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)
    return str(value)


def safe_str(value) -> str | None:
    """
    Return string value or None.
    Handles pandas NaN which is a float, not None.
    """
    if value is None:
        return None
    if isinstance(value, float):
        return None
    return str(value).strip() or None


def clean(df_raw: pd.DataFrame) -> list[dict]:
    """
    Apply cleaning rules to raw records.
    Returns a list of cleaned dicts — one per kept product.
    """
    kept = []
    dropped = {"missing_asin": 0, "missing_title": 0, "short_title": 0}

    for _, row in df_raw.iterrows():
        asin = safe_str(row.get("parent_asin"))
        if not asin:
            dropped["missing_asin"] += 1
            continue

        title = row.get("title")
        if not title:
            dropped["missing_title"] += 1
            continue

        title = str(title).strip()
        if len(title) < MIN_TITLE_LENGTH:
            dropped["short_title"] += 1
            log.debug("Dropping short title: %r", title)
            continue

        price = parse_price(row.get("price"))
        description_text = flatten_list_field(row.get("description"))
        features_text = flatten_list_field(row.get("features"))
        brand = safe_str(row.get("store")) or "Unknown"
        avg_rating = row.get("average_rating")
        rating_num = row.get("rating_number")

        search_text = " ".join(filter(None, [
            title,
            features_text,
            description_text,
            brand,
        ]))

        kept.append({
            "parent_asin": asin,
            "title": title,
            "brand": brand,
            "price": price,
            "has_price": price is not None,
            "average_rating": None if pd.isna(avg_rating) else avg_rating,
            "rating_number": 0 if pd.isna(rating_num) else int(rating_num),
            "description_text": description_text,
            "features_text": features_text,
            "search_text": search_text,
            "main_category": safe_str(row.get("main_category")),
        })

    log.info(
        "Kept %d products. Dropped: %s",
        len(kept),
        ", ".join(f"{v} {k}" for k, v in dropped.items() if v > 0) or "none",
    )
    return kept


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("Loading %s", RAW_PATH)
    df_raw = pq.read_table(RAW_PATH).to_pandas()
    log.info("Loaded %d rows", len(df_raw))

    records = clean(df_raw)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(records, schema=SCHEMA), OUTPUT_PATH)
    log.info("Wrote %d rows to %s", len(records), OUTPUT_PATH)

    df_out = pd.DataFrame(records)
    has_price = df_out["has_price"].sum()
    print("\n--- Clean Product Stats ---")
    print(f"  Total products    : {len(df_out)}")
    pct_str = f"{has_price / len(df_out) * 100:.1f}%" if len(df_out) else "N/A"
    print(f"  Has price         : {has_price} ({pct_str})")
    print(f"  Missing price     : {len(df_out) - has_price}")
    print(f"  Avg search_text   : {df_out['search_text'].str.len().mean():.0f} chars")
    print(f"  Columns           : {df_out.columns.tolist()}")
    print(f"  Sample titles     :")
    for t in df_out["title"].head(5):
        print(f"    • {t[:80]}")


if __name__ == "__main__":
    main()