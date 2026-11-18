"""Initial schema: people, projects, keys, traces and spans, prompts, prices, budgets,
alerts and the audit trail.

Revision ID: 0001
Revises:
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = pg.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
JSONB_EMPTY = sa.text("'{}'::jsonb")
COST = sa.Numeric(18, 8)
PRICE = sa.Numeric(14, 6)


def _id() -> sa.Column[object]:
    return sa.Column("id", UUID, nullable=False)


def _created() -> sa.Column[object]:
    return sa.Column("created_at", TS, nullable=False, server_default=sa.func.now())


def _updated() -> sa.Column[object]:
    return sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now())


def _fk(column: str, table: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [f"{table}.id"], ondelete=ondelete)


def _check_in(column: str, values: Sequence[str], name: str) -> sa.CheckConstraint:
    allowed = ", ".join(f"'{v}'" for v in values)
    return sa.CheckConstraint(f"{column} IN ({allowed})", name=name)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    # Trigram indexes make the trace name search a index scan instead of a table scan.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "users",
        _id(),
        sa.Column("email", pg.CITEXT(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", TS),
        sa.Column("last_login_at", TS),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        _check_in("role", ("admin", "member", "viewer"), "role"),
    )

    op.create_table(
        "projects",
        _id(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(48), nullable=False),
        sa.Column("description", sa.String(300), nullable=False, server_default=""),
        sa.Column("sampling_rate", sa.Numeric(4, 3), nullable=False, server_default="1"),
        sa.Column("keep_errors", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("keep_slow_ms", sa.Integer()),
        sa.Column("redaction", pg.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("archive_before_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("webhook_url_sealed", sa.Text()),
        sa.Column("created_by", UUID),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        _fk("created_by", "users", "SET NULL"),
        sa.CheckConstraint("sampling_rate >= 0 AND sampling_rate <= 1", name="sampling_rate"),
        sa.CheckConstraint("retention_days BETWEEN 1 AND 3650", name="retention_days"),
    )

    op.create_table(
        "api_keys",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("created_by", UUID),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("secret_hash", sa.String(64), nullable=False),
        sa.Column("last_used_at", TS),
        sa.Column("revoked_at", TS),
        _created(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prefix"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("created_by", "users", "SET NULL"),
    )
    op.create_index("ix_api_keys_project_id", "api_keys", ["project_id"])

    op.create_table(
        "traces",
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False, server_default=""),
        sa.Column("user_id", sa.String(128)),
        sa.Column("session_id", sa.String(128)),
        sa.Column("environment", sa.String(48), nullable=False, server_default="default"),
        sa.Column("release", sa.String(64)),
        sa.Column("tags", pg.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("ended_at", TS, nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(8), nullable=False, server_default="ok"),
        sa.Column("input", sa.Text()),
        sa.Column("output", sa.Text()),
        sa.Column("metadata", pg.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        sa.Column("span_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_cost", COST, nullable=False, server_default="0"),
        sa.Column("models", pg.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("agents", pg.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("tools", pg.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("prompts", pg.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("project_id", "id"),
        _fk("project_id", "projects", "CASCADE"),
        _check_in("status", ("ok", "error"), "status"),
    )
    # The hot queries: the list (newest first), errors only, one user or session, sort by
    # cost or duration, array filters and the name search.
    op.create_index(
        "ix_traces_project_started", "traces", ["project_id", sa.text("started_at DESC")]
    )
    op.create_index(
        "ix_traces_project_errors",
        "traces",
        ["project_id", sa.text("started_at DESC")],
        postgresql_where=sa.text("status = 'error'"),
    )
    op.create_index("ix_traces_project_cost", "traces", ["project_id", sa.text("total_cost DESC")])
    op.create_index(
        "ix_traces_project_duration", "traces", ["project_id", sa.text("duration_ms DESC")]
    )
    op.create_index(
        "ix_traces_project_user",
        "traces",
        ["project_id", "user_id", sa.text("started_at DESC")],
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_traces_project_session",
        "traces",
        ["project_id", "session_id", sa.text("started_at DESC")],
        postgresql_where=sa.text("session_id IS NOT NULL"),
    )
    for column in ("tags", "models", "agents", "tools", "prompts"):
        op.create_index(f"ix_traces_{column}_gin", "traces", [column], postgresql_using="gin")
    op.create_index(
        "ix_traces_name_trgm",
        "traces",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )

    op.create_table(
        "spans",
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("parent_id", sa.String(32)),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="span"),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("ended_at", TS, nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_to_first_token_ms", sa.Integer()),
        sa.Column("status", sa.String(8), nullable=False, server_default="ok"),
        sa.Column("status_message", sa.Text()),
        sa.Column("level", sa.String(8), nullable=False, server_default="default"),
        sa.Column("agent_name", sa.String(120)),
        sa.Column("tool_name", sa.String(120)),
        sa.Column("prompt_name", sa.String(120)),
        sa.Column("prompt_version", sa.Integer()),
        sa.Column("model", sa.String(160)),
        sa.Column("provider", sa.String(48)),
        sa.Column("model_parameters", pg.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cached_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("usage_estimated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("input_cost", COST, nullable=False, server_default="0"),
        sa.Column("output_cost", COST, nullable=False, server_default="0"),
        sa.Column("total_cost", COST, nullable=False, server_default="0"),
        sa.Column("cost_source", sa.String(16)),
        sa.Column("input", sa.Text()),
        sa.Column("output", sa.Text()),
        sa.Column("metadata", pg.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        sa.Column("redactions", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("project_id", "trace_id", "id"),
        sa.ForeignKeyConstraint(
            ["project_id", "trace_id"],
            ["traces.project_id", "traces.id"],
            ondelete="CASCADE",
            name="fk_spans_trace",
        ),
        _check_in("status", ("ok", "error"), "status"),
        _check_in(
            "kind",
            ("span", "generation", "embedding", "agent", "tool", "retriever"),
            "kind",
        ),
    )
    op.create_index("ix_spans_project_started", "spans", ["project_id", "started_at"])
    op.create_index("ix_spans_project_kind", "spans", ["project_id", "kind", "started_at"])
    for column in ("model", "agent_name", "tool_name"):
        op.create_index(
            f"ix_spans_project_{column}",
            "spans",
            ["project_id", column, "started_at"],
            postgresql_where=sa.text(f"{column} IS NOT NULL"),
        )
    op.create_index(
        "ix_spans_project_prompt",
        "spans",
        ["project_id", "prompt_name", "prompt_version", "started_at"],
        postgresql_where=sa.text("prompt_name IS NOT NULL"),
    )

    op.create_table(
        "prompt_versions",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("template", sa.Text()),
        sa.Column("config", pg.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        sa.Column("labels", pg.ARRAY(sa.String(32)), nullable=False, server_default="{}"),
        sa.Column("commit_message", sa.String(300)),
        sa.Column("managed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", UUID),
        _created(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", "version"),
        _fk("project_id", "projects", "CASCADE"),
        _fk("created_by", "users", "SET NULL"),
        sa.CheckConstraint("version > 0", name="version"),
    )
    op.create_index("ix_prompt_versions_project_id", "prompt_versions", ["project_id"])

    op.create_table(
        "model_prices",
        _id(),
        sa.Column("project_id", UUID),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("match_pattern", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(48), nullable=False, server_default=""),
        sa.Column("input_per_mtok", PRICE, nullable=False),
        sa.Column("output_per_mtok", PRICE, nullable=False),
        sa.Column("cached_input_per_mtok", PRICE),
        sa.Column("source", sa.String(8), nullable=False),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        _fk("project_id", "projects", "CASCADE"),
        _check_in("source", ("builtin", "custom"), "source"),
        sa.CheckConstraint("input_per_mtok >= 0 AND output_per_mtok >= 0", name="non_negative"),
    )
    op.create_index("ix_model_prices_project_id", "model_prices", ["project_id"])
    # One price per model and scope: the shared table and each project's overrides.
    op.create_index(
        "uq_model_prices_shared",
        "model_prices",
        ["model"],
        unique=True,
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.create_index(
        "uq_model_prices_project",
        "model_prices",
        ["project_id", "model"],
        unique=True,
        postgresql_where=sa.text("project_id IS NOT NULL"),
    )

    op.create_table(
        "budgets",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("scope_value", sa.String(160)),
        sa.Column("period", sa.String(8), nullable=False),
        sa.Column("limit_usd", sa.Numeric(14, 4), nullable=False),
        sa.Column("warn_at_percent", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        _fk("project_id", "projects", "CASCADE"),
        _check_in("scope", ("project", "model", "agent", "tool", "prompt"), "scope"),
        _check_in("period", ("day", "week", "month"), "period"),
        sa.CheckConstraint("limit_usd > 0", name="limit_positive"),
        sa.CheckConstraint("warn_at_percent BETWEEN 1 AND 100", name="warn_percent"),
        sa.CheckConstraint(
            "(scope = 'project') = (scope_value IS NULL)", name="scope_value_matches_scope"
        ),
    )
    op.create_index("ix_budgets_project_id", "budgets", ["project_id"])

    op.create_table(
        "alert_rules",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("metric", sa.String(24), nullable=False),
        sa.Column("comparator", sa.String(8), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 4), nullable=False),
        sa.Column("window_minutes", sa.Integer(), nullable=False),
        sa.Column("min_traces", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("severity", sa.String(8), nullable=False, server_default="warning"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        _created(),
        _updated(),
        sa.PrimaryKeyConstraint("id"),
        _fk("project_id", "projects", "CASCADE"),
        _check_in("metric", ("error_rate", "p95_latency_ms", "cost_usd", "trace_count"), "metric"),
        _check_in("comparator", ("above", "below"), "comparator"),
        _check_in("severity", ("warning", "critical"), "severity"),
        sa.CheckConstraint("window_minutes BETWEEN 1 AND 10080", name="window"),
    )
    op.create_index("ix_alert_rules_project_id", "alert_rules", ["project_id"])

    op.create_table(
        "alert_events",
        _id(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("source_id", UUID, nullable=False),
        sa.Column("source_name", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(8), nullable=False),
        sa.Column("state", sa.String(8), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 4), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("fired_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", TS),
        sa.Column("notified_at", TS),
        sa.Column("notify_error", sa.String(200)),
        sa.PrimaryKeyConstraint("id"),
        _fk("project_id", "projects", "CASCADE"),
        _check_in("kind", ("budget", "rule"), "kind"),
        _check_in("severity", ("warning", "critical"), "severity"),
        _check_in("state", ("firing", "resolved"), "state"),
    )
    op.create_index(
        "uq_alert_events_open_source",
        "alert_events",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text("state = 'firing'"),
    )
    op.create_index(
        "ix_alert_events_project_fired",
        "alert_events",
        ["project_id", sa.text("fired_at DESC")],
    )

    op.create_table(
        "audit_events",
        _id(),
        sa.Column("actor_user_id", UUID),
        sa.Column("project_id", UUID),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(64)),
        sa.Column("details", pg.JSONB(), nullable=False, server_default=JSONB_EMPTY),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        _fk("actor_user_id", "users", "SET NULL"),
        _fk("project_id", "projects", "CASCADE"),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_events_project_id", "audit_events", ["project_id"])


def downgrade() -> None:
    for table in (
        "audit_events",
        "alert_events",
        "alert_rules",
        "budgets",
        "model_prices",
        "prompt_versions",
        "spans",
        "traces",
        "api_keys",
        "projects",
        "users",
    ):
        op.drop_table(table)
