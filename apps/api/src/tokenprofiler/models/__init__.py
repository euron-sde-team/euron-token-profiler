"""Every model, imported here so `Base.metadata` is complete for Alembic and the tests."""

from tokenprofiler.models.alerting import AlertEvent, AlertRule, Budget
from tokenprofiler.models.api_key import ApiKey
from tokenprofiler.models.audit import AuditEvent
from tokenprofiler.models.price import ModelPrice
from tokenprofiler.models.project import Project
from tokenprofiler.models.prompt import PromptVersion
from tokenprofiler.models.trace import Span, Trace
from tokenprofiler.models.user import User

__all__ = [
    "AlertEvent",
    "AlertRule",
    "ApiKey",
    "AuditEvent",
    "Budget",
    "ModelPrice",
    "Project",
    "PromptVersion",
    "Span",
    "Trace",
    "User",
]
