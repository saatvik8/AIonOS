from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .embeddings import TfidfEmbedder

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "vector_db"


class VectorStore:
    def __init__(self, name: str) -> None:
        self.name = name
        self.dir = DB_DIR / name
        self.embedder = TfidfEmbedder()
        self.vectors: np.ndarray | None = None
        self.chunks: list[dict[str, Any]] = []

    def build(self, chunks: list[dict[str, Any]]) -> None:
        texts = [c["text"] for c in chunks]
        self.embedder.fit(texts)
        self.vectors = self.embedder.encode(texts)
        self.chunks = chunks
        self.persist()

    def persist(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        np.save(self.dir / "vectors.npy", self.vectors)
        (self.dir / "chunks.json").write_text(
            json.dumps(self.chunks, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.dir / "embedder.json").write_text(
            json.dumps(self.embedder.to_state()), encoding="utf-8"
        )

    def load(self) -> "VectorStore":
        vec_path = self.dir / "vectors.npy"
        if not vec_path.exists():
            raise FileNotFoundError(f"Vector store {self.name} is missing. Run ingest first.")
        self.vectors = np.load(vec_path)
        self.chunks = json.loads((self.dir / "chunks.json").read_text(encoding="utf-8"))
        self.embedder = TfidfEmbedder.from_state(
            json.loads((self.dir / "embedder.json").read_text(encoding="utf-8"))
        )
        return self

    def exists(self) -> bool:
        return (self.dir / "vectors.npy").exists()

    def search(self, query: str, k: int = 5, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if self.vectors is None or not len(self.chunks):
            return []
        q = self.embedder.encode([query])[0]
        scores = self.vectors @ q
        order = np.argsort(-scores)
        hits: list[dict[str, Any]] = []
        for idx in order:
            item = self.chunks[int(idx)]
            meta = item.get("metadata") or {}
            if where:
                skip = False
                for key, value in where.items():
                    if str(meta.get(key, "")).strip().lower() != str(value).strip().lower():
                        skip = True
                        break
                if skip:
                    continue
            hits.append(
                {
                    "id": item.get("id"),
                    "text": item["text"],
                    "metadata": meta,
                    "score": float(scores[int(idx)]),
                }
            )
            if len(hits) >= k:
                break
        return hits
