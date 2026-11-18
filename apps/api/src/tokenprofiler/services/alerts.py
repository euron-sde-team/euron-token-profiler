"""Budgets and alert rules: management, evaluation and webhook notification.

Evaluation is a pull model: the worker re-reads spend and trace health every
`alert_interval_s` seconds under a Valkey lock (one worker evaluates at a time) and opens,
escalates or resolves one event per budget or rule. At most one event per source is open at
a time, enforced by a partial unique index, so a restart or a second worker cannot
double-fire.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from tokenprofiler.core import metrics
from tokenprofiler.core.errors import NotFoundError, UnprocessableError
from tokenprofiler.core.logging import get_logger
from tokenprofiler.models import AlertEvent, AlertRule, Budget, Project
from tokenprofiler.repositories.alerting import AlertRepository
from tokenprofiler.repositories.metrics import MetricsRepository
from tokenprofiler.schemas.alerting import (
    AlertsOverview,
    BudgetOut,
    BudgetWrite,
    RuleOut,
    RuleWrite,
)
from tokenprofiler.services import audit
from tokenprofiler.services.container import Container
from tokenprofiler.services.principal import Principal
from tokenprofiler.services.webhooks import deliver

log = get_logger("tokenprofiler.alerts")
MAX_PER_PROJECT = 50


def period_bounds(period: str, now: datetime) -> tuple[datetime, datetime]:
    """The UTC calendar day, ISO week (Monday start) or month containing `now`."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "day":
        return midnight, midnight + timedelta(days=1)
    if period == "week":
        start = midnight - timedelta(days=midnight.weekday())
        return start, start + timedelta(days=7)
    start = midnight.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end


def budget_state(spent: Decimal, limit: Decimal, warn_percent: int) -> str:
    if spent >= limit:
        return "exceeded"
    if spent * 100 >= limit * warn_percent:
        return "warning"
    return "ok"


def rule_firing(metric: str, comparator: str, value: float, threshold: float) -> bool:
    return value > threshold if comparator == "above" else value < threshold


