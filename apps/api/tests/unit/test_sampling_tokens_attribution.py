from __future__ import annotations

from decimal import Decimal

from tokenprofiler.ingest.attribution import Node, resolve_attribution
from tokenprofiler.ingest.sampling import keep_by_rate, sample_fraction
from tokenprofiler.ingest.tokens import estimate_tokens


def test_sampling_is_deterministic_and_proportional() -> None:
    ids = [f"trace-{i}" for i in range(4000)]
    first = [keep_by_rate(t, 0.25) for t in ids]
    assert first == [keep_by_rate(t, 0.25) for t in ids]
    assert 0.2 < sum(first) / len(ids) < 0.3
    assert all(keep_by_rate(t, 1) for t in ids[:50])
    assert not any(keep_by_rate(t, Decimal(0)) for t in ids[:50])
    assert 0 <= sample_fraction("x") < 1


def test_kept_traces_at_a_lower_rate_are_kept_at_a_higher_one() -> None:
    ids = [f"t{i}" for i in range(2000)]
    assert all(keep_by_rate(t, 0.5) for t in ids if keep_by_rate(t, 0.2))


def test_token_estimate() -> None:
    assert estimate_tokens(None) == 0
    assert estimate_tokens("") == 0
    assert estimate_tokens("a") == 1
    assert estimate_tokens("x" * 400) == 100
    assert estimate_tokens({"k": "v" * 100}) > 25
    assert estimate_tokens("你好世界") == 4


def test_attribution_flows_down_the_tree() -> None:
    nodes = [
        Node("a", None, "agent", "research-agent"),
        Node("b", "a", "generation", "plan"),
        Node("c", "a", "tool", "web_search"),
        Node("d", "c", "generation", "summarise"),
        Node("e", "d", "span", "post"),
    ]
    got = resolve_attribution(nodes)
    assert got["a"] == ("research-agent", None)
    assert got["b"] == ("research-agent", None)
    assert got["c"] == ("research-agent", "web_search")
    assert got["d"] == ("research-agent", "web_search")
    assert got["e"] == ("research-agent", "web_search")


def test_declared_names_win_and_orphans_are_tolerated() -> None:
    nodes = [
        Node("a", None, "agent", "outer"),
        Node("b", "a", "generation", "call", agent_name="inner"),
        Node("c", "missing", "generation", "orphan"),
    ]
    got = resolve_attribution(nodes)
    assert got["b"] == ("inner", None)
    assert got["c"] == (None, None)


def test_cycles_do_not_hang() -> None:
    nodes = [Node("a", "b", "span", "x"), Node("b", "a", "span", "y")]
    assert resolve_attribution(nodes) == {"a": (None, None), "b": (None, None)}
