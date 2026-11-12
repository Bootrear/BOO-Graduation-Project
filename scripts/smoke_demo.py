"""Run a dependency-free DSES smoke example."""

from __future__ import annotations

import json

from cyber_qa.data import Evidence
from cyber_qa.selection import Candidate, select_evidence


def make_evidence(identifier: str, field_name: str, token_count: int) -> Evidence:
    return Evidence(
        evidence_id=f"demo:{identifier}:{field_name}",
        source="DEMO",
        record_id=identifier,
        record_type="demonstration",
        field_name=field_name,
        text="This is synthetic demonstration text, not an official security fact.",
        url="https://example.invalid/demo",
        source_version="demo-only",
        token_count=token_count,
    )


def main() -> None:
    candidates = [
        Candidate(
            make_evidence("CVE-DEMO", "description", 100),
            relevance=0.95,
            entity_match=1.0,
            covered_fields=frozenset({"description", "impact"}),
        ),
        Candidate(
            make_evidence("CVE-DEMO", "mitigation", 90),
            relevance=0.80,
            entity_match=1.0,
            covered_fields=frozenset({"mitigation"}),
        ),
        Candidate(
            make_evidence("OTHER-DEMO", "description", 120),
            relevance=0.85,
            covered_fields=frozenset({"description"}),
        ),
    ]
    result = select_evidence(
        candidates,
        required_fields={"description", "impact", "mitigation"},
        max_items=2,
        token_budget=256,
    )
    print(
        json.dumps(
            {
                "selected": [item.evidence.evidence_id for item in result.selected],
                "covered_fields": sorted(result.covered_fields),
                "used_tokens": result.used_tokens,
                "steps": [step.__dict__ for step in result.steps],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
