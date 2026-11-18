from __future__ import annotations

import pytest

from tokenprofiler.ingest.redaction import TRUNCATED, luhn_valid, validate_pattern
from tokenprofiler.schemas.redaction import CustomRule, RedactionRules


def redactor(**kwargs: object):
    return RedactionRules.model_validate(kwargs).redactor()


def test_builtin_detectors_mask_pii() -> None:
    r = redactor()
    text = (
        "mail sam.lee@example.com or call +1 415-555-0134, card 4111 1111 1111 1111, "
        "ssn 123-45-6789, key sk-abcdefghijklmnopqrstuvwxyz123456"
    )
    masked = r.mask(text)
    for needle in ("sam.lee@example.com", "415-555-0134", "4111 1111", "123-45-6789", "sk-abc"):
        assert needle not in masked
    assert "[REDACTED:email]" in masked
    assert r.count == 5
    assert r.hits["credit_card"] == 1


def test_card_numbers_need_a_valid_checksum() -> None:
    assert (
        redactor(detectors=["credit_card"]).mask("order 1234 5678 9012 3456")
        == "order 1234 5678 9012 3456"
    )
    assert luhn_valid("4111111111111111")
    assert not luhn_valid("4111111111111112")


def test_ipv4_is_opt_in() -> None:
    assert redactor().mask("host 10.0.0.12") == "host 10.0.0.12"
    assert "[REDACTED:ipv4]" in redactor(detectors=["ipv4"]).mask("host 10.0.0.12")


def test_structure_survives_and_numbers_are_untouched() -> None:
    r = redactor()
    value = {"user": "a@example.com", "count": 4111111111111111, "items": ["ok", "b@example.com"]}
    assert r.walk(value) == {
        "user": "[REDACTED:email]",
        "count": 4111111111111111,
        "items": ["ok", "[REDACTED:email]"],
    }


def test_custom_rule_and_replacement() -> None:
    rules = RedactionRules(
        detectors=[], custom=[CustomRule(name="emp", pattern=r"EMP-\d{6}", replacement="[EMP]")]
    )
    r = rules.redactor()
    assert r.mask("EMP-123456 asked") == "[EMP] asked"
    assert r.hits == {"emp": 1}


def test_payload_respects_limits_and_switches() -> None:
    r = redactor(max_payload_chars=100)
    out = r.payload("x" * 500)
    assert out is not None
    assert out.endswith(TRUNCATED)
    assert len(out) <= 100 + len(TRUNCATED)
    assert redactor(store_payloads=False).payload("secret") is None
    assert r.payload(None) is None
    assert redactor().payload({"a": "b"}) == '{"a": "b"}'


def test_nul_bytes_are_removed() -> None:
    assert redactor().mask("a\x00b") == "ab"


def test_deep_nesting_is_cut() -> None:
    value: object = "leaf"
    for _ in range(30):
        value = [value]
    assert "nested too deeply" in str(redactor().walk(value))


@pytest.mark.parametrize("pattern", ["(a+)+", "(.*)*x", "(\\w+\\s?)+$"])
def test_catastrophic_patterns_are_refused(pattern: str) -> None:
    assert validate_pattern(pattern) is not None
    with pytest.raises(ValueError, match="Nested repetition"):
        CustomRule(name="x", pattern=pattern)


def test_bad_patterns_are_refused() -> None:
    assert validate_pattern("(") is not None
    assert validate_pattern("") is not None
    assert validate_pattern("a" * 300) is not None
    assert validate_pattern(r"EMP-\d{6}") is None


def test_unknown_detector_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown detectors"):
        RedactionRules(detectors=["nope"])
