"""AI API routes - real implementations backed by the M1-M5 stack."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.ai.agents.coordinator import CoordinatorAgent
from app.ai.agents.content_agent import ContentAgent
from app.ai.agents.analysis_agent import AnalysisAgent
from app.ai.memory.db import MemoryDB
from app.ai.memory.manager import MemoryManager
from app.ai.rag.document_loader import DocumentLoader
from app.ai.rag.rag_pipeline import build_default_rag_pipeline
from app.ai.rag.text_splitter import TextSplitter
from app.ai.tools.registry import tool_registry
from app.ai.tools.content_tools import register_content_tools
from app.ai.tools.scheduler_tools import register_scheduler_tools
from app.ai.tools.search_tools import register_search_tools


router = APIRouter(prefix="/ai", tags=["AI"])


# Auto-register tools so /api/ai/tools is always populated.
def _ensure_tools_registered() -> None:
    if not tool_registry.list_tools():
        register_content_tools()
        register_scheduler_tools()
        register_search_tools()


_ensure_tools_registered()


# Persistent RAG pipeline singleton so /chat/stream queries hit the same
# index the user populated via /rag/ingest or /ingest. The previous
# implementation built a new pipeline per call AND reindexed two demo docs
# on every request, which duplicated data, lost the real corpus, and made
# the streaming response useless for anything other than smoke tests.
_RAG_PIPELINE: Optional[RAGPipeline] = None
_RAG_PIPELINE_LOCK = __import__("threading").Lock()


def get_rag_pipeline() -> RAGPipeline:
    """Get or lazily build the process-wide RAG pipeline.

    Uses an in-memory vector store by default. Callers that want persistence
    can replace this with a Chroma-backed pipeline by mutating
    ``_RAG_PIPELINE`` (e.g. in startup hooks).
    """
    global _RAG_PIPELINE
    if _RAG_PIPELINE is None:
        with _RAG_PIPELINE_LOCK:
            if _RAG_PIPELINE is None:
                _RAG_PIPELINE = build_default_rag_pipeline(store_type="memory")
    return _RAG_PIPELINE


def reset_rag_pipeline() -> None:
    """Drop the cached pipeline. Tests use this to start each case fresh."""
    global _RAG_PIPELINE
    with _RAG_PIPELINE_LOCK:
        _RAG_PIPELINE = None


def _memory_db_path() -> str:
    base = os.environ.get("AI_MEMORY_PATH", "data/ai_memory.sqlite")
    Path(base).parent.mkdir(parents=True, exist_ok=True)
    return base


async def _memory_manager(agent_id: str = "default", tenant_id: str = "default") -> MemoryManager:
    db = MemoryDB(_memory_db_path())
    await db.init()
    return MemoryManager(db, agent_id=agent_id, tenant_id=tenant_id)


# ---------- Schemas ----------

class ChatRequest(BaseModel):
    message: str
    agent: str = "coordinator"
    account_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    agent: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatStreamRequest(ChatRequest):
    pass


class IngestRequest(BaseModel):
    path: str
    persist: bool = True


class IngestTextRequest(BaseModel):
    texts: List[str]
    source: str = "inline"


class IngestTextResponse(BaseModel):
    chunks: int
    source: str


class IngestResponse(BaseModel):
    chunks: int
    documents: int
    source: str


class RAGQueryRequest(BaseModel):
    question: str
    top_k: int = 5
    agent_id: str = "default"


class RAGQueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float


class MemoryAddRequest(BaseModel):
    content: str
    memory_type: str = "short"
    importance: float = 0.5
    agent_id: str = "default"
    tenant_id: str = "default"


class MemoryRecallRequest(BaseModel):
    query: str
    memory_types: List[str] = Field(default_factory=lambda: ["short", "long", "semantic"])
    agent_id: str = "default"
    tenant_id: str = "default"


class MemoryResponse(BaseModel):
    success: bool
    data: Any = None
    message: str = ""


class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    success: bool
    result: Any = None
    error: Optional[str] = None


# ---------- Routes ----------

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Route a task to the appropriate agent graph and persist the exchange."""
    if request.agent == "content_creator":
        agent = ContentAgent()
        result = await agent.create_content(request.message)
        return ChatResponse(
            response=result.get("body") or str(result),
            agent=request.agent,
            metadata={"draft": result},
        )
    if request.agent == "data_analyst":
        agent = AnalysisAgent()
        result = await agent.analyze_account(request.account_id or "default")
        return ChatResponse(
            response=str(result),
            agent=request.agent,
            metadata={"analysis": result},
        )
    coord = CoordinatorAgent()
    final = await coord.coordinate_task(request.message, account_id=request.account_id)
    return ChatResponse(
        response=str(final),
        agent="coordinator",
        metadata={"final": final},
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatStreamRequest) -> StreamingResponse:
    """Stream the RAG answer as Server-Sent Events."""
    pipeline = get_rag_pipeline()

    async def event_source() -> AsyncIterator[str]:
        async for token in pipeline.query_stream(request.message, top_k=3):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.post("/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest) -> IngestResponse:
    """Load documents from a directory and index them into the default RAG pipeline."""
    src = Path(request.path)
    if not src.exists():
        raise HTTPException(status_code=404, detail=f"path not found: {request.path}")
    loader = DocumentLoader()
    docs = loader.load(request.path)
    splitter = TextSplitter()
    chunks = splitter.split_documents(docs)
    pipeline = get_rag_pipeline()
    pipeline.index_documents([
        {"content": c.content, "source": c.metadata.get("source", request.path)}
        for c in chunks
    ])
    return IngestResponse(
        chunks=len(chunks),
        documents=len(docs),
        source=request.path,
    )


@router.post("/rag/ingest_text", response_model=IngestTextResponse)
async def rag_ingest_text(request: IngestTextRequest) -> IngestTextResponse:
    """Index raw text strings into the singleton RAG pipeline.

    Useful for tests and quick demos where the caller doesn't want to drop
    a file on disk. Documents are split with the default TextSplitter and
    appended to whatever's already in the pipeline.
    """
    if not request.texts:
        raise HTTPException(status_code=400, detail="texts must not be empty")
    splitter = TextSplitter()
    all_chunks = []
    for t in request.texts:
        all_chunks.extend(splitter.split_text(t))
    pipeline = get_rag_pipeline()
    pipeline.index_documents([
        {"content": c.content, "source": request.source}
        for c in all_chunks
    ])
    return IngestTextResponse(chunks=len(all_chunks), source=request.source)


@router.post("/rag/reset")
async def rag_reset() -> Dict[str, str]:
    """Drop the cached RAG pipeline. Mainly for tests."""
    reset_rag_pipeline()
    return {"status": "reset"}


@router.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest) -> RAGQueryResponse:
    pipeline = get_rag_pipeline()
    result = await pipeline.query(request.question, top_k=request.top_k)
    return RAGQueryResponse(
        answer=result.answer,
        sources=result.sources,
        confidence=result.confidence,
    )


