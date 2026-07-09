"""Document loader for various file formats."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Document:
    """Represents a loaded document."""
    content: str
    metadata: dict
    source: str


class BaseLoader(ABC):
    """Abstract base class for document loaders."""

    @abstractmethod
    def load(self, path: str) -> List[Document]:
        """Load documents from a path."""
        pass


class TextLoader(BaseLoader):
    """Load plain text files."""

    def load(self, path: str) -> List[Document]:
        """Load text file."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return [Document(
            content=content,
            metadata={"source": path, "type": "text"},
            source=path
        )]


class MarkdownLoader(BaseLoader):
    """Load Markdown files."""

    def load(self, path: str) -> List[Document]:
        """Load markdown file."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return [Document(
            content=content,
            metadata={"source": path, "type": "markdown"},
            source=path
        )]


class DirectoryLoader:
    """Load all documents from a directory."""

    def __init__(self):
        self.loaders = {
            ".txt": TextLoader(),
            ".md": MarkdownLoader(),
        }

    def load(self, directory: str, recursive: bool = True) -> List[Document]:
        """Load all documents from a directory."""
        documents = []
        path = Path(directory)

        for file_path in path.rglob("*") if recursive else path.glob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                loader = self.loaders.get(ext)
                if loader:
                    try:
                        docs = loader.load(str(file_path))
                        documents.extend(docs)
                    except Exception:
                        pass  # Skip files that can't be loaded

        return documents


class DocumentLoader:
    """Main document loader with format detection."""

    def __init__(self):
        self.loaders = {
            ".txt": TextLoader(),
            ".md": MarkdownLoader(),
        }

    def load(self, source: str) -> List[Document]:
        """Load document(s) from source."""
        path = Path(source)

        if path.is_file():
            ext = path.suffix.lower()
            loader = self.loaders.get(ext)
            if loader:
                return loader.load(source)
            return []

        if path.is_dir():
            dir_loader = DirectoryLoader()
            return dir_loader.load(source)

        return []
