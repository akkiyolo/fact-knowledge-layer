from app.db.database import get_session_factory
from app.db.models import Claim, Document

factory = get_session_factory()
session = factory()
claims = session.query(Claim).all()
docs = {d.id: d.filename for d in session.query(Document).all()}
for c in claims:
    doc_name = docs.get(c.document_id, "doc")
    print(f"[{doc_name[:25]}] ID:{c.id[:8]} | Entity:{c.entity_text} | Attr:{c.attribute_raw} ({c.attribute_canonical}) | Val:{c.value} {c.unit or ''} | Time:{c.time_scope or ''}")
