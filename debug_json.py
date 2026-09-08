import os, re, json
from dotenv import load_dotenv
load_dotenv()
from app.services.llm_service import get_llm_service
from app.pipeline.nodes.extract_claims import _PROMPT_TEMPLATE
import pymupdf

doc = pymupdf.open('data/sample/03-delhivery-q4-fy24-earnings-presentation.pdf')
text = doc[15].get_text().strip()

prompt = _PROMPT_TEMPLATE.format(
    page_number=16,
    char_start=0,
    char_end=len(text),
    chunk_text=text
)
llm = get_llm_service()
raw = llm.generate(prompt)

with open("raw_output.txt", "w", encoding="utf-8") as f:
    f.write(raw)

print("Saved raw output. Length:", len(raw))

# Test parsing
try:
    d = json.loads(raw)
    print("Direct json.loads worked!")
except Exception as e:
    print("Direct json.loads failed:", e)

json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
if json_match:
    content = json_match.group(1).strip()
    try:
        d = json.loads(content)
        print("Code block json.loads worked! Keys:", d.keys())
    except Exception as e:
        print("Code block json.loads failed:", e)
        print("First 300 chars of code block:\n", content[:300])
        print("Last 300 chars of code block:\n", content[-300:])
else:
    print("No code block match!")
