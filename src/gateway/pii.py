"""Redaction of personal data in prompts and logs. Regex-based and deliberately conservative: it catches
structured identifiers (emails, phone numbers, IBANs, card numbers, German tax IDs), not names."""

from __future__ import annotations

import re
from collections import Counter

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,3})?\b")),
    ("card", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    # international (+49 ...) or national (0151 ...) numbers; bare digit groups are left alone
    ("phone", re.compile(r"(?<![\w.+])(?:\+\d{1,3}[ /-]?|0)\(?\d{2,5}\)?[ /-]?\d{3,8}(?:[ /-]?\d{1,6})?(?![\w.])")),
    ("tax-id", re.compile(r"\b\d{2} ?\d{3} ?\d{3} ?\d{3}\b")),
]


def _luhn(digits: str) -> bool:
    nums = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(nums) <= 19:
        return False
    total = 0
    for i, n in enumerate(reversed(nums)):
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def redact(text: str) -> tuple[str, Counter[str]]:
    counts: Counter[str] = Counter()
    for kind, pat in PATTERNS:

        def repl(m: re.Match[str], kind: str = kind) -> str:
            if kind == "card" and not _luhn(m.group(0)):
                return m.group(0)
            counts[kind] += 1
            return f"[{kind.upper()}]"

        text = pat.sub(repl, text)
    return text, counts
