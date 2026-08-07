import urllib.request
import json
import zipfile
import io

repo = "theqasimkhan/openhospital-sim"
url = f"https://api.github.com/repos/{repo}/actions/runs"

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        if not data['workflow_runs']:
            print("No runs found.")
            exit(0)
        
        run = data['workflow_runs'][0]
        print(f"Latest run ID: {run['id']}, Status: {run['status']}, Conclusion: {run['conclusion']}")
        
        jobs_url = run['jobs_url']
        req2 = urllib.request.Request(jobs_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req2) as resp2:
            jobs_data = json.loads(resp2.read().decode())
            for job in jobs_data['jobs']:
                if job['conclusion'] == 'failure':
                    print(f"\nJOB FAILED: {job['name']}")
                    for step in job['steps']:
                        if step['conclusion'] == 'failure':
                            print(f"  STEP FAILED: {step['name']}")
except Exception as e:
    print(f"Error: {e}")
