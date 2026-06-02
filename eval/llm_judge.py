"""
LLM-as-judge: generate relevance labels using Claude and compute Cohen's kappa
inter-rater agreement against the human labels in eval/benchmark_queries.json.

Run:
    python -m eval.llm_judge
"""
import copy
import json
import logging
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

log = logging.getLogger(__name__)

BENCHMARK_PATH = Path("eval/benchmark_queries.json")
LABELS_PATH = Path("eval/llm_labels.json")

# Cached at the system-prompt level across all 400 calls.
SYSTEM_PROMPT = """\
You are evaluating search result relevance for an e-commerce search engine. \
Rate the relevance of a product to a query on a 0-2 scale:
0 = irrelevant (wrong product type, clearly doesn't match)
1 = acceptable (matches category, partially fits)
2 = good match (clearly fits query intent, constraints, preferences)
Return ONLY the integer 0, 1, or 2. Nothing else.\
"""


def cohen_kappa(human: list[int], llm: list[int]) -> float:
    n = len(human)
    po = sum(h == l for h, l in zip(human, llm)) / n
    pe = sum((human.count(k) / n) * (llm.count(k) / n) for k in (0, 1, 2))
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def interpret_kappa(kappa: float) -> str:
    if kappa < 0.20:
        return "slight agreement"
    if kappa < 0.40:
        return "fair agreement"
    if kappa < 0.60:
        return "moderate agreement"
    if kappa < 0.80:
        return "substantial agreement"
    return "almost perfect agreement"


def label_pair(client: anthropic.Anthropic, query: str, title: str) -> int:
    user_text = f"Query: {query}\nProduct: {title}\nRelevance (0, 1, or 2):"
    raw = ""
    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=10,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_text}],
            )
            raw = response.content[0].text.strip()
            label = int(raw)
            if label not in (0, 1, 2):
                raise ValueError(f"out of range: {label}")
            return label
        except anthropic.RateLimitError as e:
            wait = 60 * (attempt + 1)
            log.warning("Rate limited (%s) — waiting %ds", e, wait)
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            wait = 30 * (attempt + 1)
            log.warning("API error %d (%s) — waiting %ds", e.status_code, e.message, wait)
            time.sleep(wait)
        except (ValueError, IndexError):
            log.warning("Unexpected response %r — defaulting to 1", raw)
            return 1

    log.error("All 3 retries failed — defaulting to 1")
    return 1


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    load_dotenv()

    client = anthropic.Anthropic()

    with open(BENCHMARK_PATH) as f:
        data = json.load(f)

    output = copy.deepcopy(data)
    human_labels: list[int] = []
    llm_labels: list[int] = []

    total = sum(len(q["results"]) for q in data["queries"])
    done = 0

    for qi, q in enumerate(data["queries"]):
        query = q["query"]
        for ri, result in enumerate(q["results"]):
            done += 1
            log.info(
                "[%3d/%d] Q%-2d R%-2d  %s",
                done, total, q["id"], result["rank"], query[:55],
            )

            label = label_pair(client, query, result["title"])

            human_labels.append(result["relevance"])
            llm_labels.append(label)
            output["queries"][qi]["results"][ri]["llm_relevance"] = label

            time.sleep(0.5)

    LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LABELS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    kappa = cohen_kappa(human_labels, llm_labels)
    agreement = sum(h == l for h, l in zip(human_labels, llm_labels)) / len(human_labels)

    print()
    print("Inter-rater Agreement (Human vs LLM)")
    print(f"Total pairs: {len(human_labels)}")
    print(f"Agreement: {agreement * 100:.1f}%")
    print(f"Cohen's kappa: {kappa:.2f} ({interpret_kappa(kappa)})")

    log.info("LLM labels saved to %s", LABELS_PATH)


if __name__ == "__main__":
    main()
