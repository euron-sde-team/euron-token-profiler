from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from tests.unit.test_pricing import book
from tokenprofiler.ingest.types import SpanIn
from tokenprofiler.services.ingest import price_span

NOW = datetime(2026, 11, 1, tzinfo=UTC)


def make(**kwargs: object) -> SpanIn:
    return SpanIn(
        trace_id="t",
        span_id="s",
        parent_id=None,
        name="n",
        kind="generation",
        started_at=NOW,
        ended_at=NOW,
        **kwargs,  # type: ignore[arg-type]
    )


def test_reported_usage_is_priced_from_the_table() -> None:
    priced = price_span(
        make(model="gpt-4o", input_tokens=1000, output_tokens=100), "generation", book()
    )
    assert (priced.source, priced.estimated) == ("table", False)
    assert priced.input_cost == Decimal("0.00250000")
    assert priced.output_cost == Decimal("0.00100000")


def test_missing_usage_is_estimated_and_flagged() -> None:
    priced = price_span(
        make(model="gpt-4o", input="x" * 400, output="y" * 80), "generation", book()
    )
    assert (priced.input_tokens, priced.output_tokens) == (100, 20)
    assert priced.estimated


def test_reported_cost_wins_over_the_table() -> None:
    priced = price_span(
        make(model="gpt-4o", input_tokens=10, output_tokens=10, reported_cost=Decimal("0.5")),
        "generation",
        book(),
    )
    assert priced.source == "reported"
    assert priced.input_cost + priced.output_cost == Decimal("0.5")


def test_unknown_model_is_zero_and_marked() -> None:
    priced = price_span(
        make(model="mystery", input_tokens=5, output_tokens=5), "generation", book()
    )
    assert priced.source == "none"
    assert priced.input_cost == 0


def test_only_metered_kinds_carry_usage() -> None:
    priced = price_span(make(model="gpt-4o", input_tokens=5), "tool", book())
    assert priced.input_tokens == 0
    assert priced.source is None


def test_embeddings_have_no_output_tokens() -> None:
    priced = price_span(
        make(model="text-embedding-3-small", input="hello world"), "embedding", book()
    )
    assert priced.output_tokens == 0
    assert priced.input_tokens > 0
