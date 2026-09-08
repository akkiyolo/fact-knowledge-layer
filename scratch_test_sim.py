import sys
from app.db.database import get_session_factory
from app.db.models import Claim, Document
import numpy as np

factory = get_session_factory()
session = factory()
claims = session.query(Claim).filter(Claim.status == "usable").all()
docs = {d.id: d.filename for d in session.query(Document).all()}

print(f"Total usable claims: {len(claims)}")

pairs = []
for i in range(len(claims)):
    for j in range(i + 1, len(claims)):
        c1 = claims[i]
        c2 = claims[j]
        if c1.document_id == c2.document_id:
            continue
        v1 = np.array(c1.embedding)
        v2 = np.array(c2.embedding)
        sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9))
        pairs.append((sim, c1, c2))

pairs.sort(key=lambda x: x[0], reverse=True)
print(f"Total cross-doc pairs: {len(pairs)}")
print("Top 20 cross-doc pairs by similarity:")
for sim, c1, c2 in pairs[:20]:
    t1 = f"{c1.entity_text} - {c1.attribute_raw} = {c1.value}"
    t2 = f"{c2.entity_text} - {c2.attribute_raw} = {c2.value}"
    d1 = docs.get(c1.document_id, '')[:15]
    d2 = docs.get(c2.document_id, '')[:15]
    # safe print ascii
    t1 = t1.encode('ascii', 'replace').decode('ascii')
    t2 = t2.encode('ascii', 'replace').decode('ascii')
    print(f"Sim {sim:.3f} | [{d1}] {t1[:45]} <==> [{d2}] {t2[:45]}")
