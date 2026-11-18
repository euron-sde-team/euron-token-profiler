"""Read token usage out of the response objects of the common LLM clients."""

from __future__ import annotations

from typing import Any


def _get(source: Any, name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def usage_from(response: Any) -> dict[str, int]:
    """Usage in the shape `update(usage=...)` takes, from a provider response.

    Understands OpenAI style (`prompt_tokens`, `completion_tokens`, cached tokens in
    `prompt_tokens_details`), Anthropic style (`input_tokens`, `output_tokens`,
    `cache_read_input_tokens`) and plain dicts of either. Returns only what it finds.
    """
    usage = _get(response, "usage") or response
    found: dict[str, int] = {}
    input_tokens = _int(_get(usage, "input_tokens"))
    if input_tokens is None:
        input_tokens = _int(_get(usage, "prompt_tokens"))
    output_tokens = _int(_get(usage, "output_tokens"))
    if output_tokens is None:
        output_tokens = _int(_get(usage, "completion_tokens"))
    cached = _int(_get(usage, "cache_read_input_tokens"))
    if cached is None:
        cached = _int(_get(_get(usage, "prompt_tokens_details"), "cached_tokens"))
    if input_tokens is not None:
        found["input"] = input_tokens
    if output_tokens is not None:
        found["output"] = output_tokens
    if cached:
        found["cached"] = cached
    return found
