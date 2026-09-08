import os, sys
from dotenv import load_dotenv
load_dotenv()

from app.services.llm_service import get_llm_service
from app.config import get_settings
from app.pipeline.nodes.extract_claims import _extract_from_chunk
from app.pipeline.state import ChunkData
import pymupdf

pdf_path = "data/sample/03-delhivery-q4-fy24-earnings-presentation.pdf"
doc = pymupdf.open(pdf_path)

print(f"Total pages: {len(doc)}")

# Look at pages and test extraction
llm = get_llm_service()
settings = get_settings()

for page_idx in [5, 10, 15]:
    text = doc[page_idx].get_text().strip()
    print(f"\n--- Testing Page {page_idx+1} (length {len(text)}) ---")
    print(text[:200].encode('ascii', errors='replace').decode('ascii'))
    
    chunk = ChunkData(
        chunk_id="test-chunk",
        page_number=page_idx + 1,
        char_start=0,
        char_end=len(text),
        text=text,
        metadata={"page_number": page_idx + 1}
    )
    
    try:
        claims = _extract_from_chunk(llm, chunk, settings)
        print(f"Extracted {len(claims)} claims!")
        for c in claims:
            print("  Claim:", c.entity_text, "|", c.attribute_raw, "|", c.value)
    except Exception as e:
        print("Extraction failed with error:", type(e), e)
