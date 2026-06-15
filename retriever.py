"""
Lightweight TF-IDF retriever (pure numpy, no heavy ML dependencies).

Builds a term-frequency / inverse-document-frequency index over text chunks and
answers queries by cosine similarity. Kept dependency-free on purpose so the
prototype runs anywhere Python + numpy is available.
"""

import math
import pickle
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Dict

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A small English stopword set keeps the vocabulary focused.
_STOP = set(
    "a an the of to and or in on for with at by from as is are was were be been "
    "this that these those it its their there here which who whom whose will would "
    "can could should may might must shall do does did has have had not no if then "
    "than so such into over under out up down about your you we they he she i me my "
    "our us them his her also any all each other more most some only same our".split()
)


def _stem(t: str) -> str:
    """Very light suffix stemmer: folds common plural/verb inflections to a
    shared root so 'officers'/'officer' and 'reporting'/'report' match at query
    time. Intentionally crude - no dependency, applied identically when building
    the index and when vectorizing a query, so both sides stay consistent."""
    if len(t) <= 3 or not t.isalpha():
        return t
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith("ing") and len(t) > 5:
        return t[:-3]
    if t.endswith("ed") and len(t) > 4:
        return t[:-2]
    if t.endswith("es") and len(t) > 4:
        return t[:-2]
    if t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def tokenize(text: str) -> List[str]:
    return [_stem(t) for t in _TOKEN_RE.findall(text.lower())
            if t not in _STOP and len(t) > 1]


@dataclass
class Chunk:
    chunk_id: int
    doc_id: str
    doc_title: str
    category: str
    page: int
    text: str
    url: str = ""  # source URL for clickable citations (empty for sample corpus)


@dataclass
class Index:
    chunks: List[Chunk]
    vocab: Dict[str, int]
    idf: np.ndarray
    matrix: np.ndarray  # (n_chunks, vocab) L2-normalized tf-idf, float32
    meta: dict = field(default_factory=dict)

    # ---- persistence ----
    def save(self, path):
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path) -> "Index":
        with open(path, "rb") as f:
            return pickle.load(f)

    # ---- search ----
    def _vectorize(self, text: str) -> np.ndarray:
        counts = Counter(tokenize(text))
        vec = np.zeros(len(self.vocab), dtype=np.float32)
        for term, c in counts.items():
            j = self.vocab.get(term)
            if j is not None:
                vec[j] = c
        if vec.sum() > 0:
            vec = vec * self.idf
            n = np.linalg.norm(vec)
            if n > 0:
                vec /= n
        return vec

    def search(self, query: str, top_k: int = 5, max_per_doc: int = 2):
        """Return up to top_k (chunk, score) hits, most relevant first.

        To keep results diverse, at most `max_per_doc` chunks from any single
        document are returned - otherwise one long doc can fill every slot and
        crowd out the document that actually answers the question.
        """
        q = self._vectorize(query)
        if not np.any(q):
            return []
        scores = self.matrix @ q  # cosine similarity (both normalized)
        order = np.argsort(-scores)
        results = []
        per_doc: Dict[str, int] = {}
        for i in order:
            s = float(scores[i])
            if s <= 0:
                break
            ch = self.chunks[i]
            if per_doc.get(ch.doc_id, 0) >= max_per_doc:
                continue
            results.append((ch, s))
            per_doc[ch.doc_id] = per_doc.get(ch.doc_id, 0) + 1
            if len(results) >= top_k:
                break
        return results


def build_index(chunks: List[Chunk]) -> Index:
    # vocabulary + document frequency
    df = Counter()
    tokenized = []
    for ch in chunks:
        toks = tokenize(ch.text)
        tokenized.append(toks)
        df.update(set(toks))

    vocab = {term: j for j, term in enumerate(sorted(df))}
    n_docs = len(chunks)
    idf = np.zeros(len(vocab), dtype=np.float32)
    for term, j in vocab.items():
        idf[j] = math.log((1 + n_docs) / (1 + df[term])) + 1.0

    matrix = np.zeros((n_docs, len(vocab)), dtype=np.float32)
    for i, toks in enumerate(tokenized):
        counts = Counter(toks)
        for term, c in counts.items():
            matrix[i, vocab[term]] = c
        matrix[i] *= idf
        norm = np.linalg.norm(matrix[i])
        if norm > 0:
            matrix[i] /= norm

    return Index(chunks=chunks, vocab=vocab, idf=idf, matrix=matrix,
                 meta={"n_chunks": n_docs, "vocab_size": len(vocab)})
