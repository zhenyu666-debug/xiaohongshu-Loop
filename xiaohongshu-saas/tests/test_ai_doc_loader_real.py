"""End-to-end loader tests using real binary fixtures.

These build small PDF/DOCX/text fixtures in tmp_path at session start, then
exercise the actual loaders (PyPDFLoader + docx2txt + custom text fallback).
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from app.ai.rag.document_loader import (
    DirectoryLoader,
    DocxLoader,
    DocumentLoader,
    PDFLoader,
    TextLoader,
)


# --------------------------------------------------------------------------- #
# Fixtures (generated once per test session, reused across tests)
# --------------------------------------------------------------------------- #

def _build_pdf(path: Path) -> None:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    c = canvas.Canvas(str(path), pagesize=letter)
    # Page 1
    c.drawString(72, 720, "Sample PDF Title")
    c.drawString(72, 700, "Page 1: Xiaohongshu content strategies")
    c.showPage()
    # Page 2
    c.drawString(72, 720, "Page 2: Engagement metrics")
    c.drawString(72, 700, "Watch time and CTR benchmarks")
    c.showPage()
    c.save()


def _build_docx(path: Path) -> None:
    ct = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        '<w:p><w:r><w:t>Xiaohongshu Posting Guide</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>Use 2-3 short paragraphs with blank lines between them.</w:t></w:r></w:p>'
        '</w:body>'
        '</w:document>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("doc_fixtures")
    _build_pdf(d / "sample.pdf")
    _build_docx(d / "sample.docx")
    (d / "plain.txt").write_text("Plain UTF-8 sample text.\n", encoding="utf-8")
    (d / "chinese_gbk.txt").write_bytes("\u4e2d\u6587\u5c0f\u7ea2\u4e66\u5185\u5bb9\u6307\u5357\n".encode("gbk"))
    return d


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_pdf_loader_reads_real_pdf(fixtures_dir):
    docs = PDFLoader().load(str(fixtures_dir / "sample.pdf"))
    assert len(docs) == 2, f"expected 2 pages, got {len(docs)}"
    assert "Xiaohongshu content strategies" in docs[0].content
    assert "Engagement metrics" in docs[1].content
    # pdf loader exposes page index in metadata
    assert docs[0].metadata["type"] == "pdf"
    assert docs[0].metadata["source"].endswith("sample.pdf")


def test_docx_loader_reads_real_docx(fixtures_dir):
    docs = DocxLoader().load(str(fixtures_dir / "sample.docx"))
    assert len(docs) == 1
    content = docs[0].content
    assert "Xiaohongshu Posting Guide" in content
    assert "blank lines between them" in content
    assert docs[0].metadata["type"] == "docx"


def test_text_loader_handles_utf8(fixtures_dir):
    docs = TextLoader().load(str(fixtures_dir / "plain.txt"))
    assert docs[0].content.startswith("Plain UTF-8")


def test_text_loader_falls_back_to_gbk(fixtures_dir):
    """A Windows-saved Chinese text file must not crash; content should decode."""
    docs = TextLoader().load(str(fixtures_dir / "chinese_gbk.txt"))
    # The original characters must round-trip.
    assert "\u4e2d\u6587\u5c0f\u7ea2\u4e66\u5185\u5bb9\u6307\u5357" in docs[0].content


def test_directory_loader_loads_all_supported(fixtures_dir):
    docs = DirectoryLoader().load(str(fixtures_dir))
    types = {d.metadata["type"] for d in docs}
    assert "text" in types
    assert "pdf" in types
    assert "docx" in types
    # Total: 2 plain-text files + 1 docx + 2 pdf pages = 5
    assert len(docs) == 5, f"expected 5 docs, got {len(docs)}"


def test_document_loader_routes_by_extension(fixtures_dir):
    loader = DocumentLoader()
    pdf_docs = loader.load(str(fixtures_dir / "sample.pdf"))
    assert len(pdf_docs) == 2
    docx_docs = loader.load(str(fixtures_dir / "sample.docx"))
    assert len(docx_docs) == 1
    txt_docs = loader.load(str(fixtures_dir / "plain.txt"))
    assert len(txt_docs) == 1
    assert txt_docs[0].metadata["type"] == "text"
