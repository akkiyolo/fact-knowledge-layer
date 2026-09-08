"""
LangGraph pipeline definition.
Wires all nodes into an explicit staged graph.
"""

import logging
from langgraph.graph import StateGraph, END

from app.pipeline.state import PipelineState
from app.pipeline.nodes.ingest import ingest_document
from app.pipeline.nodes.extract_pdf import extract_pdf_content
from app.pipeline.nodes.chunk import create_chunks
from app.pipeline.nodes.extract_claims import extract_claims
from app.pipeline.nodes.validate_grounding import validate_grounding
from app.pipeline.nodes.canonicalize import canonicalize_attributes
from app.pipeline.nodes.embed import embed_claims
from app.pipeline.nodes.retrieve import retrieve_candidates
from app.pipeline.nodes.classify import classify_relations
from app.pipeline.nodes.reconcile import reconcile_contradictions
from app.pipeline.nodes.persist import persist_results

logger = logging.getLogger(__name__)


def _should_continue_after_ingest(state: PipelineState) -> str:
    """Route after ingestion: stop if duplicate, continue otherwise."""
    if state.get("is_duplicate"):
        return "persist"
    if state.get("status") == "failed":
        return END
    return "extract_pdf"


def _should_continue_after_stage(state: PipelineState) -> str:
    """Generic check: stop if failed."""
    if state.get("status") == "failed":
        return END
    return "continue"


def build_pipeline() -> StateGraph:
    """
    Build the fact extraction pipeline as a LangGraph StateGraph.

    Flow:
    ingest → extract_pdf → chunk → extract_claims → validate_grounding
    → canonicalize → embed → retrieve → classify → reconcile → persist
    """
    graph = StateGraph(PipelineState)

    # Add all nodes
    graph.add_node("ingest", ingest_document)
    graph.add_node("extract_pdf", extract_pdf_content)
    graph.add_node("chunk", create_chunks)
    graph.add_node("extract_claims", extract_claims)
    graph.add_node("validate_grounding", validate_grounding)
    graph.add_node("canonicalize", canonicalize_attributes)
    graph.add_node("embed", embed_claims)
    graph.add_node("retrieve", retrieve_candidates)
    graph.add_node("classify", classify_relations)
    graph.add_node("reconcile", reconcile_contradictions)
    graph.add_node("persist", persist_results)

    # Set entry point
    graph.set_entry_point("ingest")

    # Conditional after ingest (skip to persist if duplicate)
    graph.add_conditional_edges(
        "ingest",
        _should_continue_after_ingest,
        {
            "extract_pdf": "extract_pdf",
            "persist": "persist",
            END: END,
        },
    )

    # Linear flow for the rest
    graph.add_edge("extract_pdf", "chunk")
    graph.add_edge("chunk", "extract_claims")
    graph.add_edge("extract_claims", "validate_grounding")
    graph.add_edge("validate_grounding", "canonicalize")
    graph.add_edge("canonicalize", "embed")
    graph.add_edge("embed", "retrieve")
    graph.add_edge("retrieve", "classify")
    graph.add_edge("classify", "reconcile")
    graph.add_edge("reconcile", "persist")
    graph.add_edge("persist", END)

    return graph


# Compiled pipeline singleton
_pipeline = None


def get_pipeline():
    """Get the compiled pipeline."""
    global _pipeline
    if _pipeline is None:
        graph = build_pipeline()
        _pipeline = graph.compile()
        logger.info("Pipeline compiled successfully")
    return _pipeline


def run_pipeline(filename: str, file_content: bytes) -> PipelineState:
    """
    Run the full pipeline for a document.

    Args:
        filename: Original filename of the uploaded PDF
        file_content: Raw bytes of the PDF file

    Returns:
        Final pipeline state with all results
    """
    pipeline = get_pipeline()

    initial_state: PipelineState = {
        "filename": filename,
        "file_content": file_content,
        "errors": [],
        "warnings": [],
        "status": "starting",
    }

    logger.info("Starting pipeline for: %s", filename)

    try:
        result = pipeline.invoke(initial_state)
        logger.info(
            "Pipeline complete for %s: status=%s, claims=%d, relations=%d, errors=%d",
            filename,
            result.get("status", "unknown"),
            len(result.get("claims", [])),
            len(result.get("relations", [])),
            len(result.get("errors", [])),
        )
        return result
    except Exception as e:
        logger.error("Pipeline failed for %s: %s", filename, e, exc_info=True)
        return {
            **initial_state,
            "status": "failed",
            "errors": [{"stage": "pipeline", "error": str(e)}],
        }
