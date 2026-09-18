"""
Runs the mock RAG agent over TEST_CASES and writes rag_eval_dataset.jsonl in
the format Bedrock expects for a "retrieve-and-generate" RAG evaluation job
where YOU supply the inference output (bring-your-own-inference / precomputed
RAG source), rather than pointing the job at a live Knowledge Base.

Schema reference (one JSON object per line):
{
  "conversationTurns": [
    {
      "prompt": {"content": [{"text": "<query>"}]},
      "referenceResponses": [{"content": [{"text": "<ground truth answer>"}]}],
      "output": {
        "text": "<what your RAG agent answered>",
        "modelIdentifier": "<free-text id for your generator>",
        "knowledgeBaseIdentifier": "<free-text id for your retriever/KB>",
        "retrievedPassages": {
          "retrievalResults": [
            {"name": "<doc id>", "content": {"text": "<chunk text>"}}
          ]
        }
      }
    }
  ]
}

Each line is independent (a single-turn "conversation"). Multi-turn
conversations are supported too (up to 5 turns) but aren't needed here.
"""

import json

from mock_rag_agent import MockRagAgent, RAG_SOURCE_ID
from test_dataset import TEST_CASES

OUTPUT_PATH = "rag_eval_dataset.jsonl"


def build_dataset(output_path: str = OUTPUT_PATH):
    agent = MockRagAgent()
    lines = []

    for case in TEST_CASES:
        result = agent.answer(case["query"])

        turn = {
            "prompt": {"content": [{"text": case["query"]}]},
            "referenceResponses": [
                {"content": [{"text": case["reference_response"]}]}
            ],
            "output": {
                "text": result["answer"],
                "modelIdentifier": "mock-rag-agent-generator-v1",
                "knowledgeBaseIdentifier": RAG_SOURCE_ID,
                "retrievedPassages": {
                    "retrievalResults": [
                        {
                            "name": p["id"],
                            "content": {"text": p["text"]},
                        }
                        for p in result["retrieved_passages"]
                    ]
                },
            },
        }
        lines.append({"conversationTurns": [turn]})

    with open(output_path, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")

    print(f"Wrote {len(lines)} records to {output_path}")
    return output_path


if __name__ == "__main__":
    build_dataset()
