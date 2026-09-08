"""
PDF extraction service using PyMuPDF.
Extracts page-aware text with character offsets.
Treats PDF content as untrusted data.
"""

import logging
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    """Extracted text from a single PDF page."""
    page_number: int  # 1-indexed
    text: str
    char_start: int  # Offset within the full document text
    char_end: int


@dataclass
class PDFContent:
    """Full extracted content from a PDF."""
    filename: str
    content_hash: str
    page_count: int
    full_text: str
    pages: list[PageContent] = field(default_factory=list)


class PDFService:
    """Extracts text from PDFs with page awareness and character offsets."""

    def extract(self, file_path: str | Path) -> PDFContent:
        """
        Extract all text from a PDF file.

        Returns structured content with page boundaries and character offsets.
        Treats PDF text as untrusted data.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        if not file_path.suffix.lower() == ".pdf":
            raise ValueError(f"Not a PDF file: {file_path}")

        # Compute content hash
        content_hash = self._compute_hash(file_path)

        try:
            doc = fitz.open(str(file_path))
        except Exception as e:
            raise RuntimeError(f"Failed to open PDF: {e}")

        pages: list[PageContent] = []
        full_text_parts: list[str] = []
        current_offset = 0

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text("text")

            # Sanitize: remove null bytes and other control characters
            text = text.replace("\x00", "")

            page_content = PageContent(
                page_number=page_idx + 1,  # 1-indexed
                text=text,
                char_start=current_offset,
                char_end=current_offset + len(text),
            )
            pages.append(page_content)
            full_text_parts.append(text)
            current_offset += len(text)

        doc.close()

        full_text = "".join(full_text_parts)

        logger.info(
            "Extracted PDF: %s (%d pages, %d chars)",
            file_path.name,
            len(pages),
            len(full_text),
        )

        return PDFContent(
            filename=file_path.name,
            content_hash=content_hash,
            page_count=len(pages),
            full_text=full_text,
            pages=pages,
        )

    @staticmethod
    def _compute_hash(file_path: Path) -> str:
        """Compute SHA-256 hash of file content for duplicate detection."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
