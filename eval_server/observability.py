from __future__ import annotations

import json
import os
import threading
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

# Config
OBS_ENABLED = os.environ.get("LOGOS_OBS_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
OBS_URL = os.environ.get("LOGOS_OBS_URL", "http://127.0.0.1:5051")
OBS_TIMEOUT_SECS = float(os.environ.get("LOGOS_OBS_TIMEOUT_SECS", "2.0"))
OBS_MAX_PREVIEW = int(os.environ.get("LOGOS_OBS_MAX_PREVIEW", "2000"))
OBS_SAMPLING = float(os.environ.get("LOGOS_OBS_SAMPLING", "1.0"))  # 0.0-1.0

# Context
_current_trace_id: ContextVar[Optional[str]] = ContextVar("logos_trace_id", default=None)
_current_span_id: ContextVar[Optional[str]] = ContextVar("logos_span_id", default=None)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _preview(value: Any) -> str:
    try:
        text = repr(value)
    except Exception:
        try:
            text = json.dumps(value, default=str)
        except Exception:
            text = str(value)
    if len(text) > OBS_MAX_PREVIEW:
        return text[:OBS_MAX_PREVIEW] + "... [truncated]"
    return text


def _should_sample() -> bool:
    try:
        if OBS_SAMPLING >= 1.0:
            return True
        if OBS_SAMPLING <= 0.0:
            return False
        return (hash(f"{uuid4()}") % 10_000) / 10_000.0 < OBS_SAMPLING
    except Exception:
        return True


def _post_event_async(event: Dict[str, Any]) -> None:
    if not OBS_ENABLED or not _should_sample():
        return
    try:
        import requests  # type: ignore
    except Exception:
        return

    def _send() -> None:
        try:
            requests.post(
                f"{OBS_URL}/log",
                json=event,
                timeout=OBS_TIMEOUT_SECS,
            )
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


def log(event_type: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    trace_id = _current_trace_id.get() or str(uuid4())
    span_id = _current_span_id.get()
    payload = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "name": name,
        "trace_id": trace_id,
        "span_id": span_id,
        "metadata": metadata or {},
    }
    _post_event_async(payload)


def trace(name: Optional[str] = None, category: str = "function") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        span_name = name or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            if not OBS_ENABLED or not _should_sample():
                return func(*args, **kwargs)

            trace_id = kwargs.get("_trace_id") or _current_trace_id.get() or str(uuid4())
            parent_span = _current_span_id.get()
            span_id = str(uuid4())
            token_trace = _current_trace_id.set(trace_id)
            token_span = _current_span_id.set(span_id)
            start_ts = time.time()

            try:
                _post_event_async(
                    {
                        "timestamp": _now_iso(),
                        "event_type": "span_start",
                        "name": span_name,
                        "category": category,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span,
                        "args_preview": _preview(args),
                        "kwargs_preview": _preview({k: v for k, v in kwargs.items() if k != "_trace_id"}),
                    }
                )
                result = func(*args, **kwargs)
                duration_ms = int((time.time() - start_ts) * 1000)
                _post_event_async(
                    {
                        "timestamp": _now_iso(),
                        "event_type": "span_end",
                        "name": span_name,
                        "category": category,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span,
                        "status": "ok",
                        "duration_ms": duration_ms,
                        "result_preview": _preview(result),
                    }
                )
                return result
            except Exception as exc:
                duration_ms = int((time.time() - start_ts) * 1000)
                _post_event_async(
                    {
                        "timestamp": _now_iso(),
                        "event_type": "span_end",
                        "name": span_name,
                        "category": category,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span,
                        "status": "error",
                        "duration_ms": duration_ms,
                        "error_type": type(exc).__name__,
                        "error_message": _preview(exc),
                    }
                )
                raise
            finally:
                try:
                    _current_span_id.reset(token_span)
                    _current_trace_id.reset(token_trace)
                except Exception:
                    pass

        return _wrapper

    return _decorator


class trace_span:
    def __init__(self, name: str, category: str = "span", metadata: Optional[Dict[str, Any]] = None):
        self.name = name
        self.category = category
        self.metadata = metadata or {}
        self.trace_id: Optional[str] = None
        self.parent_span: Optional[str] = None
        self.span_id: Optional[str] = None
        self.start_ts: float = 0.0

    def __enter__(self):
        self.trace_id = _current_trace_id.get() or str(uuid4())
        self.parent_span = _current_span_id.get()
        self.span_id = str(uuid4())
        self.start_ts = time.time()
        _current_trace_id.set(self.trace_id)
        _current_span_id.set(self.span_id)
        _post_event_async(
            {
                "timestamp": _now_iso(),
                "event_type": "span_start",
                "name": self.name,
                "category": self.category,
                "trace_id": self.trace_id,
                "span_id": self.span_id,
                "parent_span_id": self.parent_span,
                "metadata": self.metadata,
            }
        )
        return self

    def __exit__(self, exc_type, exc, tb):
        duration_ms = int((time.time() - self.start_ts) * 1000)
        _post_event_async(
            {
                "timestamp": _now_iso(),
                "event_type": "span_end",
                "name": self.name,
                "category": self.category,
                "trace_id": self.trace_id,
                "span_id": self.span_id,
                "parent_span_id": self.parent_span,
                "status": "error" if exc else "ok",
                "duration_ms": duration_ms,
                "error_type": None if not exc else getattr(exc, "__class__", type(exc)).__name__,
                "error_message": None if not exc else _preview(exc),
            }
        )
        # Do not suppress exceptions
        return False


# Backwards-friendly API suggested by user
traceback = trace
logos_log = log 