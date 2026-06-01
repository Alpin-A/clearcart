import pytest
from search.query_parser import parse


# 1. Budget extracted correctly for each pattern variant
@pytest.mark.parametrize("query,expected", [
    ("headphones under $200", 200.0),
    ("headphones under 200", 200.0),
    ("headphones below $150", 150.0),
    ("headphones below 150", 150.0),
    ("less than $300 headphones", 300.0),
    ("less than 300 headphones", 300.0),
    ("up to $250 earbuds", 250.0),
    ("up to 250 earbuds", 250.0),
    ("max $100 headphones", 100.0),
    ("max 100 headphones", 100.0),
    ("budget of $400", 400.0),
    ("budget of 400", 400.0),
    ("no more than $180", 180.0),
    ("no more than 180", 180.0),
    ("$75 or less", 75.0),
    ("75 or less", 75.0),
])
def test_budget_extracted(query, expected):
    assert parse(query).budget == expected


# 2. No budget returns None
def test_no_budget_returns_none():
    result = parse("best noise cancelling headphones for commuting")
    assert result.budget is None


# 3. Brand exclusion from "avoid gaming headphones"
def test_brand_exclusion_avoid():
    result = parse("avoid gaming headphones")
    assert "gaming" in result.brand_exclusions


# 4. Preferences detected: noise cancelling, long battery, comfortable
def test_preferences_detected():
    result = parse("noise cancelling headphones with long battery life and comfortable fit")
    prefs = result.preferences
    assert any("noise cancell" in p for p in prefs)
    assert any("long battery" in p or "battery life" in p for p in prefs)
    assert any("comfort" in p for p in prefs)


# 5. clean_query removes price phrase but keeps rest intact
def test_clean_query_removes_budget_phrase():
    result = parse("noise cancelling headphones under $200 for studying")
    assert "noise cancelling headphones" in result.clean_query
    assert "for studying" in result.clean_query
    assert "$200" not in result.clean_query
    assert "under" not in result.clean_query


# 6. Query with no constraints: clean_query == raw query stripped
def test_clean_query_no_constraints():
    query = "  wireless headphones for running  "
    result = parse(query)
    assert result.clean_query == query.strip()
