"""`tokenprofiler demo seed`: people, two projects, prompts, prices, budgets, alert rules and
two weeks of traces, all written through the same services the product uses."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text

from tokenprofiler.core.config import Settings
from tokenprofiler.core.errors import UnprocessableError
from tokenprofiler.demo.workload import generate
from tokenprofiler.models import AlertEvent, Project
from tokenprofiler.models.enums import Role
from tokenprofiler.repositories.alerting import AlertRepository
from tokenprofiler.repositories.projects import ProjectRepository
from tokenprofiler.repositories.users import UserRepository
from tokenprofiler.schemas.alerting import BudgetWrite, RuleWrite
from tokenprofiler.schemas.prices import PriceWrite
from tokenprofiler.schemas.projects import ProjectUpdate
from tokenprofiler.schemas.prompts import LabelMove, PromptVersionCreate
from tokenprofiler.schemas.redaction import CustomRule, RedactionRules
from tokenprofiler.services.alerts import AlertService
from tokenprofiler.services.container import Container, build_container
from tokenprofiler.services.ingest import IngestService
from tokenprofiler.services.keys import ApiKeyService
from tokenprofiler.services.prices import PriceService, sync_builtin_prices
from tokenprofiler.services.principal import Principal
from tokenprofiler.services.projects import ProjectService
from tokenprofiler.services.prompts import PromptService
from tokenprofiler.services.users import UserService

PEOPLE = [
    ("admin@example.com", "Ada Admin", Role.ADMIN),
    ("maya@example.com", "Maya Chen", Role.MEMBER),
    ("viewer@example.com", "Victor Reyes", Role.VIEWER),
]

PROMPTS: dict[str, list[tuple[str, str]]] = {
    "support-triage": [
        (
            "Classify the customer message into intent and urgency. Return JSON.\n\n"
            "Intents: billing, shipping, account, bug, sales, other.\nMessage: {{message}}",
            "First version",
        ),
        (
            "You triage support messages. Return JSON with intent and urgency only.\n"
            "Intents: billing, shipping, account, bug, sales, other.\nMessage: {{message}}",
            "Shorter instructions",
        ),
        ("Triage: {{message}}\nJSON {intent, urgency}", "Minimal prompt, 45 percent fewer tokens"),
    ],
    "refund-policy-answer": [
        (
            "You are a support agent for Acme. Use the policy excerpts to answer.\n"
            "Policy: {{policy}}\nOrder: {{order}}\nCustomer: {{message}}",
            "First version",
        ),
        (
            "You are a friendly support agent for Acme. Answer using only the policy excerpts and "
            "say when you are unsure.\nPolicy: {{policy}}\nOrder: {{order}}\nCustomer: {{message}}",
            "Add an uncertainty rule",
        ),
    ],
    "research-planner": [
        ("Plan the research steps for: {{topic}}. List at most five steps.", "First version"),
        (
            "Plan research for: {{topic}}. Prefer primary sources. At most five steps, each with "
            "the tool to use.",
            "Name the tool per step",
        ),
    ],
    "sql-generator": [
        ("Write a PostgreSQL query for: {{question}}\nSchema: {{schema}}", "First version"),
        (
            "Write a read only PostgreSQL query for: {{question}}\nSchema: {{schema}}\n"
            "Never use SELECT *.",
            "Read only, explicit columns",
        ),
        (
            "Write one PostgreSQL query for: {{question}}\nSchema: {{schema}}\nUse CTEs for "
            "readability.",
            "Prefer CTEs",
        ),
    ],
    "code-review-summary": [
        ("Review this diff for bugs and risky changes. Be specific.\n{{diff}}", "First version"),
    ],
    "kb-summarizer": [
        ("Summarise the document in five bullets.\n{{document}}", "First version"),
        (
            "Summarise the document in five bullets, keep numbers exact.\n{{document}}",
            "Keep numbers exact",
        ),
    ],
}
LABELS = {
    "support-triage": {3: ["production"], 2: ["staging"]},
    "refund-policy-answer": {2: ["production"]},
    "research-planner": {2: ["production"]},
    "sql-generator": {2: ["production"], 3: ["staging"]},
    "code-review-summary": {1: ["production"]},
    "kb-summarizer": {2: ["production"]},
}


async def _already_seeded(container: Container) -> bool:
    async with container.db.session() as session:
        return await UserRepository(session).by_email(PEOPLE[0][0]) is not None


async def seed(settings: Settings, *, force: bool = False) -> str:
    if settings.is_production:
        raise UnprocessableError(
            "The demo seed creates well-known accounts; never run it in production."
        )
    password = settings.demo_password.get_secret_value() if settings.demo_password else None
    if not password:
        raise UnprocessableError("Set DEMO_PASSWORD (make env writes TP_DEMO_PASSWORD).")
    container = await build_container(settings)
    try:
        await sync_builtin_prices(container)
        if await _already_seeded(container) and not force:
            return "demo data already present (use --force to add another batch of traces)"
        return await _seed(container, password)
    finally:
        await container.close()


async def _seed(container: Container, password: str) -> str:
    now = datetime.now(UTC)
    admin = None
    async with container.db.session() as session:
        users = UserRepository(session)
        for email, name, role in PEOPLE:
            if await users.by_email(email) is None:
                user, _ = await UserService(container, session).create(
                    Principal(), email=email, name=name, role=role.value, password=password
                )
                admin = admin or (user if role == Role.ADMIN else None)
        if admin is None:
            admin = await users.by_email(PEOPLE[0][0])
    if admin is None:
        raise UnprocessableError("The demo administrator could not be created.")
    principal = Principal(user=admin)

    projects: dict[str, Project] = {}
    async with container.db.session() as session:
        service = ProjectService(container, session)
        for name, description in (
            ("Customer Copilot", "Support, research and analytics agents serving customers."),
            ("Internal Tools", "Engineering assistants: code review and document summaries."),
        ):
            existing = await ProjectRepository(session).by_slug(name.lower().replace(" ", "-"))
            projects[name] = existing or await service.create(
                principal, name=name, description=description
            )

    copilot = projects["Customer Copilot"]
    tools = projects["Internal Tools"]
    async with container.db.session() as session:
        await ProjectService(container, session).update(
            principal,
            copilot.id,
            ProjectUpdate(
                redaction=RedactionRules(
                    custom=[
                        CustomRule(
                            name="employee-id",
                            pattern=r"EMP-\d{6}",
                            replacement="[REDACTED:employee]",
                        )
                    ]
                ),
                retention_days=30,
                archive_before_delete=True,
            ),
        )
        await ProjectService(container, session).update(
            principal, tools.id, ProjectUpdate(sampling_rate=Decimal("1"), retention_days=14)
        )

    async with container.db.session() as session:
        prompts = PromptService(session)
        for project in (copilot, tools):
            for name, versions in PROMPTS.items():
                for template, message in versions:
                    await prompts.create_version(
                        principal,
                        project.id,
                        PromptVersionCreate(name=name, template=template, commit_message=message),
                    )
                for version, labels in LABELS[name].items():
                    for label in labels:
                        await prompts.move_label(
                            principal, project.id, name, LabelMove(label=label, version=version)
                        )
    async with container.db.session() as session:
        await PriceService(container, session).upsert_override(
            principal,
            tools.id,
            PriceWrite(
                model="claude-haiku-4-5",
                provider="anthropic",
                input_per_mtok=Decimal("0.8"),
                output_per_mtok=Decimal("4"),
                cached_input_per_mtok=Decimal("0.08"),
            ),
        )
    key_text = ""
    async with container.db.session() as session:
        _, key_text = await ApiKeyService(container, session).create(
            principal, copilot.id, name="production-sdk"
        )
        await ApiKeyService(container, session).create(principal, tools.id, name="ci-pipeline")

    total_traces = 0
    for project, seed_value, per_day, flows in (
        (
            copilot,
            11,
            210,
            {"support": 0.52, "research": 0.1, "analytics": 0.2, "review": 0.0, "summarize": 0.18},
        ),
        (tools, 29, 70, {"review": 0.55, "summarize": 0.45}),
    ):
        batches = generate(seed=seed_value, now=now, days=14, per_weekday=per_day, flows=flows)
        for batch in batches:
            async with container.db.session() as session:
                result = await IngestService(container, session).ingest(
                    project, batch, protocol="native"
                )
            total_traces += result.accepted_traces
        sys.stderr.write(f"seeded {project.name}: {len(batches)} batches\n")

    await _alerting(container, principal, copilot, now)
    async with container.db.session() as session:
        await session.execute(text("ANALYZE traces"))
        await session.execute(text("ANALYZE spans"))
        await session.commit()
    return (
        f"seeded {total_traces} traces in 2 projects\n"
        f"  sign in: admin@example.com, maya@example.com (member), viewer@example.com (viewer)\n"
        f"  password: the DEMO_PASSWORD of this stack\n"
        f"  Customer Copilot ingest key: {key_text}"
    )


async def _alerting(
    container: Container, principal: Principal, project: Project, now: datetime
) -> None:
    """Budgets sized against the real spend so the page shows ok, warning and exceeded."""
    async with container.db.session() as session:
        service = AlertService(container, session)
        metrics = service.metrics
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Month to date can be a single day: size the monthly limit from the last 30 days.
        month = await metrics.spend(project.id, "project", None, month_start)
        research_week = await metrics.spend(project.id, "agent", "research-agent", week_start)
        gpt4o_day = await metrics.spend(project.id, "model", "gpt-4o", day_start)
        support_week = await metrics.spend(project.id, "agent", "support-agent", week_start)
        month = max(month, Decimal("20"))
        await service.save_budget(
            principal,
            project.id,
            BudgetWrite(
                name="Monthly LLM spend",
                scope="project",
                period="month",
                limit_usd=(month * Decimal("1.2")).quantize(Decimal("0.01")) or Decimal("500"),
            ),
        )
        await service.save_budget(
            principal,
            project.id,
            BudgetWrite(
                name="Research agent, weekly",
                scope="agent",
                scope_value="research-agent",
                period="week",
                limit_usd=max(
                    Decimal("1"), (research_week * Decimal("0.8")).quantize(Decimal("0.01"))
                ),
            ),
        )
        await service.save_budget(
            principal,
            project.id,
            BudgetWrite(
                name="Support agent, weekly",
                scope="agent",
                scope_value="support-agent",
                period="week",
                limit_usd=max(
                    Decimal("1"), (support_week * Decimal("1.18")).quantize(Decimal("0.01"))
                ),
            ),
        )
        await service.save_budget(
            principal,
            project.id,
            BudgetWrite(
                name="GPT-4o daily cap",
                scope="model",
                scope_value="gpt-4o",
                period="day",
                limit_usd=max(Decimal("5"), (gpt4o_day * Decimal("3")).quantize(Decimal("0.01"))),
            ),
        )
        await service.save_rule(
            principal,
            project.id,
            RuleWrite(
                name="Error rate above 8 percent",
                metric="error_rate",
                threshold=Decimal(8),
                window_minutes=60,
                min_traces=20,
                severity="critical",
            ),
        )
        await service.save_rule(
            principal,
            project.id,
            RuleWrite(
                name="p95 latency above 25 seconds",
                metric="p95_latency_ms",
                threshold=Decimal(25000),
                window_minutes=120,
                min_traces=20,
            ),
        )
        await service.save_rule(
            principal,
            project.id,
            RuleWrite(
                name="No traces for 30 minutes",
                metric="trace_count",
                comparator="below",
                threshold=Decimal(1),
                window_minutes=30,
                min_traces=0,
                severity="critical",
            ),
        )
    # History: the incident four days ago fired the error rule and resolved after the
    # timeouts stopped.
    async with container.db.session() as session:
        alerts = AlertRepository(session)
        rules = await alerts.rules(project.id)
        error_rule = next(r for r in rules if r.metric == "error_rate")
        base = (now - timedelta(days=4)).replace(hour=13, minute=22, second=0, microsecond=0)
        await alerts.add(
            AlertEvent(
                project_id=project.id,
                kind="rule",
                source_id=error_rule.id,
                source_name=error_rule.name,
                severity="critical",
                state="resolved",
                value=Decimal("14.6"),
                threshold=Decimal(8),
                message=f"{error_rule.name}: error_rate is 14.60, above 8 over 60 minutes",
                fired_at=base,
                resolved_at=base + timedelta(hours=2, minutes=41),
            )
        )
        await session.commit()
    async with container.db.session() as session:
        await AlertService(container, session).evaluate_project(project, now=now)
