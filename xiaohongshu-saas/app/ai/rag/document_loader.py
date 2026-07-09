"""Document loader for various file formats, including PDF/DOCX/MD/TXT."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass


# Encodings to try when reading a text-like file. We try UTF-8 first (with BOM
# stripped), then GBK (the dominant Windows Chinese encoding), then latin-1
# as a last resort that never raises.
_TEXT_ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "gbk", "gb18030", "big5", "latin-1")


def _read_text_with_fallback(path: str) -> str:
    """Read a text file, trying common encodings until one decodes cleanly."""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in _TEXT_ENCODING_CANDIDATES:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # Should be unreachable: latin-1 accepts any byte. Be paranoid anyway.
    return raw.decode("utf-8", errors="replace")


@dataclass
class Document:
    """A loaded document."""
    content: str
    metadata: dict
    source: str


class BaseLoader(ABC):
    @abstractmethod
    def load(self, path: str) -> List[Document]:
        pass


class TextLoader(BaseLoader):
    def load(self, path: str) -> List[Document]:
        content = _read_text_with_fallback(path)
        return [Document(content=content, metadata={"source": path, "type": "text"}, source=path)]


class MarkdownLoader(BaseLoader):
    def load(self, path: str) -> List[Document]:
        content = _read_text_with_fallback(path)
        return [Document(content=content, metadata={"source": path, "type": "markdown"}, source=path)]


class PDFLoader(BaseLoader):
    """Load PDF files via langchain_community PyPDFLoader."""

    def load(self, path: str) -> List[Document]:
        try:
            from langchain_community.document_loaders import PyPDFLoader
        except ImportError as e:
            raise ImportError(
                "PDF support requires pypdf and langchain-community: pip install pypdf langchain-community"
            ) from e

        loader = PyPDFLoader(path)
        lc_docs = loader.load()
        return [
            Document(
                content=d.page_content,
                metadata={**d.metadata, "source": path, "type": "pdf"},
                source=path,
            )
            for d in lc_docs
        ]


class DocxLoader(BaseLoader):
    """Load DOCX files via docx2txt."""

    def load(self, path: str) -> List[Document]:
        try:
            import docx2txt
        except ImportError as e:
            raise ImportError("DOCX support requires docx2txt: pip install docx2txt") from e

        text = docx2txt.process(path)
        return [Document(content=text, metadata={"source": path, "type": "docx"}, source=path)]


class DirectoryLoader:
    """Load all supported documents from a directory."""

    DEFAULT_LOADERS: Dict[str, BaseLoader] = {
        ".txt": TextLoader(),
        ".md": MarkdownLoader(),
        ".pdf": PDFLoader(),
        ".docx": DocxLoader(),
    }

    def __init__(self, loaders: Optional[Dict[str, BaseLoader]] = None):
        self.loaders = loaders or self.DEFAULT_LOADERS

    def load(self, directory: str, recursive: bool = True) -> List[Document]:
        documents = []
        path = Path(directory)
        iterator = path.rglob("*") if recursive else path.glob("*")
        for file_path in iterator:
            if not file_path.is_file():
                continue
            ext = file_path.suffix.lower()
            loader = self.loaders.get(ext)
            if loader is None:
                continue
            try:
                documents.extend(loader.load(str(file_path)))
            except Exception:
                continue
        return documents


class DocumentLoader:
    """Top-level loader with format detection."""

    def __init__(self, loaders: Optional[Dict[str, BaseLoader]] = None):
        self.loaders = loaders or DirectoryLoader.DEFAULT_LOADERS

    def load(self, source: str) -> List[Document]:
        path = Path(source)
        if path.is_file():
            ext = path.suffix.lower()
            loader = self.loaders.get(ext)
            if loader:
                return loader.load(source)
            return []
        if path.is_dir():
            return DirectoryLoader(self.loaders).load(source)
        return []