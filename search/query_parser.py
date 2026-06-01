import re
from dataclasses import dataclass, field

PREFERENCE_TERMS = [
    "noise cancell", "active noise", "anc",
    "long battery", "battery life",
    "comfortable", "comfort",
    "wireless", "bluetooth",
    "wired",
    "foldable", "folding",
    "lightweight", "light weight",
    "waterproof", "water resistant",
    "bass", "deep bass",
    "studio", "flat response",
    "gaming",
    "workout", "running", "gym",
    "studying", "study", "focus",
    "commuting", "travel",
    "over ear", "over-ear",
    "on ear", "on-ear",
    "in ear", "in-ear",
    "true wireless", "tws",
    "microphone", "mic",
    "kids", "children",
    "volume limit",
]

_BUDGET_PATTERNS = [
    r"(?:under|below)\s+\$?([\d]+(?:\.\d+)?)",
    r"less\s+than\s+\$?([\d]+(?:\.\d+)?)",
    r"up\s+to\s+\$?([\d]+(?:\.\d+)?)",
    r"max\s+\$?([\d]+(?:\.\d+)?)",
    r"budget\s+of\s+\$?([\d]+(?:\.\d+)?)",
    r"no\s+more\s+than\s+\$?([\d]+(?:\.\d+)?)",
    r"\$?([\d]+(?:\.\d+)?)\s+or\s+less",
]

_BUDGET_COMPILED = [(re.compile(p, re.IGNORECASE), p) for p in _BUDGET_PATTERNS]

_EXCLUSION_PATTERNS = [
    re.compile(r"\bavoid\s+(\w+(?:\s+\w+)*?)(?=\s+(?:headphones?|earbuds?|products?|brand|$)|\s*$)", re.IGNORECASE),
    re.compile(r"\bno\s+(\w+)\s+(?:headphones?|earbuds?|products?|brand)", re.IGNORECASE),
    re.compile(r"\bnot\s+(\w+)", re.IGNORECASE),
    re.compile(r"\bexclude\s+(\w+)", re.IGNORECASE),
    re.compile(r"\bwithout\s+(\w+)", re.IGNORECASE),
]

# Combined pattern for stripping budget phrases from clean_query
_BUDGET_STRIP_PATTERN = re.compile(
    r"(?:"
    r"(?:under|below)\s+\$?[\d]+(?:\.\d+)?"
    r"|less\s+than\s+\$?[\d]+(?:\.\d+)?"
    r"|up\s+to\s+\$?[\d]+(?:\.\d+)?"
    r"|max\s+\$?[\d]+(?:\.\d+)?"
    r"|budget\s+of\s+\$?[\d]+(?:\.\d+)?"
    r"|no\s+more\s+than\s+\$?[\d]+(?:\.\d+)?"
    r"|\$?[\d]+(?:\.\d+)?\s+or\s+less"
    r")",
    re.IGNORECASE,
)


@dataclass
class ParsedQuery:
    raw: str
    budget: float | None
    brand_exclusions: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    clean_query: str = ""


def _extract_budget(query: str) -> float | None:
    for compiled, _ in _BUDGET_COMPILED:
        m = compiled.search(query)
        if m:
            return float(m.group(1))
    return None


def _extract_brand_exclusions(query: str) -> list[str]:
    results: list[str] = []
    for pattern in _EXCLUSION_PATTERNS:
        for m in pattern.finditer(query):
            term = m.group(1).strip().lower()
            if term and term not in results:
                results.append(term)
    return results


def _extract_preferences(query: str) -> list[str]:
    lower = query.lower()
    return [term for term in PREFERENCE_TERMS if term in lower]


def _clean_query(query: str) -> str:
    cleaned = _BUDGET_STRIP_PATTERN.sub("", query)
    # Collapse multiple spaces left behind
    cleaned = re.sub(r" {2,}", " ", cleaned).strip()
    return cleaned


def parse(query: str) -> ParsedQuery:
    return ParsedQuery(
        raw=query,
        budget=_extract_budget(query),
        brand_exclusions=_extract_brand_exclusions(query),
        preferences=_extract_preferences(query),
        clean_query=_clean_query(query),
    )