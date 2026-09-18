"""
Polls a Bedrock evaluation job until it finishes, then downloads and
summarizes the per-metric average scores from the output JSONL in S3.

Usage:
    python3 check_evaluation_job.py <job-name-or-arn>
"""

import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import boto3

REGION = "us-east-1"
POLL_SECONDS = 30
HISTORY_PATH = Path(__file__).with_name("evaluation_history.jsonl")

# These weights are intentionally explicit: replace them with estimates from
# your own support volume, cost model, or stakeholder priorities.
BUSINESS_WEIGHTS = {
    "Builtin.Correctness": 0.30,
    "Builtin.Completeness": 0.20,
    "Builtin.Helpfulness": 0.20,
    "Builtin.Faithfulness": 0.15,
    "NoGuessingPolicyCompliance": 0.15,
}
HIGHER_IS_BETTER = {
    "Builtin.Harmfulness": False,
}


def wait_for_completion(job_identifier: str):
    client = boto3.client("bedrock", region_name=REGION)
    while True:
        resp = client.get_evaluation_job(jobIdentifier=job_identifier)
        status = resp["status"]
        print(f"Status: {status}")
        if status in ("Completed", "Failed", "Stopped"):
            return resp
        time.sleep(POLL_SECONDS)


def collect_scores(output_s3_uri: str):
    parsed = urlparse(output_s3_uri)
    bucket, prefix = parsed.netloc, parsed.path.lstrip("/")

    s3 = boto3.client("s3", region_name=REGION)
    paginator = s3.get_paginator("list_objects_v2")
    result_files = [
        obj["Key"]
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix)
        for obj in page.get("Contents", [])
        if obj["Key"].endswith(".jsonl")
    ]

    totals = defaultdict(list)
    cases = []
    for key in result_files:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
        for line in body.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            records = record.get("conversationTurns", [record])
            for turn in records:
                prompt = turn.get("inputRecord", turn).get("prompt", {})
                prompt_content = prompt.get("content", [{}])
                question = prompt_content[0].get("text", "") if prompt_content else ""
                answer = turn.get("output", {}).get("text", "")
                metrics = turn.get("results")
                if metrics is None:
                    metrics = turn.get("automatedEvaluationResult", {}).get("scores", [])
                case_scores = {}
                for metric in metrics:
                    result = metric["result"]
                    if isinstance(result, dict):
                        result = result.get("floatValue", result.get("value"))
                    result = float(result)
                    name = metric["metricName"]
                    totals[name].append(result)
                    details = metric.get("evaluatorDetails", [])
                    case_scores[name] = {
                        "score": result,
                        "explanation": details[0].get("explanation", "") if details else "",
                    }
                cases.append({"question": question, "answer": answer, "metrics": case_scores})

    scores = {
        name: {"average": sum(values) / len(values), "count": len(values)}
        for name, values in totals.items()
    }
    return scores, cases


def append_history(job_identifier: str, scores: dict, cases: list, history_path: Path = HISTORY_PATH):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_identifier": job_identifier,
        "metrics": scores,
        "cases": cases,
    }
    with history_path.open("a", encoding="utf-8") as history_file:
        history_file.write(json.dumps(record) + "\n")


def load_history(history_path: Path = HISTORY_PATH):
    if not history_path.exists():
        return []
    records = []
    with history_path.open(encoding="utf-8") as history_file:
        for line in history_file:
            if line.strip():
                records.append(json.loads(line))
    return records


