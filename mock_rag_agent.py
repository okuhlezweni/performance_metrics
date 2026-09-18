"""
The mock RAG agent itself: retrieve -> generate -> return a structured
result that already matches the shape Bedrock's RAG evaluation dataset
wants (see build_eval_dataset.py).
"""

from retriever import retrieve
from generator import generate_answer

RAG_SOURCE_ID = "mock-helpdesk-rag-agent-v1"


class MockRagAgent:
    def __init__(self, model_id=None, region=None, top_k: int = 3):
        self.model_id = model_id
        self.region = region
        self.top_k = top_k

    def answer(self, query: str) -> dict:
        passages = retrieve(query, k=self.top_k)
        kwargs = {}
        if self.model_id:
            kwargs["model_id"] = self.model_id
        if self.region:
            kwargs["region"] = self.region
        answer_text, used_offline = generate_answer(query, passages, **kwargs)
        return {
            "query": query,
            "answer": answer_text,
            "used_offline_fallback": used_offline,
            "retrieved_passages": [
                {"id": p["id"], "title": p["title"], "text": p["text"]}
                for p in passages
            ],
        }


if __name__ == "__main__":
    agent = MockRagAgent()
    demo_queries = [
        "How long until my password expires?",
        "My VPN won't connect, what should I check?",
        "What's the office guest Wi-Fi network called?",
    ]
    for q in demo_queries:
        result = agent.answer(q)
        mode = "OFFLINE fallback" if result["used_offline_fallback"] else "Bedrock"
        print(f"\nQ: {q}\n[{mode}] A: {result['answer']}")
        print("Retrieved:", [p["id"] for p in result["retrieved_passages"]])
