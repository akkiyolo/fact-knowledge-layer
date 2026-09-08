import json

sample_truncated = """{
  "claims": [
    {"entity": {"text": "Delhivery"}, "attribute_raw": "revenue", "value": {"type": "number", "value": "1860"}, "unit": "Cr", "evidence": {"text": "1860"}},
    {"entity": {"text": "Delhivery"}, "attribute_raw": "EBITDA", "value": {"type": "number", "value": "205"}, "unit": "Cr", "evidence": {"text": "205"}},
    {"entity": {"text": "Delhivery"}, "attribute_raw": "margin", "value":
"""

def repair_truncated_claims_json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    
    # If it's a claims list, find the last complete claim '}'
    # But note that the string started with '{ "claims": ['
    # So we want to find the last complete object inside the array.
    last_brace = text.rfind('}')
    if last_brace != -1:
        # Check if the opening '{' for "claims" was before this
        truncated_slice = text[:last_brace + 1].strip()
        # Remove any trailing comma
        if truncated_slice.endswith(','):
            truncated_slice = truncated_slice[:-1].strip()
        
        # Now close the array and root object
        repaired = truncated_slice + "\n]}"
        try:
            return json.loads(repaired)
        except Exception as e:
            print("Repair attempt 1 error:", e)
            print("Repaired text was:\n", repaired[-150:])
    return {}

repaired = repair_truncated_claims_json(sample_truncated)
print('Repaired claims count:', len(repaired.get('claims', [])))
for c in repaired.get('claims', []):
    print(" - Claim:", c['entity']['text'], c['attribute_raw'], c['value'])