class AlertService:
    def __init__(self, container: Container, session: AsyncSession) -> None:
        self.c = container
        self.session = session
        self.alerts = AlertRepository(session)
        self.metrics = MetricsRepository(session)

    # --- management -------------------------------------------------------------------

    async def _budget_out(self, budget: Budget, now: datetime) -> BudgetOut:
        start, end = period_bounds(budget.period, now)
        spent = await self.metrics.spend(budget.project_id, budget.scope, budget.scope_value, start)
        return BudgetOut(
            id=budget.id,
            name=budget.name,
            scope=budget.scope,
            scope_value=budget.scope_value,
            period=budget.period,
            limit_usd=budget.limit_usd,
            warn_at_percent=budget.warn_at_percent,
            enabled=budget.enabled,
            spent_usd=spent,
            percent_used=round(float(spent / budget.limit_usd * 100), 1),
            period_start=start,
            period_end=end,
            state=budget_state(spent, budget.limit_usd, budget.warn_at_percent),
        )

    async def overview(self, project_id: uuid.UUID) -> AlertsOverview:
        now = datetime.now(UTC)
        budgets = await self.alerts.budgets(project_id)
        rules = await self.alerts.rules(project_id)
        events, _ = await self.alerts.events(project_id, limit=200, offset=0, firing_only=True)
        firing_sources = {event.source_id for event in events}
        return AlertsOverview(
            budgets=[await self._budget_out(b, now) for b in budgets],
            rules=[
                RuleOut(
                    id=r.id,
                    name=r.name,
                    metric=r.metric,
                    comparator=r.comparator,
                    threshold=r.threshold,
                    window_minutes=r.window_minutes,
                    min_traces=r.min_traces,
                    severity=r.severity,
                    enabled=r.enabled,
                    firing=r.id in firing_sources,
                )
                for r in rules
            ],
            firing=len(events),
        )

    async def save_budget(
        self,
        principal: Principal,
        project_id: uuid.UUID,
        body: BudgetWrite,
        budget_id: uuid.UUID | None = None,
    ) -> BudgetOut:
        if budget_id is None:
            if len(await self.alerts.budgets(project_id)) >= MAX_PER_PROJECT:
                raise UnprocessableError(f"At most {MAX_PER_PROJECT} budgets per project.")
            budget = Budget(project_id=project_id)
        else:
            found = await self.alerts.budget(project_id, budget_id)
            if found is None:
                raise NotFoundError("Budget not found.")
            budget = found
        budget.name = body.name
        budget.scope = body.scope
        budget.scope_value = body.scope_value
        budget.period = body.period
        budget.limit_usd = body.limit_usd
        budget.warn_at_percent = body.warn_at_percent
        budget.enabled = body.enabled
        await self.alerts.add(budget)
        await audit.record(
            self.session,
            principal=principal,
            project_id=project_id,
            action="budget.created" if budget_id is None else "budget.updated",
            target_type="budget",
            target_id=budget.id,
            details={"name": budget.name, "limit_usd": float(budget.limit_usd)},
        )
        await self.session.commit()
        await self.session.refresh(budget)
        return await self._budget_out(budget, datetime.now(UTC))

    async def delete_budget(
        self, principal: Principal, project_id: uuid.UUID, budget_id: uuid.UUID
    ) -> None:
        budget = await self.alerts.budget(project_id, budget_id)
        if budget is None:
            raise NotFoundError("Budget not found.")
        await self.alerts.delete_budget(budget)
        await audit.record(
            self.session,
            principal=principal,
            project_id=project_id,
            action="budget.deleted",
            target_type="budget",
            target_id=budget_id,
            details={"name": budget.name},
        )
        await self.session.commit()

    async def save_rule(
        self,
        principal: Principal,
        project_id: uuid.UUID,
        body: RuleWrite,
        rule_id: uuid.UUID | None = None,
    ) -> AlertRule:
        if rule_id is None:
            if len(await self.alerts.rules(project_id)) >= MAX_PER_PROJECT:
                raise UnprocessableError(f"At most {MAX_PER_PROJECT} rules per project.")
            rule = AlertRule(project_id=project_id)
        else:
            found = await self.alerts.rule(project_id, rule_id)
            if found is None:
                raise NotFoundError("Alert rule not found.")
            rule = found
        for field in (
            "name",
            "metric",
            "comparator",
            "threshold",
            "window_minutes",
            "min_traces",
            "severity",
            "enabled",
        ):
            setattr(rule, field, getattr(body, field))
        await self.alerts.add(rule)
        await audit.record(
            self.session,
            principal=principal,
            project_id=project_id,
            action="alert_rule.created" if rule_id is None else "alert_rule.updated",
            target_type="alert_rule",
            target_id=rule.id,
            details={"name": rule.name, "metric": rule.metric},
        )
        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def delete_rule(
        self, principal: Principal, project_id: uuid.UUID, rule_id: uuid.UUID
    ) -> None:
        rule = await self.alerts.rule(project_id, rule_id)
        if rule is None:
            raise NotFoundError("Alert rule not found.")
        await self.alerts.delete_rule(rule)
        await audit.record(
            self.session,
            principal=principal,
            project_id=project_id,
            action="alert_rule.deleted",
            target_type="alert_rule",
            target_id=rule_id,
            details={"name": rule.name},
        )
        await self.session.commit()

    # --- evaluation -------------------------------------------------------------------

    async def evaluate_project(self, project: Project, *, now: datetime | None = None) -> int:
        """Re-check every budget and rule of a project. Returns how many events changed."""
        now = now or datetime.now(UTC)
        changed = 0
        for budget in await self.alerts.budgets(project.id):
            start, _ = period_bounds(budget.period, now)
            spent = await self.metrics.spend(project.id, budget.scope, budget.scope_value, start)
            state = (
                budget_state(spent, budget.limit_usd, budget.warn_at_percent)
                if budget.enabled
                else "ok"
            )
            what = f"{budget.scope} {budget.scope_value}" if budget.scope_value else "project"
            message = (
                f"{budget.name}: ${spent:.2f} of ${budget.limit_usd:.2f} "
                f"{budget.period}ly budget used ({what})"
            )
            threshold = (
                budget.limit_usd
                if state == "exceeded"
                else budget.limit_usd * budget.warn_at_percent / 100
            )
            changed += await self._reconcile(
                project,
                kind="budget",
                source_id=budget.id,
                source_name=budget.name,
                severity="critical" if state == "exceeded" else "warning",
                firing=state != "ok",
                value=spent,
                threshold=threshold,
                message=message,
            )
        stats_cache: dict[int, tuple[int, int, float, Decimal]] = {}
        for rule in await self.alerts.rules(project.id):
            window = rule.window_minutes
            if window not in stats_cache:
                stats_cache[window] = await self.metrics.window_stats(
                    project.id, now - timedelta(minutes=window)
                )
            traces, errors, p95, cost = stats_cache[window]
            value = {
                "error_rate": 100 * errors / traces if traces else 0.0,
                "p95_latency_ms": p95,
                "cost_usd": float(cost),
                "trace_count": float(traces),
            }[rule.metric]
            enough = rule.metric == "trace_count" or traces >= rule.min_traces
            firing = (
                rule.enabled
                and enough
                and rule_firing(rule.metric, rule.comparator, value, float(rule.threshold))
            )
            changed += await self._reconcile(
                project,
                kind="rule",
                source_id=rule.id,
                source_name=rule.name,
                severity=rule.severity,
                firing=firing,
                value=Decimal(str(round(value, 4))),
                threshold=rule.threshold,
                message=(
                    f"{rule.name}: {rule.metric} is {value:.2f}, {rule.comparator} "
                    f"{rule.threshold} over {rule.window_minutes} minutes"
                ),
            )
        await self.session.commit()
        return changed

    async def _reconcile(
        self,
        project: Project,
        *,
        kind: str,
        source_id: uuid.UUID,
        source_name: str,
        severity: str,
        firing: bool,
        value: Decimal,
        threshold: Decimal,
        message: str,
    ) -> int:
        open_event = await self.alerts.open_event(source_id)
        now = datetime.now(UTC)
        if firing and open_event is None:
            event = AlertEvent(
                project_id=project.id,
                kind=kind,
                source_id=source_id,
                source_name=source_name,
                severity=severity,
                state="firing",
                value=value,
                threshold=threshold,
                message=message,
                fired_at=now,
            )
            await self.alerts.add(event)
            metrics.ALERTS_FIRED.labels(kind).inc()
            await self._notify(project, event, "alert.firing")
            return 1
        if firing and open_event is not None:
            escalated = severity != open_event.severity
            open_event.severity = severity
            open_event.value = value
            open_event.threshold = threshold
            open_event.message = message
            if escalated:
                await self._notify(project, open_event, "alert.escalated")
            return int(escalated)
        if not firing and open_event is not None:
            open_event.state = "resolved"
            open_event.resolved_at = now
            await self._notify(project, open_event, "alert.resolved")
            return 1
        return 0

    async def _notify(self, project: Project, event: AlertEvent, name: str) -> None:
        sealed = project.webhook_url_sealed
        if sealed is None:
            return
        url = self.c.secretbox.open(sealed, context=f"project:{project.id}:webhook")
        payload: dict[str, Any] = {
            "event": name,
            "project": {"id": str(project.id), "name": project.name, "slug": project.slug},
            "alert": {
                "id": str(event.id),
                "kind": event.kind,
                "name": event.source_name,
                "severity": event.severity,
                "state": event.state,
                "value": float(event.value),
                "threshold": float(event.threshold),
                "message": event.message,
                "fired_at": event.fired_at.isoformat() if event.fired_at else None,
            },
            "url": f"{self.c.settings.web_url.rstrip('/')}/budgets",
        }
        error = await deliver(self.c.http, self.c.settings, url, payload)
        event.notified_at = datetime.now(UTC) if error is None else None
        event.notify_error = error


async def evaluate_all(container: Container) -> int:
    """One evaluation pass over every project with a budget or a rule."""
    changed = 0
    async with container.db.session() as session:
        projects = await AlertRepository(session).projects_with_alerting()
    for project in projects:
        try:
            async with container.db.session() as session:
                changed += await AlertService(container, session).evaluate_project(project)
        except Exception:
            log.exception("alert_evaluation_failed", project=project.slug)
    return changed
