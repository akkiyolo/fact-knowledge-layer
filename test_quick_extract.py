import os, json
from dotenv import load_dotenv
load_dotenv()
import google.generativeai as genai
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
import pymupdf

doc = pymupdf.open('data/sample/03-delhivery-q4-fy24-earnings-presentation.pdf')
text = doc[13].get_text().strip()

prompt = """You are a precise fact extraction system.
Extract at most 10 of the most significant atomic claims from this page (prioritize key annual/quarterly financial metrics, revenue, EBITDA, margins, and totals).
Output valid JSON matching this schema:
{
  "claims": [
    {
      "entity": {"text": "Delhivery", "type": "company"},
      "attribute_raw": "revenue",
      "value": {"type": "number", "value": "8142"},
      "unit": "Cr",
      "time_scope": {"text": "FY24", "start": null, "end": null},
      "scope": null,
      "qualifiers": [],
      "evidence": {"text": "8,142", "page": 14, "char_start": 0, "char_end": 0},
      "confidence": 1.0
    }
  ]
}

Source text:
""" + text

m = genai.GenerativeModel('gemini-3.5-flash-lite')
r = m.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.1, response_mime_type='application/json', max_output_tokens=4096))
print('Finish reason:', r.candidates[0].finish_reason)
print('Text length:', len(r.text))
data = json.loads(r.text)
print('SUCCESS! Extracted claims count:', len(data.get('claims', [])))
for c in data.get('claims', [])[:5]:
    print(' - Claim:', c['entity']['text'], '|', c['attribute_raw'], '|', c['value']['value'], c.get('unit'))
