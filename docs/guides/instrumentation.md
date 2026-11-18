# Instrumenting your application

Three ways in; all end in the same pipeline, so sampling, masking, pricing and attribution behave
the same.

## 1. The Python SDK

```bash
pip install tokenprofiler-sdk
```

```python
from tokenprofiler_sdk import TokenProfiler, observe, usage_from

profiler = TokenProfiler(base_url="http://localhost:8210", api_key="tp_...", environment="production")
prompt = profiler.get_prompt("refund-policy-answer")          # label production, cached 60 s


@observe(kind="agent", name="support-agent")
def answer(question: str, user_id: str) -> str:
    with profiler.trace("support.chat", user_id=user_id):
        with profiler.tool("vector_search") as search:
            docs = retrieve(question)
            search.update(output=docs)
        with profiler.generation("draft-reply", model="gpt-4o", prompt=prompt, input=question) as call:
            response = client.chat.completions.create(model="gpt-4o", messages=[...])
            call.update(output=response.choices[0].message.content, usage=usage_from(response))
        return response.choices[0].message.content
```

- Spans nest through `contextvars`: tools and generations inside an agent are attributed to it, in
  threads and in asyncio.
- A span left by an exception is recorded as failed and the exception propagates unchanged.
- Sending happens on a background thread with batching, retries and a bounded queue; the
  application is never blocked or failed by the profiler. `profiler.stats` shows sent, dropped and
  failed counts. Call `profiler.flush()` before a short-lived process exits.
- `span.mark_first_token()` records time to first token for streams.
- `Prompt.compile(**variables)` fills `{{variable}}` placeholders and raises when one is missing.

## 2. OpenTelemetry

No SDK needed: point any OTLP/HTTP exporter (JSON or protobuf, gzip is fine) at the API.

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:8210/v1/otlp"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer tp_..."
export OTEL_SERVICE_NAME="support-api"
```

Attributes understood (first match wins): the GenAI conventions `gen_ai.request.model`,
`gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`gen_ai.agent.name`, `gen_ai.tool.name`, `gen_ai.operation.name` (`chat`, `embeddings`,
`execute_tool`, `invoke_agent`); OpenInference (`llm.model_name`, `llm.token_count.*`,
`openinference.span.kind`); Traceloop (`traceloop.span.kind`). Add `tokenprofiler.prompt.name` and
`tokenprofiler.prompt.version` to attribute a prompt, `user.id` and `session.id` for the trace, and
`deployment.environment` on the resource. Libraries that follow the GenAI conventions (the OpenAI,
Anthropic and LangChain instrumentations) work without changes.

## 3. HTTP

`POST /v1/ingest` with `{"traces": [...], "spans": [...]}`; the exact fields are in the API docs at
`/docs`. Items are validated one by one, bad ones are listed under `rejected`, and sending a span
again replaces the earlier copy.

## What gets a cost

Only `generation` and `embedding` spans carry tokens and cost. If usage is missing it is estimated
from the payload and flagged "tokens estimated". The cost is taken from `cost` if you send it,
otherwise from the price table (see Models, Pricing); a model with no price is stored at zero and
marked. Add an override for negotiated rates or self-hosted models.

## Attribution

Name the agent with an `agent` span (or `gen_ai.agent.name`) and the tool with a `tool` span; every
model call below inherits them, so Agents and tools and Models add up to the same total.

## Good habits

- Send a request's spans in one batch; sampling keeps traces whole when it can see them together.
- Keep keys in servers, not browsers.
- Use `environment` to separate staging from production; the dashboards filter on it.
- Do not send secrets on purpose; masking is a safety net, not a plan.
