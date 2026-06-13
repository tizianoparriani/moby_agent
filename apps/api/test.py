import os, requests
from dotenv import load_dotenv
load_dotenv("/.env")

url = "https://api.anthropic.com/v1/messages"
print(url)
headers = {
    "x-api-key": os.environ["CLAUDE_API_KEY"],
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}
payload = {
    "model": "claude-sonnet-4-6",
    "max_tokens": 64,
    "messages": [
        {"role": "user", "content": "Rispondi esattamente con: OK"}
    ],
}
resp = requests.post(url, headers=headers, json=payload, timeout=30)
print(resp.status_code, resp.text)
resp.raise_for_status()
