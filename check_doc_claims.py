from app.db.database import get_session_factory
from app.db.models import Claim, Relation, Document
from app.services.llm_service import get_llm_service
from app.pipeline.state import ClaimData, CandidatePair
from app.pipeline.nodes.classify import _classify_pair
from app.pipeline.nodes.reconcile import reconcile_contradictions

factory = get_session_factory()
session = factory()
llm = get_llm_service()

# Let's inspect claims from each doc
docs = {d.id: d.filename for d in session.query(Document).all()}
claims = session.query(Claim).all()

doc_claims = {}
for c in claims:
    doc_claims.setdefault(docs.get(c.document_id, "unknown"), []).append(c)

for doc_name, c_list in doc_claims.items():
    print(f"=== {doc_name} ({len(c_list)} claims) ===")
    for c in c_list[:5]:
        print(f"  [{c.id[:8]}] {c.entity_text} | {c.attribute_raw} = {c.value} ({c.time_scope})")
