import json
import math


def price_fit_score(price: float | None, budget: float | None) -> float:
    if budget is None:
        return 0.5
    if price is None:
        return 0.3
    if price > budget * 1.05:
        return 0.0
    if price >= budget * 0.70:
        return 1.0
    return max(0.1, price / (budget * 0.70))


def rating_confidence_score(avg_rating: float | None, review_count: int) -> float:
    if avg_rating is None or review_count == 0:
        return 0.0
    # Normalize rating to 0-1 first (maps 1-5 star range to 0-1)
    rating_norm = (avg_rating - 1.0) / 4.0
    # Weight by log review count normalized to our 0-100 review cap
    count_weight = math.log(review_count + 1) / math.log(101)
    return round(min(rating_norm * count_weight, 1.0), 4)


def compute_fit_score(
    asin: str,
    rrf_score: float,
    rrf_max: float,
    product: dict,
    aggregates: dict | None,
    budget: float | None,
) -> float:
    if aggregates is not None:
        evidence_score = float(aggregates.get("evidence_score", 0.3))
        complaint_rate = float(aggregates.get("complaint_rate", 0.0))
        avg_rating = aggregates.get("avg_rating")
        review_count = int(aggregates.get("review_count", 0))
    else:
        evidence_score = 0.3
        complaint_rate = 0.0
        avg_rating = product.get("average_rating")
        review_count = int(product.get("rating_number", 0))

    price = product["price"] if product.get("has_price") else None

    fit = (
        0.40 * (rrf_score / rrf_max)
        + 0.25 * evidence_score
        + 0.20 * price_fit_score(price, budget)
        + 0.15 * rating_confidence_score(avg_rating, review_count)
        - 0.10 * complaint_rate
    ) * 100

    return round(max(0.0, min(100.0, fit)), 1)


def rank_results(
    rrf_results: list[tuple[str, float]],
    products_lookup: dict[str, dict],
    aggregates_lookup: dict[str, dict],
    budget: float | None,
) -> list[dict]:
    if not rrf_results:
        return []

    rrf_max = max(score for _, score in rrf_results)

    results: list[dict] = []
    for asin, rrf_score in rrf_results:
        product = products_lookup.get(asin, {})
        aggregates = aggregates_lookup.get(asin)

        if aggregates is not None:
            evidence_score = float(aggregates.get("evidence_score", 0.3))
            complaint_rate = float(aggregates.get("complaint_rate", 0.0))
            avg_rating = aggregates.get("avg_rating")
            review_count = int(aggregates.get("review_count", 0))
            raw_pros = aggregates.get("top_pros", "[]")
            raw_cons = aggregates.get("top_cons", "[]")
        else:
            evidence_score = 0.3
            complaint_rate = 0.0
            avg_rating = product.get("average_rating")
            review_count = int(product.get("rating_number", 0))
            raw_pros = "[]"
            raw_cons = "[]"

        price = product.get("price") if product.get("has_price") else None

        top_pros: list[str] = json.loads(raw_pros) if raw_pros else []
        top_cons: list[str] = json.loads(raw_cons) if raw_cons else []

        price_fit = price_fit_score(price, budget)
        rating_conf = rating_confidence_score(avg_rating, review_count)
        fit_score = compute_fit_score(asin, rrf_score, rrf_max, product, aggregates, budget)

        results.append({
            "asin": asin,
            "title": product.get("title", ""),
            "brand": product.get("brand", ""),
            "price": price,
            "has_price": bool(product.get("has_price", False)),
            "avg_rating": float(avg_rating) if avg_rating is not None else None,
            "review_count": review_count,
            "fit_score": fit_score,
            "rrf_score": rrf_score,
            "evidence_score": evidence_score,
            "complaint_rate": complaint_rate,
            "price_fit": price_fit,
            "rating_confidence": rating_conf,
            "over_budget": bool(price is not None and budget is not None and price > budget),
            "top_pros": top_pros,
            "top_cons": top_cons,
        })

    results.sort(key=lambda r: r["fit_score"], reverse=True)
    return results
