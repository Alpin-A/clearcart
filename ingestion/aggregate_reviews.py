"""
Inputs:  data/processed/reviews_clean.parquet
         data/processed/products_clean.parquet  (for valid ASIN filter)
Output:  data/aggregates/product_aggregates.parquet

Sanity check:
    import pyarrow.parquet as pq, json
    df = pq.read_table("data/aggregates/product_aggregates.parquet").to_pandas()
    print(df.shape)                           # expect (4062, 22)
    print(df["evidence_score"].describe())
    print(df["complaint_rate"].describe())
    print(df.isnull().sum())
    sample = df[df["review_count"] >= 20].iloc[0]
    print(json.loads(sample["top_pros"]))
    print(json.loads(sample["top_cons"]))
"""
import argparse
import json
import logging
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from dotenv import load_dotenv

log = logging.getLogger(__name__)

DOMAIN_TERMS = {
    "comfort":            ["comfort", "comfortable", "cushion", "padding", "clamping"],
    "audio_quality":      ["bass", "treble", "sound", "audio", "balanced"],
    "noise_cancellation": ["noise cancell", "anc", "isolation"],
    "battery":            ["battery", "battery life", "hours", "charge"],
    "connectivity":       ["bluetooth", "wireless", "pairing", "dropout", "lag"],
    "durability":         ["durable", "build quality", "broke", "lasted"],
    "microphone":         ["mic", "microphone", "call quality"],
    "portability":        ["portable", "lightweight", "travel", "folding"],
}

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "they", "have",
    "but", "are", "not", "was", "its", "very", "it", "is", "a",
    "to", "of", "in", "i", "my", "you", "your", "really", "just",
    "so", "them", "these", "those", "been", "has", "had",
    "got", "get", "too", "also", "even", "like", "good", "great",
    "nice", "love", "work", "use", "used", "well", "would", "could",
}

SCHEMA = pa.schema([
    pa.field("parent_asin",         pa.string()),
    pa.field("review_count",        pa.int32()),
    pa.field("positive_count",      pa.int32()),
    pa.field("negative_count",      pa.int32()),
    pa.field("neutral_count",       pa.int32()),
    pa.field("avg_rating",          pa.float32()),
    pa.field("rating_std",          pa.float32()),
    pa.field("complaint_rate",      pa.float32()),
    pa.field("rating_confidence",   pa.float32()),
    pa.field("avg_word_count",      pa.float32()),
    pa.field("verified_rate",       pa.float32()),
    pa.field("avg_helpful_votes",   pa.float32()),
    pa.field("helpful_review_rate", pa.float32()),
    pa.field("avg_specificity",     pa.float32()),
    pa.field("evidence_score",      pa.float32()),
    pa.field("ratings_1star",       pa.int32()),
    pa.field("ratings_2star",       pa.int32()),
    pa.field("ratings_3star",       pa.int32()),
    pa.field("ratings_4star",       pa.int32()),
    pa.field("ratings_5star",       pa.int32()),
    pa.field("top_pros",            pa.string()),
    pa.field("top_cons",            pa.string()),
])


def compute_specificity(texts: pd.Series) -> pd.Series:
    """Vectorized per-review specificity: fraction of domain categories hit."""
    lower = texts.str.lower().fillna("")
    n_cats = len(DOMAIN_TERMS)
    hits = pd.DataFrame(index=texts.index)
    for cat, terms in DOMAIN_TERMS.items():
        pattern = "|".join(re.escape(t) for t in terms)
        hits[cat] = lower.str.contains(pattern, na=False).astype(float)
    return hits.sum(axis=1) / n_cats


def extract_top_phrases(texts: pd.Series, top_n: int = 5) -> list[str]:
    """Return top 2/3-gram phrases by frequency from a series of review texts."""
    counter: Counter = Counter()
    for text in texts:
        if not isinstance(text, str):
            continue
        tokens = [t for t in re.split(r"\W+", text.lower()) if t]
        for n in (2, 3):
            for i in range(len(tokens) - n + 1):
                counter[" ".join(tokens[i : i + n])] += 1

    results = []
    for phrase, freq in counter.most_common():
        if freq < 2:
            break
        if len(phrase) < 6:
            continue
        if all(w in STOPWORDS for w in phrase.split()):
            continue
        results.append(phrase)
        if len(results) == top_n:
            break
    return results


