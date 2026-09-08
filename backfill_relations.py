import logging
import numpy as np
from app.db.database import get_session_factory
from app.db.models import Claim, Relation, Document
from app.db.repositories import ClaimRepository, RelationRepository
from app.services.embedding_service import get_embedding_service
from app.pipeline.nodes.embed import _claim_to_embedding_text
from app.pipeline.state import ClaimData, CandidatePair
from app.pipeline.nodes.classify import _classify_pair
from app.pipeline.nodes.reconcile import reconcile_contradictions
from app.services.llm_service import get_llm_service
from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    factory = get_session_factory()
    session = factory()
    emb_service = get_embedding_service()
    llm = get_llm_service()
    settings = get_settings()

    # 1. Backfill embeddings for any claims missing them
    missing_claims = session.query(Claim).filter(Claim.embedding == None).all()
    if missing_claims:
        print(f"Generating embeddings for {len(missing_claims)} claims...")
        texts = []
        for c in missing_claims:
            dummy_cd = ClaimData(
                claim_id=c.id,
                chunk_id=c.chunk_id or "",
                entity_text=c.entity_text,
                entity_type=c.entity_type or "",
                attribute_raw=c.attribute_raw,
                attribute_canonical=c.attribute_canonical,
                value_type=c.value_type,
                value=c.value,
                evidence_text=c.evidence_text,
                evidence_page=c.evidence_page,
                evidence_char_start=c.evidence_char_start,
                evidence_char_end=c.evidence_char_end,
                extraction_confidence=c.extraction_confidence,
            )
            texts.append(_claim_to_embedding_text(dummy_cd))
        
        vecs = emb_service.embed(texts)
        for c, v in zip(missing_claims, vecs):
            c.embedding = v
        session.commit()
        print("Embeddings updated successfully.")

    # 2. Check relations across all documents
    rel_repo = RelationRepository(session)
    
    docs = session.query(Document).all()
    print(f"Total documents: {len(docs)}")
    
    existing_relations_count = session.query(Relation).count()
    print(f"Current relations in DB: {existing_relations_count}")
    
    all_claims = session.query(Claim).filter(Claim.status == "usable").all()
    print(f"Usable claims to evaluate for relations: {len(all_claims)}")
    
    # Meaningful entity/attribute concepts to cross-reference across financial docs
    keywords = {
        "revenue", "pin", "customer", "customers", "centre", "centres", 
        "facility", "facilities", "network", "freight", "capex", "ebitda", 
        "employee", "employees", "service", "services", "volume", "parcels", 
        "turnover", "expenditure", "points", "sale"
    }

    candidate_pairs = []
    seen_pairs = set()

    for i in range(len(all_claims)):
        for j in range(i + 1, len(all_claims)):
            c1 = all_claims[i]
            c2 = all_claims[j]
            
            # Must be from different documents
            if c1.document_id == c2.document_id:
                continue

            # Check if relation already exists in DB
            existing_rel = session.query(Relation).filter(
                ((Relation.source_claim_id == c1.id) & (Relation.target_claim_id == c2.id)) |
                ((Relation.source_claim_id == c2.id) & (Relation.target_claim_id == c1.id))
            ).first()
            if existing_rel:
                continue

            # Calculate cosine similarity
            v1 = np.array(c1.embedding)
            v2 = np.array(c2.embedding)
            score = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9))

            words1 = set((c1.entity_text + " " + c1.attribute_raw).lower().split())
            words2 = set((c2.entity_text + " " + c2.attribute_raw).lower().split())
            shared_kw = (words1 & words2) & keywords

            # Candidate selection: good similarity OR shared domain keyword
            if score >= 0.16 or shared_kw:
                pair_key = tuple(sorted([c1.id, c2.id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                c1_data = ClaimData(
                    claim_id=c1.id,
                    chunk_id=c1.chunk_id or "",
                    entity_text=c1.entity_text,
                    entity_type=c1.entity_type or "",
                    attribute_raw=c1.attribute_raw,
                    attribute_canonical=c1.attribute_canonical,
                    value_type=c1.value_type,
                    value=c1.value,
                    unit=c1.unit or "",
                    time_scope=c1.time_scope,
                    scope=c1.scope or "",
                    qualifiers=c1.qualifiers or [],
                    evidence_text=c1.evidence_text,
                    evidence_page=c1.evidence_page,
                    evidence_char_start=c1.evidence_char_start,
                    evidence_char_end=c1.evidence_char_end,
                    extraction_confidence=c1.extraction_confidence,
                    grounding_confidence=c1.grounding_confidence,
                    status=c1.status,
                )
                c2_dict = {
                    "id": c2.id,
                    "entity_text": c2.entity_text,
                    "entity_type": c2.entity_type,
                    "attribute_raw": c2.attribute_raw,
                    "attribute_canonical": c2.attribute_canonical,
                    "value": c2.value,
                    "unit": c2.unit,
                    "time_scope": c2.time_scope,
                    "scope": c2.scope,
                    "evidence_text": c2.evidence_text,
                    "document_filename": c2.document.filename if c2.document else "",
                }
                pair = CandidatePair(
                    new_claim=c1_data,
                    existing_claim_id=c2.id,
                    existing_claim_data=c2_dict,
                    similarity_score=score,
                )
                candidate_pairs.append((len(shared_kw) > 0, score, pair))

    print(f"Found {len(candidate_pairs)} candidate cross-document pairs.")

    # Sort candidates prioritizing shared keywords and higher vector similarity
    candidate_pairs.sort(key=lambda x: (x[0], x[1]), reverse=True)
    unique_candidates = [p[2] for p in candidate_pairs]

    # Select top 20 candidate pairs for classification
    selected_candidates = unique_candidates[:20]
    print(f"Classifying {len(selected_candidates)} candidate pairs with {settings.google_model}...")

    classified_relations = []
    for i, pair in enumerate(selected_candidates):
        try:
            rel = _classify_pair(llm, pair)
            if rel:
                classified_relations.append(rel)
                print(f"Pair {i+1}: {rel.relation_type} (conf={rel.confidence:.2f}) - '{pair.new_claim.entity_text}' vs '{pair.existing_claim_data['entity_text']}'")
        except Exception as e:
            print(f"Classification failed for pair {i+1}: {e}")

    print(f"Classified {len(classified_relations)} relations.")

    # Run reconciliation node on classified relations
    dummy_state = {
        "claims": all_claims,
        "relations": classified_relations,
        "candidates": selected_candidates,
        "errors": [],
    }
    reconciled_state = reconcile_contradictions(dummy_state)
    final_relations = reconciled_state.get("relations", [])

    # Persist non-neutral relations (corroborates, contradicts, contradicts_reconciled)
    new_relations_created = 0
    for r in final_relations:
        if r.relation_type in ("corroborates", "contradicts", "contradicts_reconciled") or r.confidence >= 0.7:
            rel_repo.create(
                source_claim_id=r.source_claim_id,
                target_claim_id=r.target_claim_id,
                relation_type=r.relation_type,
                confidence=r.confidence,
                explanation=r.explanation,
                reasoning_factors=r.reasoning_factors,
                reconciling_factor=r.reconciling_factor,
                reconciliation_explanation=r.reconciliation_explanation,
            )
            new_relations_created += 1

    session.commit()
    print(f"\n=======================================================")
    print(f"SUCCESS! Created and committed {new_relations_created} relations to the database!")
    print(f"Total relations now in DB: {session.query(Relation).count()}")
    print(f"=======================================================\n")
    session.close()

if __name__ == "__main__":
    main()
