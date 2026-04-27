import os
import json
import urllib.request
from pathlib import Path

# Manual .env loading to be safe
env_path = Path(".env")
api_key = None
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("ANTHROPIC_API_KEY="):
            api_key = line.split("=", 1)[1].strip()

if not api_key:
    print("ANTHROPIC_API_KEY not found in .env")
    exit(1)

url = "https://api.anthropic.com/v1/models"
req = urllib.request.Request(url)
req.add_header("x-api-key", api_key)
req.add_header("anthropic-version", "2023-06-01")

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        models = data.get("data", [])
        print("Available Models:")
        for model in models:
            print(f"- {model['id']}")
except Exception as e:
    print(f"Error fetching models: {e}")
