"""PII redaction and payload limits, applied before anything is written.

Rules come from the project: built-in detectors (email, phone, card number, US SSN, IPv4,
API keys and tokens) plus custom regular expressions. Strings anywhere inside an input,
output or metadata value are masked; numbers, booleans and keys are never touched, so the
JSON structure survives. Custom patterns are checked when they are saved (`validate_pattern`)
because Python's `re` has no match timeout: nested quantifiers are refused outright, and
every string is cut to the project's payload limit before any rule runs.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

MAX_PATTERN_LENGTH = 200
MAX_DEPTH = 12
TRUNCATED = "...[truncated]"

BUILTIN_DETECTORS: dict[str, str] = {
    "email": r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}",
    "credit_card": r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])",
    "ssn": r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)",
    "phone": (
        r"(?<![\w+])(?:\+\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?|\d{2,4}[ -])"
        r"\d{3,4}[ -]\d{3,4}(?!\w)"
    ),
    "ipv4": r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])",
    "api_key": (
        r"\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}"
        r"|xox[baprs]-[A-Za-z0-9-]{10,}|tp_[a-z2-7]{10}_[A-Za-z0-9_-]{43})\b"
    ),
    "jwt": r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
}
DEFAULT_DETECTORS = ("email", "credit_card", "ssn", "phone", "api_key", "jwt")

# A group that is repeated and itself contains a repeat is how catastrophic backtracking
# is written: (a+)+, (a*)*, (.+)*, (\w+\s?)+ ...
_NESTED_QUANTIFIER = re.compile(r"\((?:[^()\\]|\\.)*[+*](?:[^()\\]|\\.)*\)[+*{]")


def validate_pattern(pattern: str) -> str | None:
    """Why a custom pattern cannot be used, or None when it is fine."""
    if not pattern or len(pattern) > MAX_PATTERN_LENGTH:
        return f"Use a pattern of 1 to {MAX_PATTERN_LENGTH} characters."
    if _NESTED_QUANTIFIER.search(pattern):
        return "Nested repetition such as (a+)+ can hang the ingest path; simplify the pattern."
    try:
        re.compile(pattern)
    except re.error as exc:
        return f"Not a valid regular expression: {exc}."
    return None


def luhn_valid(digits: str) -> bool:
    total, flip = 0, False
    for char in reversed(digits):
        number = ord(char) - 48
        if flip:
            number *= 2
            if number > 9:
                number -= 9
        total += number
        flip = not flip
    return total % 10 == 0


@dataclass(frozen=True, slots=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    replacement: str
    accept: Callable[[str], bool] | None = None


@dataclass(slots=True)
class Redactor:
    rules: list[Rule]
    store_payloads: bool = True
    max_chars: int = 20_000
    redact_metadata: bool = True
    count: int = field(default=0)
    hits: dict[str, int] = field(default_factory=dict)

    def mask(self, text: str) -> str:
        # Postgres text cannot hold NUL bytes.
        text = text.replace("\x00", "")
        if len(text) > self.max_chars:
            text = text[: self.max_chars]
            truncated = True
        else:
            truncated = False
        for rule in self.rules:

            def replace(match: re.Match[str], rule: Rule = rule) -> str:
                if rule.accept is not None and not rule.accept(match.group(0)):
                    return match.group(0)
                self.count += 1
                self.hits[rule.name] = self.hits.get(rule.name, 0) + 1
                return rule.replacement

            text = rule.pattern.sub(replace, text)
        return text + TRUNCATED if truncated else text

    def walk(self, value: Any, depth: int = 0) -> Any:
        if isinstance(value, str):
            return self.mask(value)
        if depth >= MAX_DEPTH:
            return "[nested too deeply]"
        if isinstance(value, dict):
            return {str(key): self.walk(item, depth + 1) for key, item in value.items()}
        if isinstance(value, list | tuple):
            return [self.walk(item, depth + 1) for item in value]
        return value

    def payload(self, value: Any) -> str | None:
        """Masked, serialised and length-limited text for an input or an output."""
        if value is None or not self.store_payloads:
            return None
        masked = self.walk(value)
        if isinstance(masked, str):
            return masked
        text = json.dumps(masked, ensure_ascii=False, default=str)
        if len(text) > self.max_chars:
            return text[: self.max_chars] + TRUNCATED
        return text

    def metadata(self, value: dict[str, Any]) -> dict[str, Any]:
        if not self.redact_metadata:
            return value
        walked = self.walk(value)
        return walked if isinstance(walked, dict) else {}


def build_redactor(
    *,
    detectors: list[str] | tuple[str, ...],
    custom: list[tuple[str, str, str]],
    store_payloads: bool,
    max_chars: int,
    redact_metadata: bool,
) -> Redactor:
    rules: list[Rule] = []
    # Canonical order, whatever order the project lists them in: a card number must be
    # recognised before the phone pattern can claim a run of its digits.
    for name in BUILTIN_DETECTORS:
        if name in detectors:
            accept = (
                (lambda s: luhn_valid(re.sub(r"\D", "", s)) and len(re.sub(r"\D", "", s)) >= 13)
                if name == "credit_card"
                else None
            )
            rules.append(
                Rule(name, re.compile(BUILTIN_DETECTORS[name]), f"[REDACTED:{name}]", accept)
            )
    for name, pattern, replacement in custom:
        rules.append(Rule(name, re.compile(pattern), replacement))
    return Redactor(
        rules=rules,
        store_payloads=store_payloads,
        max_chars=max_chars,
        redact_metadata=redact_metadata,
    )
