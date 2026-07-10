"""End-to-end tests for LLM streaming.
Covers mock multi-chunk streaming, RAG query_stream, and
FastAPI /api/ai/chat/stream SSE end-to-end via httpx ASGI transport.
Real OpenAI streaming is exercised when OPENAI_API_KEY is set; otherwise
the test is skipped (we do not silently fall back to mock there so the
coverage gap is visible)."""
from __future__ import annotations
import os
import pytest
import httpx
from fastapi import FastAPI
from app.api import ai as ai_api
from app.ai.llm import LLMClient


# A self-contained FastAPI app that mounts only the AI router. Using a
# separate app (instead of importing app.main) keeps these tests fast and
# avoids pulling the XHS channel adapter / scheduler / db init paths into
# scope.
@pytest.fixture
def app():
    ai_api.reset_rag_pipeline()
    a = FastAPI(title='xhs-ai-test')
    a.include_router(ai_api.router)
    yield a
    ai_api.reset_rag_pipeline()


# -------------------------------------------------------------- unit

@pytest.mark.asyncio
async def test_llmclient_astream_mock_yields_multiple_chunks():
    client = LLMClient(provider='mock', mock_stream_chunk_words=4)
    chunks = []
    async for c in client.astream([{'role': 'user', 'content': 'hello'}]):
        chunks.append(c)
    assert len(chunks) >= 2, 'mock astream should yield multiple chunks'
    full = ''.join(chunks).strip()
    assert 'mock streaming answer' in full

@pytest.mark.asyncio
async def test_llmclient_astream_mock_chunk_size_is_configurable():
    client = LLMClient(provider='mock', mock_stream_chunk_words=1)
    chunks = []
    async for c in client.astream([{'role': 'user', 'content': 'hi'}]):
        chunks.append(c)
    n_words = len(LLMClient.MOCK_RESPONSE.split(' '))
    assert len(chunks) == n_words


@pytest.mark.asyncio
async def test_rag_pipeline_query_stream_yields_chunks():
    from app.ai.rag.embedder import MockEmbedder
    from app.ai.rag.retriever import Retriever
    from app.ai.rag.vector_store import InMemoryVectorStore
    from app.ai.rag.generator import Generator, RAGPipeline
    embedder = MockEmbedder()
    store = InMemoryVectorStore()
    retriever = Retriever(store, embedder, top_k=2)
    pipeline = RAGPipeline(embedder, store, retriever, Generator(provider='mock'))
    pipeline.index_documents([
        {'content': 'AI is the future of automation', 'source': 'doc1'},
        {'content': 'Machine learning powers modern AI', 'source': 'doc2'},
    ])
    chunks = []
    async for tok in pipeline.query_stream('What is AI?'):
        chunks.append(tok)
    assert len(chunks) >= 2
    assert 'mock streaming answer' in ''.join(chunks)


# --------------------------------------------- FastAPI SSE end-to-end

@pytest.mark.asyncio
async def test_chat_stream_sse_yields_multiple_chunks(app):
    pipeline = ai_api.get_rag_pipeline()
    pipeline.index_documents([
        {'content': 'Streaming end-to-end corpus', 'source': 'seed'},
    ])
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        async with client.stream(
            'POST', '/ai/chat/stream', json={'message': 'What is streaming?'}
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers['content-type'].startswith('text/event-stream')
            text = ''
            async for line in resp.aiter_lines():
                text += line + chr(10)
    data_lines = [ln[len('data: '):] for ln in text.splitlines() if ln.startswith('data: ') and ln != 'data: [DONE]']
    assert len(data_lines) >= 2, f'expected multi-chunk SSE; got {len(data_lines)}'
    full = ''.join(data_lines)
    assert 'mock streaming answer' in full
    assert '[DONE]' in text


@pytest.mark.asyncio
async def test_chat_stream_sse_no_context_yields_idk(app):
    # No corpus indexed - generator should emit a single 'I don't know.' token
    # and the stream should still close cleanly with [DONE].
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        async with client.stream(
            'POST', '/ai/chat/stream', json={'message': 'anything'}
        ) as resp:
            assert resp.status_code == 200
            text = ''
            async for line in resp.aiter_lines():
                text += line + chr(10)
    assert 'I don' + chr(39) + 't know' in text
    assert '[DONE]' in text


# -------------------------------------------- real OpenAI streaming

@pytest.mark.asyncio
async def test_real_openai_astream_if_key_present():
    """Hit real OpenAI streaming when a key is in the env.
    Skipped otherwise. The point is to keep the streaming code path
    honest: if OpenAI breaks their astream contract or langchain-openai
    drifts, this test catches it without falling back to the mock."""
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY not set; real streaming not exercised')
    from langchain_core.messages import HumanMessage
    from langchain_openai import ChatOpenAI
    chat = ChatOpenAI(model='gpt-4o-mini', temperature=0)
    n = 0
    content_chars = 0
    async for chunk in chat.astream([HumanMessage(content='Say hi in exactly 3 words.')]):
        n += 1
        if isinstance(chunk.content, str):
            content_chars += len(chunk.content)
    assert n >= 1, 'real OpenAI astream produced zero chunks'
    assert content_chars > 0, 'real OpenAI astream produced empty content'

