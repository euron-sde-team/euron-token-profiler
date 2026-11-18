/** Connection examples shown on the API keys page. Each runs as written once the key is real. */

export type SnippetInput = { apiUrl: string; key: string };

export function pythonSnippet({ apiUrl, key }: SnippetInput): string {
  return `pip install tokenprofiler-sdk

from tokenprofiler_sdk import TokenProfiler, observe

profiler = TokenProfiler(base_url="${apiUrl}", api_key="${key}")


@observe(kind="agent", name="support-agent")
def answer(question: str) -> str:
    with profiler.generation(
        "draft-reply",
        model="gpt-4o",
        input=question,
        prompt=("refund-policy-answer", 2),
    ) as call:
        reply = "..."  # your model call
        call.update(output=reply, usage={"input": 812, "output": 96})
    return reply


answer("Where is my order?")
profiler.flush()`;
}

export function otlpSnippet({ apiUrl, key }: SnippetInput): string {
  return `# Any OpenTelemetry SDK or collector, JSON or protobuf:
export OTEL_EXPORTER_OTLP_ENDPOINT="${apiUrl}/v1/otlp"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer ${key}"
export OTEL_SERVICE_NAME="support-api"

# GenAI conventions are understood: gen_ai.request.model, gen_ai.usage.input_tokens,
# gen_ai.usage.output_tokens, gen_ai.agent.name, gen_ai.tool.name.
# Add tokenprofiler.prompt.name and tokenprofiler.prompt.version to attribute a prompt.`;
}

export function curlSnippet({ apiUrl, key }: SnippetInput): string {
  const now = new Date().toISOString();
  return `curl -X POST ${apiUrl}/v1/ingest \\
  -H "Authorization: Bearer ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "traces": [{"id": "trace-1", "name": "support.chat", "user_id": "usr_42"}],
    "spans": [{
      "id": "span-1", "trace_id": "trace-1", "name": "draft-reply", "kind": "generation",
      "start_time": "${now}", "model": "gpt-4o",
      "usage": {"input": 812, "output": 96},
      "input": "Where is my order?", "output": "It ships tomorrow."
    }]
  }'`;
}
