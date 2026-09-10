"""
retriever.py — Simple TF-IDF retrieval over the codebase's method chunks.

Deliberately not an embedding model: TF-IDF is fully local, needs no API
call and no model download, and is a fair stand-in for "similarity-only
retrieval" as a baseline. Swap this for a real embedding-based retriever
(e.g. Voyage, OpenAI embeddings) later if you want to test whether RCL's
gating still helps on top of a stronger retriever — the scoring/gating
logic in scoring.py doesn't care which retriever produced the candidates.
"""

from typing import Dict, List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from call_graph import MethodChunk


class Retriever:
    def __init__(self, codebase: Dict[str, MethodChunk]):
        self.codebase = codebase
        self.names = list(codebase.keys())
        texts = [codebase[n].source_text for n in self.names]
        self.vectorizer = TfidfVectorizer()
        self.matrix = self.vectorizer.fit_transform(texts)

    def top_k(self, query_text: str, k: int, exclude: str = None) -> List[str]:
        q_vec = self.vectorizer.transform([query_text])
        sims = cosine_similarity(q_vec, self.matrix).flatten()
        ranked = sorted(zip(self.names, sims), key=lambda x: -x[1])
        results = [n for n, _ in ranked if n != exclude]
        return results[:k]
