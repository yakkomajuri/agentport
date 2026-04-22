"""Shared HTTP response helper for Resend custom tools."""

import json

import httpx

_BASE_URL = "https://api.resend.com"


def response_to_result(response: httpx.Response) -> dict:
    """Convert an httpx response to an MCP-compatible result dict."""
    if response.status_code >= 400:
        error_text = response.text
        try:
            error_text = json.dumps(response.json())
        except Exception:
            pass
        return {
            "content": [
                {"type": "text", "text": f"API error ({response.status_code}): {error_text}"}
            ],
            "isError": True,
        }
    try:
        return {
            "content": [{"type": "text", "text": json.dumps(response.json(), indent=2)}],
            "isError": False,
        }
    except Exception:
        return {
            "content": [{"type": "text", "text": response.text or "(empty response)"}],
            "isError": False,
        }
