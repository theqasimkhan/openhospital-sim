import json

with open(r'C:\Users\Qasim Khan\.gemini\antigravity\brain\c8fbbffe-43de-4467-b458-a9cb576eb845\.system_generated\steps\447\content.md') as f:
    content = f.read()

start = content.find('{')
data = json.loads(content[start:])

for job in data['jobs']:
    print("JOB:", job["name"], "=>", job["conclusion"])
    for step in job['steps']:
        if step['conclusion'] and step['conclusion'] not in ('success', 'skipped'):
            print("  FAILED STEP:", step["name"], "=>", step["conclusion"])
