"""OpenAI-compatible LiteLLM HTTP client; credentials remain on the server."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from typing import Optional
import urllib.request


@dataclass(frozen=True)
class Completion:
    text: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: Optional[Decimal]
    request_id: str


def parse_cost(value):
    """Missing/invalid accounting is unknown, never silently zero."""
    try:
        cost = Decimal(value)
        return cost if cost.is_finite() and cost >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def complete(base_url, api_key, model, messages, max_tokens=1000, temperature=0.3):
    # No automatic retries: a retry can trigger another billable inference.
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        data=json.dumps({"model": model, "messages": messages, "stream": False,
                         "max_tokens": max_tokens, "temperature": temperature}).encode(),
    )
    with urllib.request.urlopen(request, timeout=150) as response:
        data = json.load(response)
        usage = data.get("usage") or {}
        return Completion(
            text=data["choices"][0]["message"].get("content") or "",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            cost_usd=parse_cost(response.headers.get("x-litellm-response-cost")),
            request_id=response.headers.get("x-litellm-call-id", data.get("id", "")),
        )
