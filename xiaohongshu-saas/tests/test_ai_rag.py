"""Tests for RAG module."""
import pytest
from app.ai.rag.text_splitter import TextSplitter
from app.ai.rag.embedder import MockEmbedder, Embedder
from app.ai.rag.vector_store import InMemoryVectorStore, VectorEntry
from app.ai.rag.retriever import Retriever, SearchResult
from app.ai.rag.generator import Generator, RAGPipeline
from app.ai.rag.reranker import Reranker
from app.ai.rag.document_loader import DocumentLoader


def test_text_splitter_basic():
    splitter = TextSplitter(chunk_size=100, chunk_overlap=20)
    chunks = splitter.split_text("Hello world. " * 20)
    assert len(chunks) > 0


def test_text_splitter_with_metadata():
    splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
    chunks = splitter.split_text("Test text here", {"source": "test"})
    assert chunks[0].metadata.get("source") == "test"


def test_mock_embedder():
    embedder = MockEmbedder()
    embeddings = embedder.embed_sync(["Hello", "World"])
    assert len(embeddings) == 2


def test_embedder_dimension():
    embedder = Embedder(provider="mock")
    assert embedder.dimension > 0


def test_in_memory_vector_store_add():
    store = InMemoryVectorStore()
    entries = [
        VectorEntry(id="1", vector=[1.0, 0.0], metadata={"text": "Hello"}),
        VectorEntry(id="2", vector=[0.0, 1.0], metadata={"text": "World"})
    ]
    store.add(entries)
    assert store.count() == 2


def test_in_memory_vector_store_search():
    store = InMemoryVectorStore()
    entries = [
        VectorEntry(id="1", vector=[1.0, 0.0, 0.0], metadata={"text": "Hello"}),
        VectorEntry(id="2", vector=[0.0, 1.0, 0.0], metadata={"text": "World"})
    ]
    store.add(entries)
    results = store.search([1.0, 0.0, 0.0], top_k=2)
    assert len(results) == 2


def test_vector_store_delete():
    store = InMemoryVectorStore()
    entry = VectorEntry(id="1", vector=[1.0, 0.0])
    store.add([entry])
    store.delete(["1"])
    assert store.count() == 0


def test_retriever_index_and_retrieve():
    embedder = MockEmbedder()
    store = InMemoryVectorStore()
    retriever = Retriever(store, embedder, top_k=2)
    retriever.index(["AI is great", "Machine learning", "Deep learning models"])
    results = retriever.retrieve("AI")
    assert len(results) > 0


def test_reranker():
    entries = [
        VectorEntry(id="1", vector=[1, 0], metadata={"text": "Python tutorial"}),
        VectorEntry(id="2", vector=[0, 1], metadata={"text": "JavaScript guide"})
    ]
    results = [SearchResult(entry=e, score=0.5) for e in entries]
    reranker = Reranker()
    reranked = reranker.rerank("Python", results)
    assert len(reranked) == 2
    assert reranked[0].entry.id == "1"


@pytest.mark.asyncio
async def test_generator_mock():
    entries = [VectorEntry(id="1", vector=[1, 0], metadata={"text": "Test content here"})]
    results = [SearchResult(entry=e, score=0.8) for e in entries]
    gen = Generator(llm_provider="mock")
    output = await gen.generate("query", results)
    assert output.answer != ""


@pytest.mark.asyncio
async def test_generator_empty_context():
    gen = Generator(llm_provider="mock")
    output = await gen.generate("query", [])
    assert output.confidence == 0.0


@pytest.mark.asyncio
async def test_rag_pipeline_query():
    embedder = MockEmbedder()
    store = InMemoryVectorStore()
    retriever = Retriever(store, embedder, top_k=3)
    generator = Generator(llm_provider="mock")
    pipeline = RAGPipeline(embedder, store, retriever, generator)
    documents = [
        {"content": "AI is transforming the world", "source": "doc1"},
        {"content": "Machine learning enables computers to learn", "source": "doc2"}
    ]
    pipeline.index_documents(documents)
    result = await pipeline.query("What is AI?")
    assert result.answer != ""


def test_document_loader_directory(tmp_path):
    (tmp_path / "test1.txt").write_text("Content 1", encoding="utf-8")
    (tmp_path / "test2.md").write_text("# Content 2", encoding="utf-8")
    loader = DocumentLoader()
    docs = loader.load(str(tmp_path))
    assert len(docs) == 2
