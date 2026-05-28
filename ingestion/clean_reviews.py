"""
Inputs:  data/raw/reviews_sample.parquet   (path from config reviews.output_path)
Outputs: data/processed/reviews_clean.parquet (path from config reviews.output_path_clean)
"""
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from dotenv import load_dotenv

log = logging.getLogger(__name__)

SCHEMA = pa.schema([
    pa.field("parent_asin", pa.string()),
    pa.field("rating", pa.float32()),
    pa.field("sentiment", pa.string()),
    pa.field("review_title", pa.string()),
    pa.field("text", pa.string()),
    pa.field("word_count", pa.int32()),
    pa.field("helpful_vote", pa.int32()),
    pa.field("verified_purchase", pa.bool_()),
    pa.field("timestamp", pa.int64()),
])


def clean(df: pd.DataFrame, min_word_count: int) -> pd.DataFrame:
    n_in = len(df)

    mask = df["word_count"] >= min_word_count
    n_dropped = (~mask).sum()
    df = df[mask].copy()

    df["rating"] = df["rating"].clip(1.0, 5.0).astype("float32")
    df["helpful_vote"] = df["helpful_vote"].clip(lower=0).astype("int32")

    df["sentiment"] = np.select(
        [df["rating"] >= 4.0, df["rating"] <= 2.0],
        ["positive", "negative"],
        default="neutral",
    )

    log.info(
        "Kept %d reviews. Dropped %d (word_count < %d).",
        len(df), n_dropped, min_word_count,
    )
    return df


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

    reviews_cfg = cfg["reviews"]
    input_path = Path(reviews_cfg["output_path"])
    output_path = Path(reviews_cfg["output_path_clean"])
    min_word_count = int(reviews_cfg["min_word_count"])

    log.info("Loading %s", input_path)
    df_raw = pq.read_table(input_path).to_pandas()
    log.info("Loaded %d rows", len(df_raw))

    df_clean = clean(df_raw, min_word_count)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df_clean[list(SCHEMA.names)], schema=SCHEMA, preserve_index=False)
    pq.write_table(table, output_path)
    log.info("Wrote %d rows to %s", len(df_clean), output_path)

    sentiment_counts = df_clean["sentiment"].value_counts()
    print("\n--- Clean Review Stats ---")
    print(f"  Input rows        : {len(df_raw)}")
    print(f"  Kept rows         : {len(df_clean)}")
    print(f"  Dropped rows      : {len(df_raw) - len(df_clean)}")
    print(f"  Avg word count    : {df_clean['word_count'].mean():.1f}")
    print(f"  Sentiment dist    :")
    for label, count in sentiment_counts.items():
        pct = count / len(df_clean) * 100
        print(f"    {label:<10}: {count:>6}  ({pct:.1f}%)")


if __name__ == "__main__":
    main()
