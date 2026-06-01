import pytest
from search.rank import (
    compute_fit_score,
    price_fit_score,
    rank_results,
    rating_confidence_score,
)


def make_product(price=50.0, has_price=True, avg_rating=4.0, rating_number=100):
    return {
        "title": "Test Product",
        "brand": "TestBrand",
        "price": price,
        "has_price": has_price,
        "average_rating": avg_rating,
        "rating_number": rating_number,
    }


def make_aggregates(evidence_score=0.6, complaint_rate=0.1, avg_rating=4.0, review_count=80):
    import json
    return {
        "evidence_score": evidence_score,
        "complaint_rate": complaint_rate,
        "avg_rating": avg_rating,
        "review_count": review_count,
        "top_pros": json.dumps(["great sound", "comfortable fit"]),
        "top_cons": json.dumps(["short cable"]),
    }


# 1. Product over budget scores 0.0 price_fit
def test_price_fit_over_budget():
    assert price_fit_score(price=220.0, budget=200.0) == 0.0


def test_price_fit_just_over_budget_threshold():
    # 200 * 1.05 = 210; price=211 should be 0.0
    assert price_fit_score(price=211.0, budget=200.0) == 0.0


def test_price_fit_at_threshold_edge():
    # price == budget * 1.05 exactly → 0.0 (strictly greater, so this returns 1.0)
    assert price_fit_score(price=210.0, budget=200.0) == 1.0


# 2. Product with no price scores 0.3 price_fit
def test_price_fit_no_price():
    assert price_fit_score(price=None, budget=100.0) == 0.3


def test_price_fit_no_price_no_budget():
    assert price_fit_score(price=None, budget=None) == 0.5


# 3. Product with no aggregates uses neutral defaults without crashing
def test_compute_fit_score_no_aggregates():
    product = make_product(price=80.0)
    score = compute_fit_score(
        asin="B001",
        rrf_score=0.03,
        rrf_max=0.03,
        product=product,
        aggregates=None,
        budget=100.0,
    )
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_rank_results_no_aggregates_does_not_crash():
    products = {"B001": make_product(price=80.0)}
    results = rank_results([("B001", 0.03)], products, {}, budget=100.0)
    assert len(results) == 1
    assert results[0]["evidence_score"] == 0.3
    assert results[0]["complaint_rate"] == 0.0


# 4. fit_score is always between 0 and 100
def test_fit_score_bounds_high_complaint():
    product = make_product(price=500.0)
    aggs = make_aggregates(complaint_rate=1.0, evidence_score=0.0)
    score = compute_fit_score("B002", 0.001, 0.03, product, aggs, budget=100.0)
    assert 0.0 <= score <= 100.0


def test_fit_score_bounds_perfect():
    product = make_product(price=90.0)
    aggs = make_aggregates(complaint_rate=0.0, evidence_score=1.0, avg_rating=5.0, review_count=10000)
    score = compute_fit_score("B003", 0.03, 0.03, product, aggs, budget=100.0)
    assert 0.0 <= score <= 100.0


def test_fit_score_range_across_many_combos():
    rrf_max = 0.05
    for rrf in [0.001, 0.01, 0.03, 0.05]:
        for price in [10.0, 50.0, 100.0, 200.0]:
            for budget in [None, 50.0, 100.0]:
                product = make_product(price=price)
                aggs = make_aggregates()
                score = compute_fit_score("B999", rrf, rrf_max, product, aggs, budget)
                assert 0.0 <= score <= 100.0, f"out of range: {score} (price={price}, budget={budget})"


# 5. rank_results returns results sorted by fit_score descending
def test_rank_results_sorted_descending():
    products = {
        "B001": make_product(price=50.0),
        "B002": make_product(price=90.0),
        "B003": make_product(price=200.0),
    }
    aggregates = {
        "B001": make_aggregates(evidence_score=0.3, complaint_rate=0.5),
        "B002": make_aggregates(evidence_score=0.8, complaint_rate=0.05),
        "B003": make_aggregates(evidence_score=0.1, complaint_rate=0.8),
    }
    rrf_results = [("B001", 0.02), ("B002", 0.03), ("B003", 0.01)]
    results = rank_results(rrf_results, products, aggregates, budget=100.0)

    scores = [r["fit_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_rank_results_empty_input():
    assert rank_results([], {}, {}, budget=None) == []


def test_rank_results_result_fields():
    import json
    products = {"B001": make_product(price=80.0)}
    aggregates = {"B001": make_aggregates()}
    results = rank_results([("B001", 0.03)], products, aggregates, budget=100.0)
    r = results[0]
    assert r["asin"] == "B001"
    assert isinstance(r["top_pros"], list)
    assert isinstance(r["top_cons"], list)
    assert isinstance(r["over_budget"], bool)
    assert r["has_price"] is True
