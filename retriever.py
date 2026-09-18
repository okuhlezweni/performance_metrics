"""
A deliberately simple retriever: no vector DB, no embeddings API call.
It scores documents by term-frequency overlap with the query. This is enough
to produce plausible-looking (and sometimes plausibly WRONG) retrieved
passages, which is actually useful for exercising eval metrics like
Context Relevance and Faithfulness -- you want some noisy retrievals in
your test set, not just perfect ones.
"""

import re
from collections import Counter

from knowledge_base import DOCUMENTS

_STOPWORDS = {
    "the", "a", "an", "is", "are", "to", "for", "of", "and", "on", "in",
    "my", "how", "do", "i", "can", "what", "does", "it", "with", "from",
}


def _tokenize(text: str):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in _STOPWORDS]


def _score(query_tokens, doc_tokens):
    query_counts = Counter(query_tokens)
    doc_counts = Counter(doc_tokens)
    overlap = sum(min(query_counts[t], doc_counts[t]) for t in query_counts)
    if overlap == 0:
        return 0.0
    # normalize a bit so very long docs don't win purely on length
    return overlap / (len(doc_tokens) ** 0.3)


def retrieve(query: str, k: int = 3):
    """Return the top-k documents as a list of {id, title, text, score}."""
    query_tokens = _tokenize(query)
    scored = []
    for doc in DOCUMENTS:
        doc_tokens = _tokenize(doc["title"] + " " + doc["text"])
        score = _score(query_tokens, doc_tokens)
        scored.append({**doc, "score": score})
    scored.sort(key=lambda d: d["score"], reverse=True)
    return [d for d in scored[:k] if d["score"] > 0] or scored[:1]
