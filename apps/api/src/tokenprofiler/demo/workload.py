"""A synthetic but realistic LLM workload for the demo: five agents, seven tools, a dozen
models and prompt versions that change over two weeks, with an incident, a cost spike and
slow outliers. Everything flows through the real ingest service, so prices, attribution,
redaction and totals are computed by the product, not faked here.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from tokenprofiler.ingest.types import Batch, SpanIn, TraceIn

# (tokens per second while decoding, time to first token in ms)
SPEEDS: dict[str, tuple[float, int]] = {
    "gpt-4o": (80, 480),
    "gpt-4o-mini": (125, 260),
    "gpt-4.1": (90, 420),
    "gpt-4.1-mini": (130, 280),
    "gpt-5": (70, 900),
    "claude-sonnet-4-5": (70, 620),
    "claude-haiku-4-5": (140, 300),
    "claude-opus-4-1": (40, 1100),
    "gemini-2.5-flash": (160, 340),
    "deepseek-chat": (60, 700),
    "text-embedding-3-small": (0, 60),
    "internal-llama-3.3-70b": (45, 520),
}
PROVIDERS = {
    "gpt": "openai",
    "text-embedding": "openai",
    "claude": "anthropic",
    "gemini": "google",
    "deepseek": "deepseek",
    "internal": "local",
}

USERS = [f"usr_{1000 + i}" for i in range(140)]
SUPPORT_QUESTIONS = [
    "Where is my order #{n}? It was supposed to arrive on Tuesday.",
    "I would like a refund for my annual plan. My email is {email}.",
    "Can you change the shipping address on order #{n}? Call me on {phone}.",
    "Why was I charged twice this month for the Pro plan?",
    "How do I reset two factor authentication on my account?",
    "Employee {emp} asked to move our team to the enterprise tier. What does it cost?",
    "The export button on the reports page does nothing, is this a known bug?",
    "Do you offer a student discount? I can verify with {email}.",
    "My invoice shows the wrong VAT number, please fix it before Friday.",
    "Cancel my subscription but keep the data for 90 days.",
]
RESEARCH_TOPICS = [
    "Compare managed vector databases for a 50M document corpus",
    "Summarise EU AI Act obligations for general purpose model providers",
    "What changed in Postgres 17 logical replication and does it affect us",
    "Market scan of open source LLM gateways and their pricing models",
    "Evaluate speculative decoding gains for 70B models on a single GPU",
    "Competitor review: how do three rival products price seats vs usage",
]
ANALYTICS_QUESTIONS = [
    "What was weekly revenue by plan for the last quarter?",
    "Which accounts churned in October and what was their average tenure?",
    "Top 20 customers by token spend this month",
    "Conversion rate from trial to paid by acquisition channel",
    "How many support tickets mention refunds per week?",
]
REPOS = ["billing-service", "web-app", "ingest-worker", "auth-gateway"]
ERRORS = {
    "timeout": "openai.APITimeoutError: Request timed out after 30s",
    "rate": "anthropic.RateLimitError: 429 rate_limit_error, retry after 8s",
    "sql": 'psycopg.errors.SyntaxError: syntax error at or near "GROUP"',
    "fetch": "httpx.ReadTimeout: reading https://example.org/report took more than 20s",
    "tool": "ToolExecutionError: lookup_order returned 502 from the orders service",
}


@dataclass(slots=True)
class Plan:
    """What changes over the two weeks: prompt rollouts, an incident and a cost spike."""

    start: datetime
    now: datetime

    def day(self, at: datetime) -> int:
        return int((at - self.start).total_seconds() // 86400)

    def triage_version(self, at: datetime, rng: random.Random) -> int:
        day = self.day(at)
        if day < 5:
            return 1
        if day < 10:
            return 2 if rng.random() < 0.9 else 1
        return 3 if rng.random() < 0.85 else 2

    def answer_version(self, at: datetime, rng: random.Random) -> int:
        return 1 if self.day(at) < 8 or rng.random() < 0.15 else 2

    def sql_version(self, at: datetime, rng: random.Random) -> int:
        day = self.day(at)
        return 1 if day < 4 else (2 if day < 9 else (3 if rng.random() < 0.8 else 2))

    def incident(self, at: datetime) -> bool:
        """Four days ago, 13:00 to 15:30 UTC: gpt-4o timeouts."""
        base = (self.now - timedelta(days=4)).replace(hour=13, minute=0, second=0, microsecond=0)
        return base <= at < base + timedelta(hours=2, minutes=30)

    def spike(self, at: datetime) -> bool:
        """Nine days ago a research loop ran away for an afternoon."""
        base = (self.now - timedelta(days=9)).replace(hour=14, minute=0, second=0, microsecond=0)
        return base <= at < base + timedelta(hours=3)


@dataclass(slots=True)
class Builder:
    rng: random.Random
    plan: Plan
    spans: list[SpanIn] = field(default_factory=list)
    trace_id: str = ""
    cursor: datetime = field(default_factory=datetime.now)
    errored: bool = False

    def new_id(self, bits: int) -> str:
        return f"{self.rng.getrandbits(bits):0{bits // 4}x}"

    def jitter(self, value: float, spread: float = 0.35) -> float:
        return max(1.0, value * math.exp(self.rng.gauss(0, spread)))

    def span(
        self,
        name: str,
        kind: str,
        parent: SpanIn | None,
        duration_ms: float,
        **fields: object,
    ) -> SpanIn:
        start = self.cursor
        end = start + timedelta(milliseconds=duration_ms)
        span = SpanIn(
            trace_id=self.trace_id,
            span_id=self.new_id(64),
            parent_id=parent.span_id if parent else None,
            name=name,
            kind=kind,
            started_at=start,
            ended_at=end,
            **fields,  # type: ignore[arg-type]
        )
        self.spans.append(span)
        return span

    def generation(
        self,
        parent: SpanIn,
        name: str,
        model: str,
        *,
        prompt: tuple[str, int] | None,
        tokens_in: float,
        tokens_out: float,
        cached_share: float = 0.0,
        prompt_text: str = "",
        answer_text: str = "",
        error: str | None = None,
    ) -> SpanIn:
        speed, ttft = SPEEDS[model]
        tin = int(self.jitter(tokens_in, 0.25))
        tout = 0 if speed == 0 else int(self.jitter(tokens_out, 0.35))
        first = self.jitter(ttft, 0.3)
        decode = tout / speed * 1000 if speed else 0
        if error:
            first, tout, decode = self.jitter(30_000 if "timed out" in error else 900, 0.1), 0, 0
        provider = next((v for k, v in PROVIDERS.items() if model.startswith(k)), "other")
        span = self.span(
            name,
            "embedding" if model.startswith("text-embedding") else "generation",
            parent,
            first + decode,
            model=model,
            provider=provider,
            input_tokens=tin,
            output_tokens=tout,
            cached_tokens=int(tin * cached_share),
            time_to_first_token_ms=None if error else int(first),
            prompt_name=prompt[0] if prompt else None,
            prompt_version=prompt[1] if prompt else None,
            model_parameters={"temperature": 0.2, "max_tokens": 1024} if speed else {},
            input=prompt_text or None,
            output=None if error else (answer_text or None),
            status="error" if error else "ok",
            status_message=error,
        )
        self.cursor = span.ended_at + timedelta(milliseconds=self.rng.uniform(2, 25))
        if error:
            self.errored = True
        return span

    def tool(
        self,
        parent: SpanIn,
        name: str,
        duration_ms: float,
        *,
        arguments: object = None,
        result: object = None,
        error: str | None = None,
    ) -> SpanIn:
        span = self.span(
            name,
            "tool",
            parent,
            duration_ms,
            input=arguments,
            output=None if error else result,
            status="error" if error else "ok",
            status_message=error,
        )
        self.cursor = span.ended_at + timedelta(milliseconds=self.rng.uniform(1, 12))
        if error:
            self.errored = True
        return span

    def close(self, span: SpanIn, *, error: str | None = None) -> None:
        span.ended_at = max(self.cursor, span.ended_at)
        if error:
            span.status, span.status_message = "error", error


def _fill(rng: random.Random, template: str) -> str:
    return template.format(
        n=rng.randint(100000, 999999),
        email=f"{rng.choice(['sam', 'priya', 'li', 'jordan'])}.{rng.randint(10, 99)}@example.com",
        phone=f"+1 {rng.randint(200, 989)}-{rng.randint(200, 989)}-{rng.randint(1000, 9999)}",
        emp=f"EMP-{rng.randint(100000, 999999)}",
    )


def support_flow(b: Builder, at: datetime) -> str:
    rng, plan = b.rng, b.plan
    question = _fill(rng, rng.choice(SUPPORT_QUESTIONS))
    root = b.span("support-agent", "agent", None, 1, input=question, agent_name="support-agent")
    triage = plan.triage_version(at, rng)
    scale = {1: 1.0, 2: 0.82, 3: 0.55}[triage]
    b.generation(
        root,
        "classify-intent",
        "gpt-4o-mini",
        prompt=("support-triage", triage),
        tokens_in=950 * scale,
        tokens_out=28,
        cached_share=0.45,
        prompt_text=question,
        answer_text='{"intent": "billing", "urgency": "normal"}',
    )
    embed = b.tool(root, "vector_search", 1, arguments={"query": question[:60], "top_k": 5})
    b.cursor = embed.started_at
    b.generation(
        embed,
        "embed-query",
        "text-embedding-3-small",
        prompt=None,
        tokens_in=22,
        tokens_out=0,
        prompt_text=question[:80],
    )
    b.cursor += timedelta(milliseconds=b.jitter(70, 0.3))
    b.close(embed)
    b.cursor = embed.ended_at + timedelta(milliseconds=3)
    if rng.random() < 0.45:
        failed = rng.random() < 0.03
        b.tool(
            root,
            "lookup_order",
            b.jitter(140, 0.5),
            arguments={"order_id": rng.randint(100000, 999999)},
            result={"status": "shipped", "carrier": "DHL"},
            error=ERRORS["tool"] if failed else None,
        )
    answer_model = "gpt-4o" if rng.random() < 0.55 else "claude-sonnet-4-5"
    error = None
    if plan.incident(at) and answer_model == "gpt-4o" and rng.random() < 0.7:
        error = ERRORS["timeout"]
    elif rng.random() < 0.012:
        error = ERRORS["rate"] if answer_model == "claude-sonnet-4-5" else ERRORS["timeout"]
    b.generation(
        root,
        "draft-reply",
        answer_model,
        prompt=("refund-policy-answer", plan.answer_version(at, rng)),
        tokens_in=2100,
        tokens_out=260,
        cached_share=0.5,
        prompt_text=question,
        answer_text="Thanks for reaching out. I checked your account and here is what I can do...",
        error=error,
    )
    b.close(root, error=error)
    root.output = None if error else "Thanks for reaching out. Here is what I found for your order."
    return "support.chat"


def research_flow(b: Builder, at: datetime) -> str:
    rng, plan = b.rng, b.plan
    topic = rng.choice(RESEARCH_TOPICS)
    root = b.span("research-agent", "agent", None, 1, input=topic, agent_name="research-agent")
    b.generation(
        root,
        "plan-research",
        "claude-sonnet-4-5",
        prompt=("research-planner", 1 if plan.day(at) < 7 else 2),
        tokens_in=1500,
        tokens_out=420,
        cached_share=0.3,
        prompt_text=topic,
        answer_text="1. Define criteria 2. Search vendor docs 3. Compare pricing 4. Synthesise",
    )
    loops = rng.randint(2, 4) + (rng.randint(8, 12) if plan.spike(at) else 0)
    for _ in range(loops):
        search = b.tool(root, "web_search", 1, arguments={"q": topic[:50], "n": 8})
        b.cursor = search.started_at + timedelta(milliseconds=b.jitter(900, 0.4))
        b.generation(
            search,
            "summarise-results",
            "gpt-4o-mini",
            prompt=("kb-summarizer", 1 if plan.day(at) < 6 else 2),
            tokens_in=3800,
            tokens_out=330,
            prompt_text="Results: ...",
            answer_text="Key findings: vendor A is cheapest at scale, vendor B has better recall.",
        )
        b.close(search)
        b.cursor = search.ended_at + timedelta(milliseconds=4)
        if rng.random() < 0.6:
            slow = rng.random() < 0.025
            b.tool(
                root,
                "fetch_url",
                b.jitter(25_000 if slow else 1_400, 0.3),
                arguments={"url": "https://example.org/pricing"},
                result={"status": 200, "bytes": 48213},
                error=ERRORS["fetch"] if slow and rng.random() < 0.6 else None,
            )
    final_model = "gpt-5" if rng.random() < 0.25 else "claude-sonnet-4-5"
    b.generation(
        root,
        "synthesise-report",
        final_model,
        prompt=None,
        tokens_in=9500 + 1800 * loops,
        tokens_out=1700,
        prompt_text="Synthesise the findings above into a report.",
        answer_text="# Report\n\n## Summary\n...",
    )
    b.close(root)
    return "research.report"


def analytics_flow(b: Builder, at: datetime) -> str:
    rng, plan = b.rng, b.plan
    question = rng.choice(ANALYTICS_QUESTIONS)
    root = b.span("sql-analyst", "agent", None, 1, input=question, agent_name="sql-analyst")
    version = plan.sql_version(at, rng)
    attempts = 1 + (1 if rng.random() < 0.12 else 0)
    failure_rate = {1: 0.05, 2: 0.04, 3: 0.12}[version]
    failed_hard = False
    for attempt in range(attempts):
        b.generation(
            root,
            "write-sql",
            "gpt-4.1",
            prompt=("sql-generator", version),
            tokens_in=2400,
            tokens_out=190,
            cached_share=0.6,
            prompt_text=question,
            answer_text="SELECT plan, date_trunc('week', created_at) AS week, sum(amount) FROM ...",
        )
        failed = rng.random() < failure_rate
        b.tool(
            root,
            "run_sql",
            b.jitter(420, 0.7),
            arguments={"sql": "SELECT ..."},
            result={"rows": rng.randint(3, 400)},
            error=ERRORS["sql"] if failed else None,
        )
        failed_hard = failed and attempt == attempts - 1
    if not failed_hard:
        b.generation(
            root,
            "explain-result",
            "gpt-4.1-mini",
            prompt=None,
            tokens_in=1100,
            tokens_out=240,
            prompt_text="Explain these rows to a finance lead.",
            answer_text="Revenue grew 6% week over week, driven by the Team plan.",
        )
    b.close(root, error=ERRORS["sql"] if failed_hard else None)
    return "analytics.question"


def review_flow(b: Builder, at: datetime) -> str:
    rng = b.rng
    repo = rng.choice(REPOS)
    root = b.span(
        "code-review-agent",
        "agent",
        None,
        1,
        input=f"Review PR in {repo}",
        agent_name="code-review-agent",
    )
    b.tool(
        root,
        "github_diff",
        b.jitter(650, 0.4),
        arguments={"repo": repo, "pr": rng.randint(100, 900)},
        result={"files": rng.randint(2, 9)},
    )
    for _ in range(rng.randint(2, 6)):
        b.generation(
            root,
            "review-file",
            "deepseek-chat" if rng.random() < 0.6 else "claude-haiku-4-5",
            prompt=("code-review-summary", 1),
            tokens_in=4200,
            tokens_out=380,
            prompt_text="diff --git a/service.py b/service.py ...",
            answer_text="Possible N+1 query in the loop on line 88; add a prefetch.",
        )
    b.generation(
        root,
        "summarise-review",
        "claude-sonnet-4-5",
        prompt=("code-review-summary", 1),
        tokens_in=3100,
        tokens_out=520,
        prompt_text="Combine the file reviews.",
        answer_text="Overall: approve with two requested changes.",
    )
    b.close(root)
    return "review.pull_request"


def summarize_flow(b: Builder, at: datetime) -> str:
    """A plain pipeline with no agent: a nightly-style document summariser."""
    rng = b.rng
    root = b.span("summarize-document", "span", None, 1, input="Quarterly operations memo")
    b.generation(
        root,
        "summarise",
        "gemini-2.5-flash",
        prompt=("kb-summarizer", 2 if b.plan.day(at) >= 6 else 1),
        tokens_in=6200,
        tokens_out=410,
        prompt_text="Summarise the following document in five bullets.",
        answer_text="- Revenue up 6%\n- Churn flat\n- Two incidents closed",
    )
    if rng.random() < 0.5:
        b.generation(
            root,
            "title",
            "gpt-4o-mini",
            prompt=None,
            tokens_in=520,
            tokens_out=14,
            prompt_text="Write a short title.",
            answer_text="Q3 operations review",
        )
    b.close(root)
    return "batch.summarize"


FLOWS = {
    "support": (support_flow, 0.50),
    "research": (research_flow, 0.09),
    "analytics": (analytics_flow, 0.17),
    "review": (review_flow, 0.10),
    "summarize": (summarize_flow, 0.14),
}
HOURLY = [
    0.2,
    0.15,
    0.12,
    0.12,
    0.15,
    0.3,
    0.55,
    0.85,
    1.1,
    1.3,
    1.4,
    1.35,
    1.2,
    1.3,
    1.4,
    1.35,
    1.2,
    1.0,
    0.8,
    0.6,
    0.5,
    0.4,
    0.3,
    0.25,
]


def generate(
    *, seed: int, now: datetime, days: int, per_weekday: int, flows: dict[str, float]
) -> list[Batch]:
    """Batches of about sixty traces each, in time order."""
    rng = random.Random(seed)
    start = (now - timedelta(days=days)).replace(minute=0, second=0, microsecond=0)
    plan = Plan(start=start, now=now)
    names = list(flows)
    weights = [flows[n] for n in names]
    batches: list[Batch] = []
    current = Batch()
    cursor = start
    sessions: dict[str, str] = {}
    while cursor < now:
        weekday = cursor.weekday() < 5
        rate = per_weekday * (1.0 if weekday else 0.55) * HOURLY[cursor.hour] / sum(HOURLY)
        for _ in range(int(rng.gauss(rate, math.sqrt(rate) * 0.6 + 0.01) + 0.5)):
            at = cursor + timedelta(seconds=rng.uniform(0, 3600))
            if at >= now - timedelta(seconds=30):
                continue
            builder = Builder(rng=rng, plan=plan, cursor=at)
            builder.trace_id = builder.new_id(128)
            flow = FLOWS[rng.choices(names, weights)[0]][0]
            name = flow(builder, at)
            user = rng.choice(USERS) if name != "batch.summarize" else None
            session = None
            if user and name in {"support.chat", "analytics.question"}:
                session = sessions.setdefault(user, f"sess_{rng.getrandbits(32):08x}")
                if rng.random() < 0.3:
                    sessions.pop(user, None)
            current.traces.append(
                TraceIn(
                    trace_id=builder.trace_id,
                    name=name,
                    user_id=user,
                    session_id=session,
                    environment="production" if rng.random() < 0.9 else "staging",
                    release=f"2026.11.{1 + plan.day(at) // 4}",
                    tags=[name.split(".")[0]] + (["beta"] if rng.random() < 0.08 else []),
                    timestamp=at,
                )
            )
            current.spans.extend(builder.spans)
            if len(current.traces) >= 60:
                batches.append(current)
                current = Batch()
        cursor += timedelta(hours=1)
    if current.traces:
        batches.append(current)
    return batches
