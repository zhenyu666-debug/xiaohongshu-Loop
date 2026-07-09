"""Smoke tests for ChromaVectorStore on-disk persistence.

These exercise the default-on-disk vector store path.
They use a temporary directory so they do not touch any real Chroma data.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.ai.rag.vector_store import ChromaVectorStore, VectorEntry, VectorStore


pytestmark = pytest.mark.skipif(
    not pytest.importorskip("chromadb", reason="chromadb not installed"),
    reason="chromadb required",
)


def _unit_vecs(n, dim=4):
    rng = np.random.default_rng(seed=42)
    raw = rng.standard_normal((n, dim))
    raw /= np.linalg.norm(raw, axis=1, keepdims=True)
    return raw.astype(np.float32).tolist()


def test_chroma_add_and_search(tmp_path):
    store = ChromaVectorStore(persist_directory=str(tmp_path), collection_name="docs")
    vecs = _unit_vecs(3)
    store.add([
        VectorEntry(id="a", vector=vecs[0], metadata={"text": "alpha", "src": "t1"}),
        VectorEntry(id="b", vector=vecs[1], metadata={"text": "beta", "src": "t1"}),
        VectorEntry(id="c", vector=vecs[2], metadata={"text": "gamma", "src": "t1"}),
    ])
    assert store.count() == 3
    results = store.search(vecs[0], top_k=2)
    assert len(results) == 2
    assert results[0].id == "a"
    assert results[0].metadata.get("text") == "alpha"


def test_chroma_persistence_survives_reopen(tmp_path):
    vecs = _unit_vecs(2)
    writer = ChromaVectorStore(persist_directory=str(tmp_path), collection_name="docs")
    writer.add([
        VectorEntry(id="x", vector=vecs[0], metadata={"text": "xray"}),
        VectorEntry(id="y", vector=vecs[1], metadata={"text": "yankee"}),
    ])
    assert writer.count() == 2
    reader = ChromaVectorStore(persist_directory=str(tmp_path), collection_name="docs")
    assert reader.count() == 2
    hits = reader.search(vecs[0], top_k=1)
    assert hits and hits[0].id == "x"
    assert hits[0].metadata.get("text") == "xray"


def test_chroma_delete(tmp_path):
    store = ChromaVectorStore(persist_directory=str(tmp_path), collection_name="docs")
    vecs = _unit_vecs(2)
    store.add([
        VectorEntry(id="x", vector=vecs[0], metadata={"text": "xray"}),
        VectorEntry(id="y", vector=vecs[1], metadata={"text": "yankee"}),
    ])
    store.delete(["x"])
    assert store.count() == 1


def test_chroma_collection_name_validation(tmp_path):
    with pytest.raises(ValueError, match="3 chars"):
        ChromaVectorStore(persist_directory=str(tmp_path), collection_name="ab")


def test_facade_routes_to_chroma(tmp_path):
    facade = VectorStore(store_type="chroma", persist_directory=str(tmp_path), collection_name="docs")
    assert isinstance(facade.store, ChromaVectorStore)
    facade.add([VectorEntry(id="a", vector=[1.0, 0.0, 0.0, 0.0], metadata={"text": "x"})])
    assert facade.count() == 1
