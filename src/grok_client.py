import os
import requests
from typing import Optional

GROK_API_KEY = os.environ.get("GROK_API_KEY")
# Replace the endpoint below with the real Grok endpoint/route for your account.
GROK_ENDPOINT = os.environ.get("GROK_ENDPOINT", "https://api.grok.example/v1/generate")


class GrokError(RuntimeError):
    pass


def ask_grok(prompt: str, max_tokens: int = 512, timeout: int = 30) -> str:
    """Send a prompt to Grok and return the text result.

    This is a small template client. Replace GROK_ENDPOINT with the provider's
    real endpoint and adjust the response parsing to match the provider schema.
    """
    if not GROK_API_KEY:
        raise GrokError("GROK_API_KEY not set in environment")

    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "max_tokens": max_tokens,
    }

    resp = requests.post(GROK_ENDPOINT, json=payload, headers=headers, timeout=timeout)
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise GrokError(f"Grok request failed: {exc} - {resp.text}")

    data = resp.json()

    # Generic parsing: many LLM APIs return text under keys like 'text', 'result'
    if isinstance(data, dict):
        for k in ("text", "result", "output", "choices"):
            if k in data:
                v = data[k]
                # choices could be a list of dicts with 'text' fields
                if isinstance(v, list):
                    # try to extract first item's text
                    first = v[0]
                    if isinstance(first, dict) and "text" in first:
                        return first["text"]
                    return str(v)
                return str(v)
        # Fallback: stringify whole response
        return str(data)

    return str(data)
