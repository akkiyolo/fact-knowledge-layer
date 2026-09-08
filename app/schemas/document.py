"""Pydantic schemas for Document API."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    filename: str
    content_hash: str
    created_at: datetime
    metadata: Optional[dict] = None
    page_count: Optional[int] = None
    status: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_doc(cls, doc):
        return cls(
            id=doc.id,
            filename=doc.filename,
            content_hash=doc.content_hash,
            created_at=doc.created_at,
            metadata=doc.metadata_,
            page_count=doc.page_count,
            status=doc.status,
        )


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    message: str
    is_duplicate: bool = False
