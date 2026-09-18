"""
Creates a Bedrock RAG Evaluation job that scores the precomputed outputs in
rag_eval_dataset.jsonl (i.e. your own RAG agent's outputs, not a live
Knowledge Base). This is the "bring your own inference" RAG eval mode.

Prerequisites (must be done once, outside this script):
  1. Upload rag_eval_dataset.jsonl to S3:
       aws s3 cp rag_eval_dataset.jsonl s3://<YOUR_BUCKET>/input/rag_eval_dataset.jsonl
  2. An S3 prefix for output results, e.g. s3://<YOUR_BUCKET>/output/
  3. An IAM role (roleArn below) with a trust policy allowing
     bedrock.amazonaws.com to assume it, and permissions for:
       - bedrock:InvokeModel / InvokeModelWithResponseStream on the evaluator
         model
       - s3:GetObject on the input dataset
       - s3:PutObject on the output prefix
  4. Model access enabled (in the Bedrock console, "Model access") for the
     evaluator model you choose below.

Fill in the CONFIG block, then run:  python3 create_evaluation_job.py
"""

import json
import os
from datetime import datetime

import boto3


def load_env_file(path):
    with open(path, encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip())


load_env_file(os.path.join(os.path.dirname(__file__), "env.env"))

# ---------------------------------------------------------------------------
# CONFIG - fill these in for your AWS account
# ---------------------------------------------------------------------------
model_id = os.environ.get("MODEL_ID", "anthropic.claude-sonnet-4-5-20250929-v1:0")
region = os.environ.get("REGION", "us-east-1")
role_arn = os.environ.get("ROLE_ARN")
input_s3_uri = os.environ.get("INPUT_S3_URI")
output_s3_uri = os.environ.get("OUTPUT_S3_URI")
evaluator_model_id = os.environ.get("EVALUATOR_MODEL_ID")
rag_source_identifier = os.environ.get("RAG_SOURCE_IDENTIFIER")

# Metrics that apply to precomputed retrieve-and-generate results.
# ContextRelevance / ContextCoverage need retrievedPassages (we have them).
# CitationPrecision / CitationCoverage need a "citations" field (we didn't
# populate one, so leave those out unless you extend build_eval_dataset.py).
METRIC_NAMES = [
    "Builtin.Correctness",
    "Builtin.Completeness",
    "Builtin.Helpfulness",
    "Builtin.LogicalCoherence",
    "Builtin.Faithfulness",
    "Builtin.Harmfulness",
    "Builtin.Refusal",
    # Your own metric, defined below -- name must also appear here.
    "NoGuessingPolicyCompliance",
]

# A custom metric: your own LLM-as-judge criterion, on top of the built-ins.
# `instructions` must include the required placeholders -- for RAG jobs that's
# {{prompt}}, {{prediction}}, and either {{context}} (retrieved passages) or
# {{ground_truth}} depending on what your instructions reference.
# `ratingScale` turns the judge's verdict into a number Bedrock can average.
CUSTOM_METRICS = [
    {
        "customMetricDefinition": {
            "name": "NoGuessingPolicyCompliance",
            "instructions": (
                "You are grading an internal IT helpdesk assistant against one "
                "house rule: it must answer ONLY from the given context, and "
                "must explicitly say it doesn't know rather than guessing when "
                "the context doesn't contain the answer.\n\n"
                "Context:\n{{context}}\n\n"
                "Question:\n{{prompt}}\n\n"
                "Assistant's answer:\n{{prediction}}\n\n"
                "Does the answer violate this rule -- i.e. does it state or "
                "imply anything not supported by the context, or does it "
                "confidently answer a question the context doesn't cover? "
                "Rate strictly."
            ),
            "ratingScale": [
                {"definition": "Fully compliant, no unsupported claims", "value": {"floatValue": 1.0}},
                {"definition": "Minor unsupported detail", "value": {"floatValue": 0.5}},
                {"definition": "Confidently answered without support / hallucinated", "value": {"floatValue": 0.0}},
            ],
        }
    }
]
# ---------------------------------------------------------------------------


def create_job():
    client = boto3.client("bedrock", region_name=region)
    job_name = f"mock-rag-eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    response = client.create_evaluation_job(
        jobName=job_name,
        jobDescription="Evaluation of mock RAG agent outputs (retrieve-and-generate, precomputed).",
        roleArn=role_arn,
        applicationType="RagEvaluation",
        inferenceConfig={
            "ragConfigs": [
                {
                    "precomputedRagSourceConfig": {
                        "retrieveAndGenerateSourceConfig": {
                            "ragSourceIdentifier": rag_source_identifier
                        }
                    }
                }
            ]
        },
        outputDataConfig={"s3Uri": output_s3_uri},
        evaluationConfig={
            "automated": {
                "datasetMetricConfigs": [
                    {
                        "taskType": "QuestionAndAnswer",
                        "dataset": {
                            "name": "MockHelpdeskRagEvalDataset",
                            "datasetLocation": {"s3Uri": input_s3_uri},
                        },
                        "metricNames": METRIC_NAMES,
                    }
                ],
                "evaluatorModelConfig": {
                    "bedrockEvaluatorModels": [{"modelIdentifier": evaluator_model_id}]
                },
                "customMetricConfig": {
                    "customMetrics": CUSTOM_METRICS,
                    "evaluatorModelConfig": {
                        "bedrockEvaluatorModels": [{"modelIdentifier": evaluator_model_id}]
                    },
                },
            }
        },
    )

    print(json.dumps(response, indent=2, default=str))
    print(f"\nJob name: {job_name}")
    print(f"Job ARN:  {response.get('jobArn')}")
    return response


if __name__ == "__main__":
    create_job()
