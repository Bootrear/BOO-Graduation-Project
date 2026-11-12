from cyber_qa.retrieval import extract_security_ids


def test_extracts_supported_ids_and_deduplicates() -> None:
    question = "比较 cve-2024-12345 与 CWE-79，并说明 T1059.001；再次提到 CWE-79。"

    assert extract_security_ids(question) == (
        "CVE-2024-12345",
        "CWE-79",
        "T1059.001",
    )


def test_returns_empty_tuple_without_security_id() -> None:
    assert extract_security_ids("什么是跨站脚本攻击？") == ()
