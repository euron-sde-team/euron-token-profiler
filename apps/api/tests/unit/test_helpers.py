from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tokenprofiler.core.errors import NotFoundError, UnprocessableError
from tokenprofiler.core.security import (
    decode_session,
    generate_api_key,
    issue_session,
    looks_like_api_key,
    parse_api_key,
    validate_password,
    verify_api_key_secret,
)
from tokenprofiler.integrations.archive import LocalArchive, safe_key
from tokenprofiler.services.alerts import budget_state, period_bounds, rule_firing
from tokenprofiler.services.dashboards import bucket_for, resolve_window
from tokenprofiler.services.projects import slugify

NOW = datetime(2026, 11, 18, 15, 41, 7, tzinfo=UTC)


def test_bucket_sizes_target_a_readable_chart() -> None:
    assert bucket_for(timedelta(hours=1)) == timedelta(minutes=1)
    assert bucket_for(timedelta(hours=24)) == timedelta(minutes=30)
    assert bucket_for(timedelta(days=7)) == timedelta(hours=3)
    assert bucket_for(timedelta(days=30)) == timedelta(hours=12)
    assert bucket_for(timedelta(days=400)) == timedelta(days=1)


def test_relative_ranges_snap_to_thirty_seconds() -> None:
    start, end = resolve_window("24h", None, None, now=NOW)
    assert end == datetime(2026, 11, 18, 15, 41, 0, tzinfo=UTC)
    assert end - start == timedelta(hours=24)


def test_explicit_windows_are_validated() -> None:
    start = NOW - timedelta(days=2)
    assert resolve_window(None, start, None, now=NOW) == (start, NOW)
    with pytest.raises(UnprocessableError):
        resolve_window(None, NOW, NOW - timedelta(hours=1), now=NOW)
    with pytest.raises(UnprocessableError):
        resolve_window("3y", None, None, now=NOW)
    with pytest.raises(UnprocessableError):
        resolve_window(None, NOW - timedelta(days=900), None, now=NOW)


def test_budget_periods() -> None:
    day = period_bounds("day", NOW)
    assert day == (datetime(2026, 11, 18, tzinfo=UTC), datetime(2026, 11, 19, tzinfo=UTC))
    week = period_bounds("week", NOW)
    assert week[0].weekday() == 0
    assert week[0] == datetime(2026, 11, 16, tzinfo=UTC)
    assert week[1] - week[0] == timedelta(days=7)
    month = period_bounds("month", NOW)
    assert month == (datetime(2026, 11, 1, tzinfo=UTC), datetime(2026, 12, 1, tzinfo=UTC))
    assert period_bounds("month", datetime(2026, 12, 31, tzinfo=UTC))[1] == datetime(
        2027, 1, 1, tzinfo=UTC
    )


def test_budget_states() -> None:
    assert budget_state(Decimal(10), Decimal(100), 80) == "ok"
    assert budget_state(Decimal(80), Decimal(100), 80) == "warning"
    assert budget_state(Decimal(100), Decimal(100), 80) == "exceeded"


def test_rule_comparators() -> None:
    assert rule_firing("error_rate", "above", 9, 8)
    assert not rule_firing("error_rate", "above", 8, 8)
    assert rule_firing("trace_count", "below", 0, 1)


def test_slugify() -> None:
    assert slugify("Customer Copilot!") == "customer-copilot"
    assert slugify("???") == "project"


def test_api_keys_roundtrip_and_hide_the_secret() -> None:
    generated = generate_api_key("pepper")
    assert generated.plaintext.startswith("tp_")
    assert looks_like_api_key(generated.plaintext)
    parsed = parse_api_key(generated.plaintext)
    assert parsed is not None
    prefix, secret = parsed
    assert prefix == generated.prefix
    assert generated.secret_hash != secret
    assert verify_api_key_secret(secret, generated.secret_hash, "pepper")
    assert not verify_api_key_secret(secret, generated.secret_hash, "other")
    assert parse_api_key("tp_short") is None


def test_sessions() -> None:
    user = uuid.uuid4()
    token, claims = issue_session(user, 3, secret="s" * 40, ttl=timedelta(hours=1))
    decoded = decode_session(token, secret="s" * 40)
    assert decoded.user_id == user
    assert decoded.session_version == 3
    assert decoded.jti == claims.jti
    with pytest.raises(Exception, match="expired"):
        decode_session(token, secret="x" * 40)


def test_password_rules() -> None:
    validate_password("correct horse battery")
    for bad in ("short", "aaaaaaaaaaaa"):
        with pytest.raises(UnprocessableError):
            validate_password(bad)
    with pytest.raises(UnprocessableError):
        validate_password("me@example.com", email="ME@example.com")


async def test_local_archive_roundtrip_and_key_safety(tmp_path) -> None:  # type: ignore[no-untyped-def]
    archive = LocalArchive(tmp_path)
    await archive.put("demo/2026/11/18/a.ndjson.gz", b"data")
    assert await archive.get("demo/2026/11/18/a.ndjson.gz") == b"data"
    assert await archive.list("demo/", 10) == [("demo/2026/11/18/a.ndjson.gz", 4)]
    with pytest.raises(NotFoundError):
        await archive.get("demo/missing.ndjson.gz")
    for bad in ("../etc/passwd", "/abs", "a//b", "a/../b", ""):
        with pytest.raises(ValueError, match="not a valid"):
            safe_key(bad)
