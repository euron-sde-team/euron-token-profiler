from __future__ import annotations

from decimal import Decimal

from tokenprofiler.ingest.pricing import PriceBook, PriceEntry, compile_pattern, normalize_model
from tokenprofiler.pricing import load_builtin_prices


def book(project_overrides: list[PriceEntry] | None = None) -> PriceBook:
    _, rows = load_builtin_prices()
    entries = [
        PriceEntry(
            model=r.model,
            pattern=compile_pattern(r.pattern),
            input_per_mtok=r.input_per_mtok,
            output_per_mtok=r.output_per_mtok,
            cached_input_per_mtok=r.cached_input_per_mtok,
            provider=r.provider,
        )
        for r in rows
    ]
    return PriceBook([*entries, *(project_overrides or [])])


def test_normalisation_strips_routing_prefixes() -> None:
    assert normalize_model("OpenAI/GPT-4o") == "gpt-4o"
    assert normalize_model("anthropic.claude-3-5-sonnet-20241022-v2:0") == (
        "claude-3-5-sonnet-20241022"
    )
    assert normalize_model("llama3.2:3b") == "llama3.2:3b"


def test_dated_snapshots_price_like_their_family() -> None:
    b = book()
    assert b.lookup("gpt-4o-2024-08-06").model == "gpt-4o"  # type: ignore[union-attr]
    assert b.lookup("claude-sonnet-4-5-20250929").model == "claude-sonnet-4-5"  # type: ignore[union-attr]
    assert b.lookup("openai/gpt-4o-mini").model == "gpt-4o-mini"  # type: ignore[union-attr]


def test_a_specific_model_is_not_swallowed_by_its_family() -> None:
    b = book()
    assert b.lookup("gpt-4.1-mini").model == "gpt-4.1-mini"  # type: ignore[union-attr]
    assert b.lookup("gpt-4o-mini").input_per_mtok == Decimal("0.15")  # type: ignore[union-attr]


def test_unknown_models_have_no_price_and_ollama_tags_are_free() -> None:
    b = book()
    assert b.lookup("totally-new-model") is None
    local = b.lookup("llama3.2:3b")
    assert local is not None
    assert local.input_per_mtok == 0


def test_cost_arithmetic_with_cache_discount() -> None:
    b = book()
    cost = b.cost("gpt-4o", input_tokens=1_000_000, output_tokens=500_000, cached_tokens=400_000)
    assert cost is not None
    # 600k fresh at 2.50 + 400k cached at 1.25 = 2.00; 500k out at 10 = 5.00
    assert cost.input == Decimal("2.00000000")
    assert cost.output == Decimal("5.00000000")
    assert cost.total == Decimal("7.00000000")


def test_cached_tokens_without_a_cache_price_bill_at_the_input_rate() -> None:
    b = book()
    cost = b.cost("gpt-4-turbo", input_tokens=1_000_000, output_tokens=0, cached_tokens=500_000)
    assert cost is not None
    assert cost.input == Decimal("10.00000000")


def test_project_override_wins() -> None:
    override = PriceEntry(
        model="gpt-4o",
        pattern=compile_pattern("^gpt-4o$"),
        input_per_mtok=Decimal("1"),
        output_per_mtok=Decimal("2"),
        project_scoped=True,
    )
    cost = book([override]).cost("gpt-4o", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost is not None
    assert cost.total == Decimal("3.00000000")


def test_builtin_table_is_sane() -> None:
    version, rows = load_builtin_prices()
    assert version
    assert len(rows) >= 40
    assert len({r.model for r in rows}) == len(rows)
    assert all(r.input_per_mtok >= 0 and r.output_per_mtok >= 0 for r in rows)