@router.post("/memory/add", response_model=MemoryResponse)
async def memory_add(request: MemoryAddRequest) -> MemoryResponse:
    mgr = await _memory_manager(agent_id=request.agent_id, tenant_id=request.tenant_id)
    item_id = await mgr.add(
        content=request.content,
        importance=request.importance,
        memory_type=request.memory_type,
    )
    return MemoryResponse(success=True, data={"id": item_id}, message="added")


@router.post("/memory/recall", response_model=MemoryResponse)
async def memory_recall(request: MemoryRecallRequest) -> MemoryResponse:
    mgr = await _memory_manager(agent_id=request.agent_id, tenant_id=request.tenant_id)
    results = await mgr.recall(request.query, memory_types=request.memory_types)
    return MemoryResponse(success=True, data=results, message="recalled")


@router.post("/memory/consolidate", response_model=MemoryResponse)
async def memory_consolidate(request: MemoryAddRequest) -> MemoryResponse:
    mgr = await _memory_manager(agent_id=request.agent_id, tenant_id=request.tenant_id)
    count = await mgr.consolidate(threshold=request.importance)
    return MemoryResponse(success=True, data={"consolidated": count}, message="consolidated")


@router.post("/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest) -> ToolCallResponse:
    _ensure_tools_registered()
    result = await tool_registry.execute(request.tool_name, **request.arguments)
    return ToolCallResponse(
        success=result.success,
        result=result.data,
        error=result.error,
    )


@router.get("/tools")
async def list_tools() -> Dict[str, List[Dict[str, Any]]]:
    _ensure_tools_registered()
    return {"tools": tool_registry.get_all_definitions()}


@router.get("/agents")
async def list_agents() -> Dict[str, List[str]]:
    return {"agents": ["coordinator", "content_creator", "data_analyst"]}


@router.get("/status")
async def ai_status() -> Dict[str, Any]:
    _ensure_tools_registered()
    return {
        "status": "running",
        "version": "2.0.0",
        "features": {
            "langgraph": True,
            "rag": True,
            "pdf_docx_ingest": True,
            "streaming": True,
            "memory_sqlite": True,
            "mcp_stdio": True,
            "cross_encoder_rerank": True,
        },
        "tools_registered": len(tool_registry.list_tools()),
    }