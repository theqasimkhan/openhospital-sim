import json

with open(r'C:\Users\Qasim Khan\.gemini\antigravity\brain\c8fbbffe-43de-4467-b458-a9cb576eb845\.system_generated\steps\459\content.md') as f:
    content = f.read()

start = content.find('{')
data = json.loads(content[start:])

for job in data['jobs']:
    if job['conclusion'] == 'failure':
        print("FAILED JOB ID:", job["id"])
        print("LOGS URL:", job["html_url"])
        for step in job['steps']:
            print("  STEP:", step["name"], "=>", step["conclusion"])
