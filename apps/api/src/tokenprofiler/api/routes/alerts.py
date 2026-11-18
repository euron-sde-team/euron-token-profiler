"""Budgets, alert rules and the events they raise."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from tokenprofiler.api.deps import ContainerDep, ProjectDep, SessionDep, WriterDep
from tokenprofiler.repositories.alerting import AlertRepository
from tokenprofiler.schemas.alerting import (
    AlertEventOut,
    AlertsOverview,
    BudgetOut,
    BudgetWrite,
    RuleOut,
    RuleWrite,
)
from tokenprofiler.schemas.common import Page
from tokenprofiler.services.alerts import AlertService

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["budgets and alerts"])


@router.get("/alerts", summary="Budgets with spend, rules, and how many alerts are firing")
async def overview(
    project: ProjectDep, container: ContainerDep, session: SessionDep
) -> AlertsOverview:
    return await AlertService(container, session).overview(project.id)


@router.get("/alert-events", summary="Alert history, newest first")
async def events(
    project: ProjectDep,
    session: SessionDep,
    firing_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AlertEventOut]:
    rows, total = await AlertRepository(session).events(
        project.id, limit=limit, offset=offset, firing_only=firing_only
    )
    return Page[AlertEventOut](
        items=[AlertEventOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/budgets", summary="Create a budget", status_code=status.HTTP_201_CREATED)
async def create_budget(
    body: BudgetWrite,
    project: ProjectDep,
    principal: WriterDep,
    container: ContainerDep,
    session: SessionDep,
) -> BudgetOut:
    return await AlertService(container, session).save_budget(principal, project.id, body)


@router.put("/budgets/{budget_id}", summary="Replace a budget")
async def update_budget(
    budget_id: uuid.UUID,
    body: BudgetWrite,
    project: ProjectDep,
    principal: WriterDep,
    container: ContainerDep,
    session: SessionDep,
) -> BudgetOut:
    return await AlertService(container, session).save_budget(
        principal, project.id, body, budget_id
    )


@router.delete(
    "/budgets/{budget_id}", summary="Delete a budget", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_budget(
    budget_id: uuid.UUID,
    project: ProjectDep,
    principal: WriterDep,
    container: ContainerDep,
    session: SessionDep,
) -> Response:
    await AlertService(container, session).delete_budget(principal, project.id, budget_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/alert-rules", summary="Create an alert rule", status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleWrite,
    project: ProjectDep,
    principal: WriterDep,
    container: ContainerDep,
    session: SessionDep,
) -> RuleOut:
    rule = await AlertService(container, session).save_rule(principal, project.id, body)
    return RuleOut.model_validate(rule)


@router.put("/alert-rules/{rule_id}", summary="Replace an alert rule")
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleWrite,
    project: ProjectDep,
    principal: WriterDep,
    container: ContainerDep,
    session: SessionDep,
) -> RuleOut:
    rule = await AlertService(container, session).save_rule(principal, project.id, body, rule_id)
    return RuleOut.model_validate(rule)


@router.delete(
    "/alert-rules/{rule_id}",
    summary="Delete an alert rule",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_rule(
    rule_id: uuid.UUID,
    project: ProjectDep,
    principal: WriterDep,
    container: ContainerDep,
    session: SessionDep,
) -> Response:
    await AlertService(container, session).delete_rule(principal, project.id, rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
