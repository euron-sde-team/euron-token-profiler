"""Euron TokenProfiler SDK: traces, spans and generations with token and cost attribution.

from tokenprofiler_sdk import TokenProfiler, observe

profiler = TokenProfiler(base_url="http://localhost:8210", api_key="tp_...")

@observe(kind="agent")
def answer(question: str) -> str:
    with profiler.generation("draft", model="gpt-4o", input=question) as call:
        reply = ...
        call.update(output=reply, usage={"input": 812, "output": 96})
    return reply
"""

from tokenprofiler_sdk.client import TokenProfiler, get_client, observe
from tokenprofiler_sdk.handles import Span, Trace, current_span_id, current_trace_id
from tokenprofiler_sdk.prompts import Prompt, PromptVariableError
from tokenprofiler_sdk.usage import usage_from

__version__ = "0.1.0"

__all__ = [
    "Prompt",
    "PromptVariableError",
    "Span",
    "TokenProfiler",
    "Trace",
    "current_span_id",
    "current_trace_id",
    "get_client",
    "observe",
    "usage_from",
]
