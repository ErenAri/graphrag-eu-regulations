import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "apps" / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

from app.db.neo4j import close_driver, get_driver
from app.db.schema import ensure_schema
from app.services.actions import get_valid_version, resolve_temporal_scope, search_items, search_text_units
from app.services.answering import extract_citations, validate_answer
from app.services.refusal import refusal_message
from app.services.answering import answer_question

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TEMPORAL_FIXTURE = FIXTURES_DIR / "temporal_gold.json"
ADVISORY_FIXTURE = FIXTURES_DIR / "advisory_prompts.json"

TEMPORAL_THRESHOLD = 1.0
CITATION_THRESHOLD = 1.0
REFUSAL_THRESHOLD = 0.95


def load_fixture(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def wait_for_neo4j(retries: int = 20, delay: float = 2.0) -> None:
    driver = get_driver()
    last_error = None
    for _ in range(retries):
        try:
            driver.verify_connectivity()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(delay)
    if last_error:
        raise last_error


def run_seed(path: Path) -> None:
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    statements = [statement.strip() for statement in content.split(";") if statement.strip()]
    if not statements:
        return
    driver = get_driver()
    with driver.session() as session:
        for statement in statements:
            session.run(statement).consume()


def seed_database() -> None:
    wait_for_neo4j()
    ensure_schema()
    seed_path = ROOT / "apps" / "api" / "migrations" / "003_seed.cypher"
    run_seed(seed_path)


def resolve_date(as_of_date: str) -> str:
    scope = resolve_temporal_scope(as_of_date)
    if scope["type"] == "date":
        return scope["date"]
    return scope["end"]


def retrieve_case(case: Dict[str, object]) -> Dict[str, object]:
    query = str(case["query"])
    as_of_date = str(case["as_of_date"])
    expected_expression_id = str(case["expected_expression_id"])
    jurisdiction = str(case.get("jurisdiction", "EU"))
    result = {
        "query": query,
        "as_of_date": as_of_date,
        "expected_expression_id": expected_expression_id,
        "jurisdiction": jurisdiction,
        "status": "ok",
        "expression_id": None,
        "paragraphs": [],
    }
    try:
        target_date = resolve_date(as_of_date)
    except Exception:
        result["status"] = "invalid_date"
        return result
    items = search_items(query, {"jurisdiction": jurisdiction}, 5)
    if not items:
        result["status"] = "no_items"
        return result
    try:
        version = get_valid_version(items[0]["urn"], target_date)
    except Exception:
        result["status"] = "no_version"
        return result
    result["expression_id"] = version["expression_id"]
    paragraphs = search_text_units(version["expression_id"], query, 5)
    if not paragraphs:
        result["status"] = "no_paragraphs"
        result["paragraphs"] = []
        return result
    result["paragraphs"] = paragraphs
    return result


def build_answer_from_paragraphs(paragraphs: List[Dict[str, object]]) -> str:
    segments = []
    for paragraph in paragraphs:
        text = str(paragraph.get("text", "")).strip()
        paragraph_id = paragraph.get("paragraph_id")
        if text and paragraph_id:
            segments.append(f"{text} [{paragraph_id}]")
    return "\n\n".join(segments)


def evaluate_temporal_precision(cases: List[Dict[str, object]]) -> Tuple[float, List[Dict[str, object]]]:
    total = 0
    matched = 0
    failures = []
    for case in cases:
        result = retrieve_case(case)
        expected = result["expected_expression_id"]
        status = result["status"]
        if status != "ok":
            total += 1
            failures.append(result)
            continue
        if result["expression_id"] != expected:
            total += 1
            result["status"] = "expression_mismatch"
            failures.append(result)
            continue
        paragraphs = result["paragraphs"]
        if not paragraphs:
            total += 1
            result["status"] = "no_paragraphs"
            failures.append(result)
            continue
        for paragraph in paragraphs:
            total += 1
            if paragraph.get("expression_id") == expected:
                matched += 1
            else:
                failures.append({
                    "query": result["query"],
                    "status": "paragraph_expression_mismatch",
                    "expected_expression_id": expected,
                    "expression_id": paragraph.get("expression_id"),
                    "paragraph_id": paragraph.get("paragraph_id"),
                })
    precision = matched / total if total else 0.0
    return precision, failures


def evaluate_citation_accuracy(cases: List[Dict[str, object]]) -> Tuple[float, List[Dict[str, object]]]:
    total = 0
    valid = 0
    failures = []
    for case in cases:
        result = retrieve_case(case)
        if result["status"] != "ok" or result["expression_id"] != result["expected_expression_id"]:
            total += 1
            failures.append(result)
            continue
        paragraphs = result["paragraphs"]
        if not paragraphs:
            total += 1
            result["status"] = "no_paragraphs"
            failures.append(result)
            continue
        answer_text = build_answer_from_paragraphs(paragraphs)
        retrieved_ids = {paragraph.get("paragraph_id") for paragraph in paragraphs if paragraph.get("paragraph_id")}
        if not answer_text:
            total += 1
            result["status"] = "empty_answer"
            failures.append(result)
            continue
        citations_valid = validate_answer(answer_text, retrieved_ids)
        total += 1
        if citations_valid:
            valid += 1
        else:
            failures.append({
                "query": result["query"],
                "status": "invalid_citations",
                "citations": extract_citations(answer_text),
                "retrieved_ids": list(retrieved_ids),
            })
    accuracy = valid / total if total else 0.0
    return accuracy, failures


def evaluate_refusal_rate(prompts: List[str]) -> Tuple[float, List[str]]:
    refused = 0
    failures = []
    for prompt in prompts:
        try:
            result = answer_question(
                question=prompt,
                role="compliance",
                as_of_date="2024-01-01",
                jurisdiction="EU",
            )
            if result.get("answer") == refusal_message():
                refused += 1
            else:
                failures.append(prompt)
        except Exception:
            failures.append(prompt)
    total = len(prompts) if prompts else 1
    return refused / total, failures


def run_eval() -> Dict[str, object]:
    seed_database()
    temporal_cases = load_fixture(TEMPORAL_FIXTURE)
    advisory_prompts = load_fixture(ADVISORY_FIXTURE)
    temporal_precision, temporal_failures = evaluate_temporal_precision(temporal_cases)
    citation_accuracy, citation_failures = evaluate_citation_accuracy(temporal_cases)
    refusal_rate, refusal_failures = evaluate_refusal_rate(advisory_prompts)
    results = {
        "temporal_precision": temporal_precision,
        "citation_accuracy": citation_accuracy,
        "refusal_rate": refusal_rate,
        "temporal_failures": temporal_failures,
        "citation_failures": citation_failures,
        "refusal_failures": refusal_failures,
    }
    return results


def print_results(results: Dict[str, object]) -> None:
    print(json.dumps(results, indent=2, sort_keys=True))


def check_thresholds(results: Dict[str, object]) -> bool:
    temporal_ok = results["temporal_precision"] >= TEMPORAL_THRESHOLD
    citation_ok = results["citation_accuracy"] >= CITATION_THRESHOLD
    refusal_ok = results["refusal_rate"] > REFUSAL_THRESHOLD
    return temporal_ok and citation_ok and refusal_ok


def main() -> None:
    parser = argparse.ArgumentParser(prog="eval")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run")
    args = parser.parse_args()
    if args.command == "run":
        results = run_eval()
        print_results(results)
        close_driver()
        if not check_thresholds(results):
            raise SystemExit(1)


if __name__ == "__main__":
    main()

