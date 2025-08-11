from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

# Load .env variables if present
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass


def _get_anthropic_client():
    try:
        import anthropic  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Missing optional dependency 'anthropic'. Install with: pip install anthropic"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY must be set in environment")
    return anthropic.Anthropic(api_key=api_key)


def call_anthropic(
    system_prompt: str,
    user_message: str,
    model: str = "claude-3-5-sonnet-20240620",
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> str:
    client = _get_anthropic_client()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    # Anthropic returns content as a list of content blocks; join text blocks
    parts = []
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "".join(parts).strip()


def call_anthropic_json(
    system_prompt: str,
    user_message: str,
    model: str = "claude-3-5-sonnet-20240620",
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> Dict[str, Any]:
    """Ask the model to return a JSON object and parse it.

    We strongly instruct JSON-only output but also try to extract a JSON object
    if the model includes text around it.
    """
    json_system = (
        system_prompt
        + "\n\nYou MUST respond with a single JSON object only. No prose."
    )
    text = call_anthropic(
        system_prompt=json_system,
        user_message=user_message,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    # Optional debug logging of raw LLM output
    try:
        if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
            preview = text if len(text) <= 2000 else (text[:2000] + "... [truncated]")
            print("[LLM JSON] Raw response preview:\n" + preview)
    except Exception:
        pass
    # Fast path: direct JSON
    try:
        parsed = json.loads(text)
        try:
            if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
                print("[LLM JSON] Parsed object:", parsed)
        except Exception:
            pass
        return parsed
    except Exception:
        pass

    # Fallback: extract the first {...} object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            parsed = json.loads(candidate)
            try:
                if os.environ.get("LOG_LLM", "").lower() in {"1", "true", "yes", "on"}:
                    print("[LLM JSON] Parsed object (extracted):", parsed)
            except Exception:
                pass
            return parsed
        except Exception:
            pass
    raise ValueError("Model did not return valid JSON") 