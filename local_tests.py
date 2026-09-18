"""
Fully local, deterministic tests -- no AWS, no LLM judge, no network. These
catch things a judge model is the wrong (or at least a slow/expensive) tool
for:

  - Retrieval accuracy: did the retriever actually surface the right doc?
    This is a fact you *know* (you wrote the KB), not something to ask an
    LLM to guess at.
  - Required-fact presence: did the answer literally contain the key fact
    (e.g. "90 days")? A judge model can miss this or be lenient/inconsistent
    across runs; a substring check never is.
  - Refusal behavior: for the out-of-scope question, does the agent actually
    decline rather than hallucinate a plausible-sounding answer?

Run with:  python3 local_tests.py
Exit code is non-zero if any test fails, so this also works as a CI gate
before you spend evaluation-job quota on Bedrock.
"""

import sys

from mock_rag_agent import MockRagAgent
from test_dataset import TEST_CASES

REFUSAL_PHRASES = ["don't have", "not available", "do not have", "no information"]


def check_retrieval(case, result) -> str | None:
    if case["expected_doc_id"] is None:
        return None
    retrieved_ids = [p["id"] for p in result["retrieved_passages"]]
    if case["expected_doc_id"] not in retrieved_ids:
        return f"expected doc {case['expected_doc_id']!r} not in retrieved {retrieved_ids}"
    return None


def check_required_facts(case, result) -> str | None:
    missing = [f for f in case["required_facts"] if f.lower() not in result["answer"].lower()]
    if missing:
        return f"missing required facts in answer: {missing}"
    return None


def check_refusal(case, result) -> str | None:
    if not case["expect_refusal"]:
        return None
    answer_lower = result["answer"].lower()
    if not any(phrase in answer_lower for phrase in REFUSAL_PHRASES):
        return "expected a refusal/'I don't know', but answer looked confident"
    return None


CHECKS = [check_retrieval, check_required_facts, check_refusal]


def run():
    agent = MockRagAgent()
    failures = []

    for case in TEST_CASES:
        result = agent.answer(case["query"])
        for check in CHECKS:
            problem = check(case, result)
            if problem:
                failures.append((case["query"], problem))

    total = len(TEST_CASES)
    print(f"Ran {total} test cases, {len(failures)} check(s) failed.\n")
    for query, problem in failures:
        print(f"FAIL  [{query!r}]\n      -> {problem}\n")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(run())
