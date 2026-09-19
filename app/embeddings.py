from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

import numpy as np

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    words = TOKEN_RE.findall((text or "").lower())
    unigrams = words
    bigrams = [f"{words[i]}_{words[i + 1]}" for i in range(len(words) - 1)]
    return unigrams + bigrams


class TfidfEmbedder:
    """Local TF-IDF embedder used as the vector space for the RAG store."""

    def __init__(self) -> None:
        self.vocab: dict[str, int] = {}
        self.idf: np.ndarray | None = None

    def fit(self, documents: Iterable[str]) -> "TfidfEmbedder":
        docs = list(documents)
        df: Counter[str] = Counter()
        for doc in docs:
            df.update(set(tokenize(doc)))
        tokens = sorted(df)
        self.vocab = {tok: i for i, tok in enumerate(tokens)}
        n = max(len(docs), 1)
        idf = np.zeros(len(tokens), dtype=np.float32)
        for tok, idx in self.vocab.items():
            idf[idx] = math.log((1 + n) / (1 + df[tok])) + 1.0
        self.idf = idf
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        if not self.vocab or self.idf is None:
            raise RuntimeError("Embedder is not fitted")
        dim = len(self.vocab)
        matrix = np.zeros((len(texts), dim), dtype=np.float32)
        for row, text in enumerate(texts):
            counts = Counter(tokenize(text))
            if not counts:
                continue
            max_tf = max(counts.values())
            for tok, tf in counts.items():
                idx = self.vocab.get(tok)
                if idx is None:
                    continue
                matrix[row, idx] = (tf / max_tf) * self.idf[idx]
            norm = np.linalg.norm(matrix[row])
            if norm > 0:
                matrix[row] /= norm
        return matrix

    def to_state(self) -> dict:
        return {
            "vocab": self.vocab,
            "idf": self.idf.tolist() if self.idf is not None else [],
        }

    @classmethod
    def from_state(cls, state: dict) -> "TfidfEmbedder":
        inst = cls()
        inst.vocab = {k: int(v) for k, v in state.get("vocab", {}).items()}
        inst.idf = np.array(state.get("idf", []), dtype=np.float32)
        return inst
