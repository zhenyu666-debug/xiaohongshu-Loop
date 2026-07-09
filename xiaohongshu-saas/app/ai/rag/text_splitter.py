"""Text splitter using LangChain's RecursiveCharacterTextSplitter as the primary path."""
from __future__ import annotations

from typing import List, Optional
from dataclasses import dataclass

from app.ai.rag.document_loader import Document


@dataclass
class Chunk:
    content: str
    metadata: dict
    chunk_index: int
    total_chunks: int


class TextSplitter:
    """Recursive character splitter. Defaults to LangChain's implementation."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]
        self._lc_splitter = None

    def _get_splitter(self):
        if self._lc_splitter is None:
            try:
                from langchain_text_splitters import RecursiveCharacterTextSplitter
                self._lc_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    separators=self.separators,
                )
            except ImportError:
                self._lc_splitter = None
        return self._lc_splitter

    def split_text(self, text: str, metadata: Optional[dict] = None) -> List[Chunk]:
        metadata = metadata or {}
        splitter = self._get_splitter()
        if splitter is not None:
            pieces = splitter.split_text(text)
            return [
                Chunk(
                    content=p,
                    metadata={**metadata, "chunk_index": i},
                    chunk_index=i,
                    total_chunks=len(pieces),
                )
                for i, p in enumerate(pieces)
            ]
        return self._split_fallback(text, metadata)

    def _split_fallback(self, text: str, metadata: dict) -> List[Chunk]:
        chunks: List[Chunk] = []
        start = 0
        text_len = len(text)
        idx = 0
        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            if end < text_len:
                for sep in self.separators:
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        end = pos + len(sep)
                        break
            piece = text[start:end].strip()
            if piece:
                chunks.append(Chunk(content=piece, metadata={**metadata, "chunk_index": idx}, chunk_index=idx, total_chunks=0))
                idx += 1
            new_start = end - self.chunk_overlap
            if new_start <= start:
                new_start = start + 1
            start = new_start
        for c in chunks:
            c.total_chunks = len(chunks)
        return chunks

    def split_documents(self, documents: List[Document]) -> List[Chunk]:
        all_chunks: List[Chunk] = []
        for doc in documents:
            all_chunks.extend(self.split_text(doc.content, doc.metadata))
        return all_chunks