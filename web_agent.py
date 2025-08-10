from __future__ import annotations

from typing import Any, Dict, List, Optional

import os

from dotenv import load_dotenv  # type: ignore

load_dotenv()


def _require_dependency(import_name: str, pip_name: Optional[str] = None) -> None:
    try:
        __import__(import_name)
    except ImportError as exc:
        pkg = pip_name or import_name
        raise ImportError(
            f"Missing optional dependency '{import_name}'. Install with: pip install {pkg}"
        ) from exc


def _lazy_imports() -> None:
    _require_dependency("tavily", "tavily-python")


@traceback(name="web._summarize_with_llm", category="llm")
def _summarize_with_llm(question: str, snippets: List[str]) -> str:
    try:
        from llm_utils import call_anthropic

        joined = "\n\n".join(f"Source {i+1}: {s}" for i, s in enumerate(snippets) if s)
        prompt = (
            "You are a helpful web research assistant.\n"
            "Using the sources below, write a concise, well-cited answer.\n"
            "Cite sources inline like [1], [2] referencing the source indices.\n\n"
            f"Question: {question}\n\nSources:\n{joined}\n\nAnswer:"
        )
        return call_anthropic(system_prompt="", user_message=prompt, max_tokens=600)  # type: ignore[no-any-return]
    except Exception:
        # If LLM fails for any reason, just return an empty answer and rely on sources.
        return ""


try:
    from observability import trace, traceback  # type: ignore
except Exception:
    def trace(*args, **kwargs):  # type: ignore
        def _decorator(fn):
            return fn
        return _decorator
    def traceback(*args, **kwargs):  # type: ignore
        def _decorator(fn):
            return fn
        return _decorator


@trace(name="agent.execute_web_agent", category="agent")
def execute_web_agent(user_question: str, max_results: int = 5) -> Dict[str, Any]:
    """Run a Tavily web search and return a summarized answer with sources.

    Returns a dict like: {"answer": str, "sources": List[...], "count": int, "query": str}
    or {"error": str} on failure.
    """
    try:
        _lazy_imports()
        from tavily import TavilyClient  # type: ignore

        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return {"error": "Missing TAVILY_API_KEY in environment."}

        client = TavilyClient(api_key=api_key)
        # Perform search
        search = client.search(query=user_question, max_results=max_results, search_depth="advanced")
        results: List[Dict[str, Any]] = search.get("results") or []

        # Normalize sources
        sources = []
        snippets: List[str] = []
        for res in results:
            title = res.get("title") or ""
            url = res.get("url") or ""
            content = res.get("content") or ""
            sources.append({"title": title, "url": url, "snippet": content[:500]})
            if content:
                snippets.append(content)

        answer = _summarize_with_llm(user_question, snippets[:6])

        return {
            "query": user_question,
            "answer": answer,
            "sources": sources,
            "count": len(sources),
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"} 