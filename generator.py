"""
Generation step of the mock RAG agent.

Tries a real Bedrock call first (so this becomes a genuine RAG agent the
moment you run it somewhere with AWS credentials + network access). If that
fails for any reason -- no credentials, no network, model not enabled --
it falls back to a deterministic, offline extractive answer built from the
retrieved passages, so the rest of the pipeline (dataset building, eval job
scripts) can still be developed and tested without AWS in the loop.
"""

import logging

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"
DEFAULT_REGION = "us-east-1"

SYSTEM_PROMPT = (
    "You are an internal IT helpdesk assistant. Answer the user's question "
    "using ONLY the provided context passages. If the answer is not in the "
    "context, say you don't have that information -- do not guess."
)


def _build_prompt(query: str, passages: list) -> str:
    context_block = "\n\n".join(
        f"[{p['id']}] {p['title']}: {p['text']}" for p in passages
    )
    return (
        f"Context:\n{context_block}\n\n"
        f"Question: {query}\n\n"
        "Answer the question using only the context above."
    )


def _generate_via_bedrock(query: str, passages: list, model_id: str, region: str):
    import boto3

    client = boto3.client("bedrock-runtime", region_name=region)
    user_prompt = _build_prompt(query, passages)
    response = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig={"maxTokens": 400, "temperature": 0.0},
    )
    return response["output"]["message"]["content"][0]["text"]


def _generate_offline(query: str, passages: list) -> str:
    """Deterministic fallback: stitch together the most relevant sentences.

    This intentionally does NOT try to be a good generator -- it's just
    extractive enough to give the evaluator (an LLM judge) something
    realistic to grade, including realistic failure modes like including
    an irrelevant sentence from a low-scoring passage.
    """
    if not passages:
        return "I don't have information about that in the helpdesk knowledge base."

    top = passages[0]
    sentences = [s.strip() for s in top["text"].split(".") if s.strip()]
    answer = ". ".join(sentences[:2]).strip()
    if answer and not answer.endswith("."):
        answer += "."
    return answer or "I don't have information about that in the helpdesk knowledge base."


def generate_answer(
    query: str,
    passages: list,
    model_id: str = DEFAULT_MODEL_ID,
    region: str = DEFAULT_REGION,
):
    """Returns (answer_text, used_offline_fallback: bool)."""
    try:
        text = _generate_via_bedrock(query, passages, model_id, region)
        return text, False
    except Exception as exc:  # noqa: BLE001 - deliberately broad for a demo fallback
        logger.info("Bedrock call unavailable (%s); using offline fallback.", exc)
        return _generate_offline(query, passages), True
