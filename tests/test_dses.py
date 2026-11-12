from cyber_qa.data import Evidence
from cyber_qa.selection import Candidate, DSESConfig, select_evidence


def evidence(identifier: str, field_name: str, tokens: int = 100) -> Evidence:
    return Evidence(
        evidence_id=f"test:{identifier}:{field_name}",
        source="TEST",
        record_id=identifier,
        record_type="test",
        field_name=field_name,
        text="test evidence",
        url="https://example.invalid/test",
        source_version="test",
        token_count=tokens,
    )


def test_prefers_new_required_field_over_redundant_field() -> None:
    first = Candidate(
        evidence("A", "description"),
        relevance=0.95,
        covered_fields=frozenset({"description"}),
    )
    redundant = Candidate(
        evidence("B", "description"),
        relevance=0.90,
        covered_fields=frozenset({"description"}),
    )
    complementary = Candidate(
        evidence("C", "mitigation"),
        relevance=0.75,
        covered_fields=frozenset({"mitigation"}),
    )

    def similarity(left: Candidate, right: Candidate) -> float:
        pair = {left.evidence.record_id, right.evidence.record_id}
        return 0.9 if pair == {"A", "B"} else 0.0

    result = select_evidence(
        [first, redundant, complementary],
        required_fields={"description", "mitigation"},
        max_items=2,
        token_budget=300,
        config=DSESConfig(coverage_weight=0.8, redundancy_weight=0.5),
        similarity=similarity,
    )

    assert [item.evidence.record_id for item in result.selected] == ["A", "C"]
    assert result.covered_fields == {"description", "mitigation"}


def test_respects_token_budget() -> None:
    candidates = [
        Candidate(evidence("A", "description", 120), relevance=0.9),
        Candidate(evidence("B", "impact", 120), relevance=0.8),
    ]

    result = select_evidence(
        candidates,
        required_fields=set(),
        max_items=2,
        token_budget=200,
    )

    assert len(result.selected) == 1
    assert result.used_tokens == 120