def bootstrap_slope_ci(values, seed=42, iterations=1000):
    if len(values) < 2:
        return None
    points = list(enumerate(values))
    rng = random.Random(seed)
    slopes = []
    for _ in range(iterations):
        sample = [points[rng.randrange(len(points))] for _ in points]
        x_mean = sum(x for x, _ in sample) / len(sample)
        y_mean = sum(y for _, y in sample) / len(sample)
        denominator = sum((x - x_mean) ** 2 for x, _ in sample)
        if denominator:
            slopes.append(
                sum((x - x_mean) * (y - y_mean) for x, y in sample) / denominator
            )
    if not slopes:
        return None
    slopes.sort()
    return slopes[len(slopes) // 40], slopes[len(slopes) * 39 // 40]


def trend_label(slope_ci):
    if slope_ci is None:
        return "insufficient history"
    low, high = slope_ci
    if low > 0:
        return "improving"
    if high < 0:
        return "declining"
    return "uncertain"


def business_value(scores, previous_scores=None):
    def calculate(metric_scores):
        weighted_sum = 0.0
        weight_total = 0.0
        for name, weight in BUSINESS_WEIGHTS.items():
            if name in metric_scores:
                weighted_sum += metric_scores[name]["average"] * weight
                weight_total += weight
        return weighted_sum / weight_total if weight_total else None

    index = calculate(scores)
    previous_index = calculate(previous_scores) if previous_scores else None
    return {
        "index": index,
        "change": index - previous_index if index is not None and previous_index is not None else None,
    }


def print_change_reasons(scores, cases, previous_record):
    if not previous_record or not previous_record.get("cases"):
        print("\nChange reasons: unavailable until a prior run with question-level details exists.")
        return

    previous_cases = {
        case.get("question"): case for case in previous_record["cases"]
    }
    changes = defaultdict(list)
    for case in cases:
        previous_case = previous_cases.get(case.get("question"))
        if not previous_case:
            continue
        for name, metric in case.get("metrics", {}).items():
            old_metric = previous_case.get("metrics", {}).get(name)
            if old_metric:
                changes[name].append((
                    metric["score"] - old_metric["score"],
                    case.get("question", ""),
                    metric.get("explanation", ""),
                ))

    print("\nReasons for metric changes (largest question-level movements):")
    for name in sorted(changes):
        movements = sorted(changes[name], key=lambda item: abs(item[0]), reverse=True)
        meaningful = [item for item in movements if abs(item[0]) >= 0.01][:2]
        if not meaningful:
            continue
        print(f"  {name}:")
        for delta, question, explanation in meaningful:
            direction = "up" if delta > 0 else "down"
            print(f"    {direction} {delta:+.3f}: {question}")
            if explanation:
                print(f"      evaluator: {explanation}")


def print_report(job_identifier, scores, cases, history):
    print("\nAverage scores:")
    for name, metric in sorted(scores.items()):
        print(f"  {name:30s} avg={metric['average']:.3f}  (n={metric['count']})")

    print("\nBusiness value proxy:")
    value = business_value(scores, history[-1]["metrics"] if history else None)
    if value["index"] is None:
        print("  No configured business metrics were present.")
    else:
        change = "n/a" if value["change"] is None else f"{value['change']:+.3f} vs previous run"
        print(f"  quality index={value['index']:.3f} ({change})")
        print("  Interpretation: higher index means more accurate, complete, useful, faithful answers.")

    print_change_reasons(scores, cases, history[-1] if history else None)

    if not history:
        print("\nTrend analysis: baseline saved; run another completed job for trends.")
        return
    print("\nStochastic trend analysis (95% bootstrap slope interval):")
    metric_names = sorted(set(scores) | {name for record in history for name in record["metrics"]})
    for name in metric_names:
        values = [record["metrics"][name]["average"] for record in history if name in record["metrics"]]
        if name in scores:
            values.append(scores[name]["average"])
        ci = bootstrap_slope_ci(values)
        if ci is None:
            print(f"  {name:30s} {trend_label(ci)}")
        else:
            print(f"  {name:30s} {trend_label(ci)}  slope={sum(ci) / 2:+.4f} [{ci[0]:+.4f}, {ci[1]:+.4f}]")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 check_evaluation_job.py <job-arn>")
        sys.exit(1)

    job_resp = wait_for_completion(sys.argv[1])
    if job_resp["status"] == "Completed":
        scores, cases = collect_scores(job_resp["outputDataConfig"]["s3Uri"])
        history = load_history()
        print_report(sys.argv[1], scores, cases, history)
        append_history(sys.argv[1], scores, cases)
    else:
        print("Job did not complete successfully:", json.dumps(job_resp, default=str))
