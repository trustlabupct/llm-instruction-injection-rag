"""Document retrieval.

Two backends:
  - tfidf      : no downloads, always available. Used by default.
  - embeddings : sentence-transformers + cosine search over a dense matrix.

FAISS is not used: with 40 documents, exhaustive search is instantaneous and avoids one
more dependency. If the corpus grew, the point to change is _search().
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DOCS_CSV = ROOT / "data" / "documents.csv"


@dataclass
class Document:
    doc_id: str
    title: str
    category: str
    doc_type: str          # clean | poisoned
    attack_family: str     # none | instruction_override | ...
    content: str

    @property
    def is_poisoned(self) -> bool:
        return self.doc_type == "poisoned"


def load_documents(path: Path = DOCS_CSV) -> list[Document]:
    with open(path, encoding="utf-8") as f:
        return [Document(**row) for row in csv.DictReader(f)]


def load_queries(path: Path | None = None) -> list[dict]:
    path = path or ROOT / "data" / "test_queries.csv"
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["allowed_tools"] = [t for t in r["allowed_tools"].split("|") if t]
        r["forbidden_tools"] = [t for t in r["forbidden_tools"].split("|") if t]
        r["expected_docs"] = [d for d in r["expected_docs"].split("|") if d]
    return rows


class Retriever:
    def __init__(self, documents: list[Document], backend: str = "tfidf"):
        self.documents = documents
        self.backend = backend
        corpus = [f"{d.title}. {d.content}" for d in documents]

        if backend == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer
            # ngram (1,2) helps with expressions like "practicas externas"
            self._vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
            self._matrix = self._vec.fit_transform(corpus).toarray()
        elif backend == "embeddings":
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            self._matrix = self._model.encode(corpus, normalize_embeddings=True)
        else:
            raise ValueError(f"unknown backend: {backend}")

    def _encode_query(self, query: str) -> np.ndarray:
        if self.backend == "tfidf":
            return self._vec.transform([query]).toarray()[0]
        return self._model.encode([query], normalize_embeddings=True)[0]

    def _search(self, qvec: np.ndarray, top_k: int) -> list[tuple[int, float]]:
        norms = np.linalg.norm(self._matrix, axis=1) * np.linalg.norm(qvec)
        norms[norms == 0] = 1e-9
        sims = (self._matrix @ qvec) / norms
        order = np.argsort(-sims)[:top_k]
        return [(int(i), float(sims[i])) for i in order]

    def retrieve(self, query: str, top_k: int = 3) -> list[tuple[Document, float]]:
        qvec = self._encode_query(query)
        return [(self.documents[i], s) for i, s in self._search(qvec, top_k)]


if __name__ == "__main__":
    docs = load_documents()
    r = Retriever(docs)
    for q in ["What requirements do I need to apply for an internship?",
              "How do I open a technical support ticket?"]:
        print(f"\n{q}")
        for d, s in r.retrieve(q):
            flag = "POISONED" if d.is_poisoned else "clean"
            print(f"  {d.doc_id}  {s:.3f}  [{flag}]  {d.title}")
