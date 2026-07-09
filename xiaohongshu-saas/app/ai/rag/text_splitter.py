"""Text splitter for document chunking."""
from __future__ import annotations

import re
from typing import List, Callable
from dataclasses import dataclass

from app.ai.rag.document_loader import Document


@dataclass
class Chunk:
    """Represents a text chunk."""
    content: str
    metadata: dict
    chunk_index: int
    total_chunks: int


class TextSplitter:
    """Split text into overlapping chunks."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: List[str] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " "]

    def split_text(self, text: str, metadata: dict = None) -> List[Chunk]:
        """Split text into chunks."""
        if metadata is None:
            metadata = {}

        chunks = []
        start = 0
        text_len = len(text)
        chunk_index = 0

        # Safety: ensure chunk_overlap is less than chunk_size
        if self.chunk_overlap >= self.chunk_size:
            self.chunk_overlap = max(1, self.chunk_size // 2)

        max_iterations = text_len + 100
        iteration = 0

        while start < text_len and iteration < max_iterations:
            iteration += 1
            end = min(start + self.chunk_size, text_len)

            # Try to find a good split point
            if end < text_len:
                for sep in self.separators:
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        end = pos + len(sep)
                        break

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(
                    content=chunk_text,
                    metadata={**metadata, "start": start, "end": end},
                    chunk_index=chunk_index,
                    total_chunks=0
                ))
                chunk_index += 1

            # Advance start position - guarantee progress
            new_start = end - self.chunk_overlap
            if new_start <= start:
                new_start = start + 1
            start = new_start

        # Update total chunks
        for chunk in chunks:
            chunk.total_chunks = len(chunks)

        return chunks

    def split_documents(self, documents: List[Document]) -> List[Chunk]:
        """Split multiple documents into chunks."""
        all_chunks = []
        for doc in documents:
            chunks = self.split_text(doc.content, doc.metadata)
            all_chunks.extend(chunks)
        return all_chunks


class RecursiveTextSplitter(TextSplitter):
    """Advanced text splitter with recursive splitting."""

    def split_text(self, text: str, metadata: dict = None) -> List[Chunk]:
        """Split text using multiple strategies."""
        if len(text) <= self.chunk_size:
            return [Chunk(
                content=text,
                metadata=metadata or {},
                chunk_index=0,
                total_chunks=1
            )]

        return super().split_text(text, metadata)
