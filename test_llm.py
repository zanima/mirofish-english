from openai import OpenAI
import re, json

client = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
r = client.chat.completions.create(
    model='kimi-k2.5:cloud',
    messages=[
        {'role':'system','content':'You must output valid JSON format data only.'},
        {'role':'user','content':'Return a JSON object with entity_types array containing 2 items, each with name and description fields.'}
    ],
    response_format={'type':'json_object'},
    max_tokens=500,
    temperature=0.3
)
raw = r.choices[0].message.content
raw = re.sub(r'<think>[\s\S]*?</think>', '', raw).strip()
print('RAW FIRST 300:', repr(raw[:300]))
print()

# Simulate _clean_json_text
cleaned = (raw or '').strip()
cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
cleaned = re.sub(r'\n?```\s*$', '', cleaned)
cleaned = cleaned.strip()
print('CLEANED:', repr(cleaned[:300]))

try:
    parsed = json.loads(cleaned)
    print('PARSED OK:', list(parsed.keys()))
except Exception as e:
    print('PARSE FAILED:', e)
    # try extract
    start = cleaned.find('{')
    print('JSON starts at:', start)
    print('First 50 chars after start:', repr(cleaned[start:start+50]))
