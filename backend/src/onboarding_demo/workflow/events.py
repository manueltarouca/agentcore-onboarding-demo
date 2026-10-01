"""Events streamed to the UI. Every event is a plain dict with a `type` field."""
import time


def event(kind: str, **fields) -> dict:
    return {"type": kind, "at": round(time.time() * 1000), **fields}
