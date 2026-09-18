# Mock RAG agent + Bedrock RAG Evaluation

A minimal, dependency-free mock RAG agent, plus the scripts to run its
outputs through **Amazon Bedrock Evaluations** (RAG evaluation, "bring your
own inference" mode). This mode is the right fit here: you already have a
RAG pipeline (yours, or this mock one) and want an LLM-judge to score its
answers — you don't need a live Bedrock Knowledge Base resource for it.

## Files

| File | Purpose |
|---|---|
| `knowledge_base.py` | 8 short documents (IT helpdesk domain) — the mock "corpus" |
| `retriever.py` | Zero-dependency term-overlap retriever (no embeddings/vector DB) |
| `generator.py` | Calls Bedrock Converse API if credentials/network are available; otherwise falls back to a deterministic offline extractive answer |
| `mock_rag_agent.py` | Wires retriever + generator into `MockRagAgent.answer(query)` |
| `test_dataset.py` | 6 test questions with hand-written ground-truth answers, including an out-of-scope question (tests hallucination/refusal) |
| `build_eval_dataset.py` | Runs the agent over the test set, writes `rag_eval_dataset.jsonl` in Bedrock's RAG-eval input format |
| `create_evaluation_job.py` | `boto3` script — creates the Bedrock RAG evaluation job, including one custom metric |
| `check_evaluation_job.py` | `boto3` script — polls the job, stores history, and reports score trends and a business-value proxy |
| `local_tests.py` | Fully local, no-AWS test runner (retrieval accuracy, required facts, refusal behavior) |

## Two layers of testing

**1. Local deterministic tests (`local_tests.py`)** — no AWS, no LLM judge, runs
in milliseconds. These check things you already *know* the right answer to,
so a judge model is the wrong tool: did retrieval surface the correct doc
(`expected_doc_id`), does the answer contain specific required facts
(`required_facts`), does the agent actually refuse on out-of-scope questions
(`expect_refusal`)? Run it as a fast gate before spending eval-job quota:

```bash
python3 local_tests.py   # exit code 1 if anything fails
```

Add more checks by adding functions to the `CHECKS` list and any new fields
your check needs to `test_dataset.py`.

**2. Bedrock LLM-as-judge (built-in + your own custom metrics)** — for
things that need judgment rather than exact matching: is the answer
*coherent*, *helpful*, *faithful to the context*? `create_evaluation_job.py`
includes one custom metric, `NoGuessingPolicyCompliance`, that grades the
agent against a house rule the built-in metrics don't encode ("must say it
doesn't know rather than guess"). Add your own the same way: write
`instructions` for the judge (using `{{prompt}}`, `{{prediction}}`,
`{{context}}` / `{{ground_truth}}` placeholders as needed), a `ratingScale`
so scores can be averaged, add the metric's `name` into the job's
`customMetricConfig.customMetrics` list, and also list that name in
`metricNames` so it actually gets run.

Custom metrics run against the same dataset and same evaluator model as the
built-ins — you don't need a second job.

## Try it locally (no AWS needed)

```bash
python3 mock_rag_agent.py        # sanity-check the agent
python3 build_eval_dataset.py    # writes rag_eval_dataset.jsonl
```

Without AWS credentials, both the agent's own generation step *and* the
eventual evaluation job need a model — the agent falls back to an offline
extractive answer so you can inspect the dataset shape immediately. Note
this fallback deliberately produces some wrong/incomplete answers (e.g. it
misses "90 days" for the password question, and gives an unrelated fact for
the VPN question) — good, because a metrics test is only interesting if
some answers are actually bad.

## Running the real evaluation on AWS

1. **Model access**: in the Bedrock console → Model access, enable the
   evaluator model you want to use as the judge (default here:
   `anthropic.claude-3-5-sonnet-20240620-v1:0`). If you want the agent
   itself to call a real model instead of the offline fallback, enable that
   model too and pass its ID into `MockRagAgent(model_id=...)`.

2. **IAM role**: create a role with a trust policy for `bedrock.amazonaws.com`,
   and permissions for:
   - `bedrock:InvokeModel` on the evaluator model
   - `s3:GetObject` on your input dataset
   - `s3:PutObject` / `s3:ListBucket` on your output prefix

3. **Upload the dataset**:
   ```bash
   aws s3 cp rag_eval_dataset.jsonl s3://<YOUR_BUCKET>/input/rag_eval_dataset.jsonl --region us-east-1
   ```

4. **Edit the CONFIG block** at the top of `create_evaluation_job.py`
   (region, role ARN, bucket paths, evaluator model ID), then:
   ```bash
   python3 create_evaluation_job.py
   ```

5. **Check status / get results**:
   ```bash
   python3 check_evaluation_job.py <job-arn-from-step-4>
   ```
   This polls `get_evaluation_job` until it finishes, then reads the result
   `.jsonl` files under your output S3 prefix and prints the average score
   per metric across all 6 test questions. It also appends the run to local
   `evaluation_history.jsonl`, compares it with previous runs, and reports a
   bootstrap trend interval for each metric. The business-value index is a
   transparent weighted quality proxy, not a dollar estimate; edit
   `BUSINESS_WEIGHTS` in `check_evaluation_job.py` to reflect your own support
   volume, cost, or risk assumptions. Each new run also stores question-level
   scores and evaluator explanations, so later reports identify the prompts
   that drove a metric up or down and quote the judge's rationale. The first
   run is only a baseline; change reasons appear from the second run onward.

## Metrics included

`Correctness`, `Completeness`, `Helpfulness`, `LogicalCoherence`,
`Faithfulness`, `Harmfulness`, and `Refusal` are enabled for this precomputed
retrieve-and-generate configuration. Bedrock currently rejects
`ContextRelevance` and `ContextCoverage` for this evaluation mode.

Two metrics were deliberately left out because they need extra fields this
mock agent doesn't populate:
- `CitationPrecision` / `CitationCoverage` — need a `citations` array mapping
  spans of the answer to specific retrieved passages. To add this, have
  `generator.py` tag which passage each sentence came from, and add a
  `citations` block to the `output` object in `build_eval_dataset.py`.

## Swapping in a real system later

To point this at your actual grad-programme helpdesk assistant instead of
the mock: replace `retriever.retrieve()` and `generator.generate_answer()`
with calls into your real pipeline (e.g. `bedrock-agent-runtime` `retrieve`
or `retrieve_and_generate`), keep `build_eval_dataset.py` and the two job
scripts as-is — they only care about the shape of the output dict, not
where it came from.
