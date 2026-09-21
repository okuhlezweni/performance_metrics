"""Serve the evaluation dashboard and optionally poll a Bedrock job."""

import argparse
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import boto3

from check_evaluation_job import (
    REGION,
    append_history,
    collect_scores,
    load_history,
)
from visualize_results import generate_dashboard

POLL_SECONDS = 30
JOB_ARN_PATTERN = re.compile(
    r"^arn:aws(?:-[^:]+)?:bedrock:[a-z0-9-]{1,20}:\d{12}:evaluation-job/[a-z0-9]{12}$"
)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_html(generate_dashboard(load_history()))
        elif path == "/api/dashboard":
            self.send_html(generate_dashboard(load_history()))
        elif path == "/api/history":
            self.send_json(load_history())
        else:
            self.send_error(404)

    def send_html(self, content):
        payload = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, content):
        payload = json.dumps(content).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format_string, *args):
        return


def poll_job(job_arn):
    job_arn = job_arn.strip()
    if not JOB_ARN_PATTERN.fullmatch(job_arn):
        print("Invalid Bedrock evaluation job ARN. Check for copied line breaks or spaces.")
        return
    client = boto3.client("bedrock", region_name=REGION)
    print(f"Polling Bedrock job: {job_arn}")
    while True:
        response = client.get_evaluation_job(jobIdentifier=job_arn)
        status = response["status"]
        print(f"Bedrock status: {status}")
        if status == "Completed":
            existing = {record.get("job_identifier") for record in load_history()}
            if job_arn not in existing:
                scores, cases = collect_scores(response["outputDataConfig"]["s3Uri"])
                append_history(job_arn, scores, cases)
                print("Saved completed Bedrock results to evaluation_history.jsonl")
            return
        if status in ("Failed", "Stopped"):
            print(f"Bedrock job ended with status: {status}")
            return
        time.sleep(POLL_SECONDS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-arn", help="Optional Bedrock evaluation job ARN to poll")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.job_arn:
        threading.Thread(target=poll_job, args=(args.job_arn,), daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard: http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
