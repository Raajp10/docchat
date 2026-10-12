"""Search index: hybrid of keyword search (BM25) and meaning search (embeddings).

- Keyword search always works, no downloads.
- Embeddings use a small free local model (fastembed, ~130MB, downloaded once).
  If it can't load, the index silently falls back to keyword-only.
Saved to <folder>/.docchat/ so re-opening a folder is instant.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter

import numpy as np

from .ingest import Chunk

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("""a an and are as at be by for from has have in is it its of on or that the this to
was were will with what which who how when where why do does can you your i we our they
me my get got much many any there their about if so than then""".split())


def _stem(t: str) -> str:
    """Tiny stemmer so 'incidents' matches 'incident', 'handling' matches 'handle'."""
    for suf in ("ing", "ies", "es", "ed", "s"):
        if len(t) > len(suf) + 2 and t.endswith(suf):
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
    return t


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class BM25:
    def __init__(self, docs: list[list[str]], k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs], dtype=float)
        self.avg = float(self.len.mean()) if len(docs) else 0.0
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        out = np.zeros(len(self.tf))
        for i, tf in enumerate(self.tf):
            s = 0.0
            for t in query:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1)))
            out[i] = s
        return out


_EMBEDDER = None
_EMBED_FAILED = False


def _model_cached() -> bool:
    import glob
    import tempfile
    roots = [os.environ.get("FASTEMBED_CACHE_PATH", ""), os.path.join(tempfile.gettempdir(), "fastembed_cache")]
    return any(r and glob.glob(os.path.join(r, "*bge-small-en-v1.5*")) for r in roots)


def _online(timeout=4) -> bool:
    import urllib.request
    try:
        urllib.request.urlopen("https://huggingface.co", timeout=timeout)
        return True
    except Exception:
        return False


def _load_embedder():
    """Load the local embedding model once. Returns None (keyword-only) if unavailable."""
    global _EMBEDDER, _EMBED_FAILED
    if _EMBEDDER is not None or _EMBED_FAILED:
        return _EMBEDDER
    if os.environ.get("DOCCHAT_KEYWORD_ONLY") == "1" or (not _model_cached() and not _online()):
        _EMBED_FAILED = True
        return None
    try:
        from fastembed import TextEmbedding
        _EMBEDDER = TextEmbedding(EMBED_MODEL)
    except Exception:
        _EMBED_FAILED = True
    return _EMBEDDER


class Index:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray | None = None):
        self.chunks = chunks
        self.vectors = vectors
        self.bm25 = BM25([tokenize(c.text) for c in chunks])
        self._embedder = None

    @property
    def mode(self) -> str:
        return "hybrid (keywords + meaning)" if self.vectors is not None else "keyword only"

    # ---------- build / save / load ----------
    @classmethod
    def build(cls, chunks: list[Chunk], use_embeddings: bool = True) -> "Index":
        vectors = None
        idx = cls(chunks)
        if use_embeddings and chunks:
            emb = _load_embedder()
            if emb is not None:
                vecs = np.array(list(emb.embed([c.text for c in chunks])), dtype=np.float32)
                vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
                vectors = vecs
                idx._embedder = emb
        idx.vectors = vectors
        return idx

    def save(self, folder: str):
        d = os.path.join(folder, ".docchat")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "chunks.json"), "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in self.chunks], f)
        if self.vectors is not None:
            np.save(os.path.join(d, "vectors.npy"), self.vectors)

    @classmethod
    def load(cls, folder: str) -> "Index | None":
        d = os.path.join(folder, ".docchat")
        p = os.path.join(d, "chunks.json")
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as f:
            chunks = [Chunk(**c) for c in json.load(f)]
        vp = os.path.join(d, "vectors.npy")
        vectors = np.load(vp) if os.path.exists(vp) else None
        return cls(chunks, vectors)

    # ---------- search ----------
    def _embed_query(self, q: str):
        if self._embedder is None:
            self._embedder = _load_embedder()
        if self._embedder is None:
            return None
        v = np.array(list(self._embedder.query_embed([q]))[0], dtype=np.float32)
        return v / (np.linalg.norm(v) + 1e-9)

    def search(self, query: str, k: int = 6) -> list[tuple[Chunk, float]]:
        if not self.chunks:
            return []
        kw = self.bm25.scores(tokenize(query))
        qv = self._embed_query(query) if self.vectors is not None else None
        if qv is None:
            ranks = {i: kw[i] for i in np.argsort(-kw)[:50] if kw[i] > 0}
        else:
            # Blend normalized scores, leaning on meaning. (Rank fusion over-rewards any single
            # keyword hit on small folders, e.g. "days" pulling refunds over the PTO page.)
            sim = self.vectors @ qv
            norm = lambda x: (x - x.min()) / (x.max() - x.min()) if x.max() > x.min() else x * 0
            blend = 0.3 * norm(kw) + 0.7 * norm(sim)
            ranks = {i: blend[i] for i in np.argsort(-blend)[:50]}
        best = sorted(ranks.items(), key=lambda x: -x[1])[:k]
        return [(self.chunks[i], s) for i, s in best]