def agg_product(group: pd.DataFrame) -> pd.Series:
    review_count   = len(group)
    positive_count = int((group["sentiment"] == "positive").sum())
    negative_count = int((group["sentiment"] == "negative").sum())
    neutral_count  = int((group["sentiment"] == "neutral").sum())

    avg_rating = float(group["rating"].mean())
    rating_std = float(group["rating"].std(ddof=1)) if review_count > 1 else 0.0
    if np.isnan(rating_std):
        rating_std = 0.0

    star_counts = group["rating"].round(0).clip(1, 5).astype(int).value_counts()

    complaint_rate    = float(negative_count / review_count)
    rating_confidence = float(
        np.clip(avg_rating * np.log(review_count + 1) / np.log(500), 0.0, 1.0)
    )

    avg_word_count      = float(group["word_count"].mean())
    verified_rate       = float(group["verified_purchase"].mean())
    avg_helpful_votes   = float(group["helpful_vote"].mean())
    helpful_review_rate = float((group["helpful_vote"] > 0).mean())
    avg_specificity     = float(group["_specificity"].mean())

    length_score  = min(avg_word_count / 150.0, 1.0)
    helpful_score = min(avg_helpful_votes / 10.0, 1.0)
    evidence_score = float(
        0.25 * length_score
        + 0.25 * helpful_score
        + 0.25 * verified_rate
        + 0.25 * avg_specificity
    )

    top_pros = json.dumps(extract_top_phrases(group.loc[group["rating"] >= 4, "text"]))
    top_cons = json.dumps(extract_top_phrases(group.loc[group["rating"] <= 2, "text"]))

    return pd.Series({
        "review_count":        review_count,
        "positive_count":      positive_count,
        "negative_count":      negative_count,
        "neutral_count":       neutral_count,
        "avg_rating":          avg_rating,
        "rating_std":          rating_std,
        "complaint_rate":      complaint_rate,
        "rating_confidence":   rating_confidence,
        "avg_word_count":      avg_word_count,
        "verified_rate":       verified_rate,
        "avg_helpful_votes":   avg_helpful_votes,
        "helpful_review_rate": helpful_review_rate,
        "avg_specificity":     avg_specificity,
        "evidence_score":      evidence_score,
        "ratings_1star":       int(star_counts.get(1, 0)),
        "ratings_2star":       int(star_counts.get(2, 0)),
        "ratings_3star":       int(star_counts.get(3, 0)),
        "ratings_4star":       int(star_counts.get(4, 0)),
        "ratings_5star":       int(star_counts.get(5, 0)),
        "top_pros":            top_pros,
        "top_cons":            top_cons,
    })


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

    reviews_path  = Path(cfg["reviews"]["output_path_clean"])
    products_path = Path("data/processed/products_clean.parquet")
    output_path   = Path(cfg["aggregates"]["output_path"])

    log.info("Loading products from %s", products_path)
    valid_asins = set(
        pq.read_table(products_path, columns=["parent_asin"])
        .column("parent_asin")
        .to_pylist()
    )
    log.info("Loaded %d valid ASINs", len(valid_asins))

    log.info("Loading reviews from %s", reviews_path)
    reviews = pq.read_table(reviews_path).to_pandas()
    log.info("Loaded %d reviews", len(reviews))

    reviews = reviews[reviews["parent_asin"].isin(valid_asins)].copy()
    n_products = reviews["parent_asin"].nunique()
    log.info(
        "Aggregating %d products (%d reviews after ASIN filter)",
        n_products,
        len(reviews),
    )

    log.info("Computing per-review specificity scores (vectorized)")
    reviews["_specificity"] = compute_specificity(reviews["text"])

    log.info("Running groupby aggregation")
    try:
        agg_df = reviews.groupby("parent_asin", sort=False).apply(
            agg_product, include_groups=False
        )
    except TypeError:
        agg_df = reviews.groupby("parent_asin", sort=False).apply(agg_product)

    agg_df = agg_df.reset_index()
    agg_df = agg_df[list(SCHEMA.names)]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(agg_df, schema=SCHEMA, preserve_index=False)
    pq.write_table(table, output_path)
    log.info("Wrote %d rows to %s", len(agg_df), output_path)

    print("\n--- Product Aggregates Summary ---")
    print(f"  Products aggregated  : {len(agg_df)}")
    print(f"  Total reviews used   : {len(reviews)}")
    print(f"  Columns              : {len(agg_df.columns)}")
    print(f"\n  evidence_score:")
    for label, val in agg_df["evidence_score"].describe().items():
        print(f"    {label:<6} = {val:.3f}")
    print(f"\n  complaint_rate:")
    for label, val in agg_df["complaint_rate"].describe().items():
        print(f"    {label:<6} = {val:.3f}")
    null_counts = agg_df.isnull().sum()
    if null_counts.any():
        print(f"\n  Nulls: {null_counts[null_counts > 0].to_dict()}")
    else:
        print("\n  No null values")


if __name__ == "__main__":
    main()
