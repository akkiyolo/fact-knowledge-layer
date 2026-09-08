import pymupdf
import sys

doc = pymupdf.open("data/sample/03-delhivery-q4-fy24-earnings-presentation.pdf")
total_text = ""
for page in doc:
    total_text += page.get_text()

print(f"Total characters: {len(total_text)}")
print(f"First 500 chars:\n{total_text[:500]}")

chunks = []
for page in doc:
    text = page.get_text().strip()
    if text:
        chunks.append(text)

print(f"Total chunks with text: {len(chunks)}")
if len(chunks) > 2:
    mid = len(chunks) // 2
    chunks = chunks[mid:mid+2]
    
for i, chunk in enumerate(chunks):
    print(f"--- Chunk {i} ---\n{chunk[:200]}...\n")
