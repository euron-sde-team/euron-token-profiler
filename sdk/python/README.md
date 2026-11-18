# tokenprofiler-sdk

The Python SDK for [Euron TokenProfiler](../../README.md): traces, spans and generations with
token and cost attribution per prompt, model, agent and tool.

```bash
pip install tokenprofiler-sdk
```

```python
from tokenprofiler_sdk import TokenProfiler, observe, usage_from

profiler = TokenProfiler(base_url="http://localhost:8210", api_key="tp_...")

prompt = profiler.get_prompt("refund-policy-answer")  # production label by default


@observe(kind="agent", name="support-agent")
def answer(question: str) -> str:
    with profiler.tool("vector_search") as search:
        docs = ["..."]
        search.update(output=docs)
    with profiler.generation("draft-reply", model="gpt-4o", prompt=prompt, input=question) as call:
        response = client.chat.completions.create(...)  # your provider call
        call.update(output=response.choices[0].message.content, usage=usage_from(response))
    return response.choices[0].message.content


answer("Where is my order?")
profiler.flush()
```

- Spans nest through `contextvars`, so tools and generations inside an `@observe` agent are
  attributed to it, in threads and in `asyncio`.
- Sending happens on a background thread. A full queue drops events (see `profiler.stats`)
  and a failing server is retried with backoff; nothing here raises into your application.
- A span that leaves its `with` block through an exception is recorded as failed, and the
  exception propagates unchanged.
- OpenTelemetry users do not need this package: point any OTLP/HTTP exporter at
  `<api>/v1/otlp`. See the API keys page of the dashboard for the exact settings.

Development: `uv sync && uv run pytest`.
