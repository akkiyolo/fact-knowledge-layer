from app.db.database import get_session_factory
from app.db.models import Claim, Document

factory = get_session_factory()
session = factory()
claims = session.query(Claim).all()
docs = {d.id: d.filename for d in session.query(Document).all()}

with open('scratch_claims.txt', 'w', encoding='utf-8') as f:
    for c in claims:
        d = docs.get(c.document_id, 'doc')
        unit = c.unit or ""
        f.write(f"[{d[:22]}] ID:{c.id[:8]} | Entity:{c.entity_text} | Attr:{c.attribute_raw} | Val:{c.value} {unit} | Scope:{c.scope} | Time:{c.time_scope}\n")
print("Done writing scratch_claims.txt")
