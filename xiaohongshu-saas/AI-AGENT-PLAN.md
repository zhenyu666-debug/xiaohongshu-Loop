---
name: xhs-ai-agent-platform
overview: AI Agent plan for xhs-saas
---

# xhs-saas AI Agent Platform Plan

## Overview
Build AI Agent platform with:
- LangChain, LlamaIndex, LangGraph
- RAG: text splitting, embedding, vector search, reranking, generation
- Function Calling: tool orchestration, task decomposition
- MCP Protocol: Model Context Protocol
- Memory: short-term, long-term, episodic, semantic

## Architecture

Frontend -> FastAPI Backend -> AI Modules
                                - RAG Engine
                                - Function Calling
                                - Multi-Agent
                                - Memory Manager

## Directory Structure

xiaohongshu-saas/app/ai/
  agents/     - Agent definitions
  rag/       - RAG pipeline
  tools/     - Function calling tools
  memory/     - Memory management
  mcp/        - MCP protocol
  prompts/    - Prompt templates

## RAG Components

| Component | Function |
| --------- | -------- |
| document_loader | Load PDFs, DOCX, TXT |
| text_splitter | Split text into chunks |
| embedder | Embed text to vectors |
| vector_store | Store and search vectors |
| retriever | Hybrid retrieval |
| reranker | Re-rank results |
| generator | Generate answers |

## Tools

- search_content_ideas
- generate_title
- generate_body
- schedule_post
- get_account_stats
- suggest_hashtags

## Agent Roles

- PLANNER: Task decomposition
- EXECUTOR: Execute subtasks
- REVIEWER: Validate results
- COORDINATOR: Orchestrate agents

## API Endpoints

- POST /api/ai/chat
- GET /api/ai/agents
- GET /api/ai/tools
- POST /api/ai/rag/query

## Dependencies

ai = [
    openai>=1.30,
    anthropic>=0.20,
    langchain>=0.1,
    llama-index>=0.10,
    chromadb>=0.4,
]
