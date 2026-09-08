from app.db.database import get_session_factory
from app.db.models import Claim, Document
import numpy as np

factory = get_session_factory()
session = factory()
claims = session.query(Claim).filter(Claim.status == "usable").all()
docs = {d.id: d.filename for d in session.query(Document).all()}

pairs = []
seen = set()

keywords = {"revenue", "pin", "customer", "customers", "centre", "centres", "facility", "facilities", "network", "freight", "capex", "ebitda", "employee", "employees", "service", "services", "volume", "parcels", "turnover", "expenditure"}

for i in range(len(claims)):
    for j in range(i + 1, len(claims)):
        c1 = claims[i]
        c2 = claims[j]
        if c1.document_id == c2.document_id:
            continue
            
        v1 = np.array(c1.embedding)
        v2 = np.array(c2.embedding)
        sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9))
        
        words1 = set((c1.entity_text + " " + c1.attribute_raw).lower().split())
        words2 = set((c2.entity_text + " " + c2.attribute_raw).lower().split())
        shared_kw = (words1 & words2) & keywords
        
        if sim >= 0.18 or shared_kw:
            key = tuple(sorted([c1.id, c2.id]))
            if key not in seen:
                seen.add(key)
                pairs.append((sim, list(shared_kw), c1, c2))

print(f"Total candidate pairs found: {len(pairs)}")
pairs.sort(key=lambda x: (len(x[1]) > 0, x[0]), reverse=True)
for sim, kw, c1, c2 in pairs[:15]:
    d1 = docs.get(c1.document_id, '')[:15]
    d2 = docs.get(c2.document_id, '')[:15]
    t1 = f"[{c1.entity_text}] {c1.attribute_raw} = {c1.value}"
    t2 = f"[{c2.entity_text}] {c2.attribute_raw} = {c2.value}"
    t1 = t1.encode('ascii', 'replace').decode('ascii')
    t2 = t2.encode('ascii', 'replace').decode('ascii')
    print(f"KW:{kw} Sim:{sim:.2f} | [{d1}] {t1[:40]} <==> [{d2}] {t2[:40]}")
