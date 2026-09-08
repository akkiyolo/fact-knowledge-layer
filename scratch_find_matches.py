from app.db.database import get_session_factory
from app.db.models import Claim, Document

factory = get_session_factory()
session = factory()
claims = session.query(Claim).all()
docs = {d.id: d.filename for d in session.query(Document).all()}

print("=== ALL 55 CLAIMS BY DOCUMENT ===")
for c in claims:
    d = docs.get(c.document_id, 'doc')
    print(f"[{d[:18]}] ID:{c.id[:8]} | Entity:{c.entity_text} | Attr:{c.attribute_raw} | Val:{c.value} {c.unit or ''} | Time:{c.time_scope}")
