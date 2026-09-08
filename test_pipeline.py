import asyncio
from app.db.database import get_engine, ensure_pgvector, init_db

from app.config import get_settings

async def main():
    init_db()
    
    import sys
    print("Running pipeline on pdfs/01-delhivery-prospectus-2022-excerpt.pdf")
    # We will simulate the document upload process
    from app.services.llm_service import get_llm_service
    llm = get_llm_service()
    print("LLM Provider:", get_settings().llm_provider)
    
    # Let's see what the chunks from the middle look like
    import pymupdf
    pdf_path = Path("data/sample/03-delhivery-q4-fy24-earnings-presentation.pdf")
    doc = pymupdf.open(pdf_path)
    pages = []
    char_start = 0
    for page_num in range(len(doc)):
        text = doc[page_num].get_text()
        pages.append({
            "page_number": page_num + 1,
            "text": text,
            "char_start": char_start,
            "char_end": char_start + len(text)
        })
        char_start += len(text)
        
    print(f"Total pages: {len(pages)}")
    
    # simulate chunking
    from app.pipeline.nodes.chunk import create_chunks
    state = {"pages": pages}
    chunk_state = create_chunks(state)
    chunks = chunk_state["chunks"]
    print(f"Selected chunks count: {len(chunks)}")
    for i, c in enumerate(chunks):
        print(f"--- Chunk {i} (Page {c.page_number}) ---")
        print(c.text[:200] + "...")
        print("-------------------")
        
        # Test extraction
        from app.pipeline.nodes.extract_claims import _extract_from_chunk
        try:
            claims = _extract_from_chunk(llm, c, get_settings())
            print(f"Extracted claims: {len(claims)}")
            for cl in claims:
                print("  -", cl.entity_text, "|", cl.attribute_raw, "|", cl.value)
        except Exception as e:
            print("Extraction failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
