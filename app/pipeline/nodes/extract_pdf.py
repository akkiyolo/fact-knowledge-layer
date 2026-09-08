"""
Node: extract_pdf_content
Extracts page-aware text from PDF using PyMuPDF.
"""

import logging
from app.pipeline.state import PipelineState
from app.services.pdf_service import PDFService

logger = logging.getLogger(__name__)


def extract_pdf_content(state: PipelineState) -> PipelineState:
    """Extract text from PDF with page boundaries and character offsets."""
    errors = state.get("errors", [])

    # Skip if duplicate
    if state.get("is_duplicate"):
        return state

    file_path = state.get("file_path", "")
    if not file_path:
        errors.append({"stage": "extract_pdf", "error": "No file path"})
        return {**state, "errors": errors, "status": "failed"}

    try:
        pdf_service = PDFService()
        content = pdf_service.extract(file_path)

        pages_data = []
        for page in content.pages:
            pages_data.append({
                "page_number": page.page_number,
                "text": page.text,
                "char_start": page.char_start,
                "char_end": page.char_end,
            })

        logger.info(
            "PDF extracted: %d pages, %d total chars",
            content.page_count,
            len(content.full_text),
        )

        return {
            **state,
            "full_text": content.full_text,
            "page_count": content.page_count,
            "pages": pages_data,
            "status": "extracted",
            "errors": errors,
        }

    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        errors.append({"stage": "extract_pdf", "error": str(e)})
        return {**state, "errors": errors, "status": "failed"}
