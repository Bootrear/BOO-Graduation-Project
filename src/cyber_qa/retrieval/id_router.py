"""Extract exact cybersecurity identifiers before semantic retrieval."""

from __future__ import annotations

import re


_SECURITY_ID_PATTERN = re.compile(
    r"\b(?:CVE-\d{4}-\d{4,}|CWE-\d+|CAPEC-\d+|T\d{4}(?:\.\d{3})?)\b",
    flags=re.IGNORECASE,
)


def extract_security_ids(question: str) -> tuple[str, ...]:
    """Return unique CVE/CWE/CAPEC/ATT&CK technique IDs in appearance order."""

    seen: set[str] = set()
    identifiers: list[str] = []
    for match in _SECURITY_ID_PATTERN.finditer(question):
        identifier = match.group(0).upper()
        if identifier not in seen:
            seen.add(identifier)
            identifiers.append(identifier)
    return tuple(identifiers)
