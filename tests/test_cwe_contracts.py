from dataclasses import asdict, replace
import hashlib
import zipfile

import pytest

from cyber_qa.data.contracts import (
    Passage, make_manifest, make_passage, normalize_text, text_sha256,
)
from cyber_qa.data.cwe import NAMESPACE, PARSER_VERSION, parse_cwe


def catalog(tmp_path, weaknesses, extra=""):
    path = tmp_path / "fixture.xml"
    path.write_text(f'''<Weakness_Catalog xmlns="{NAMESPACE}" Version="4.20"
        xmlns:h="http://www.w3.org/1999/xhtml"><Weaknesses>{weaknesses}</Weaknesses>
        {extra}</Weakness_Catalog>''')
    return path


def weakness(number="1", content="<Description>Identical text.</Description>"):
    return f'<Weakness ID="{number}" Name="Synthetic fixture" Status="Draft">{content}</Weakness>'


def manifest(parsed, **changes):
    values = dict(dataset_name="CWE", dataset_version=parsed.dataset_version,
                  source_download_url="https://example.invalid/synthetic.xml",
                  raw_file_sha256=parsed.raw_file_sha256, acquired_at=None,
                  acquired_at_basis="unknown", registered_at="2026-11-13T14:00:00+08:00",
                  processed_at="2026-11-13T14:01:00+08:00", parser_version=PARSER_VERSION,
                  chunker_version="fixture-only", preprocessing_config={"normalization": "NFC-LF"})
    values.update(changes)
    return make_manifest(**values)


def test_real_semantic_shapes_preserve_pairs_and_list_context(tmp_path):
    content = '''<Description>Do not <h:b>lose</h:b> inline words.</Description>
    <Extended_Description><h:p>First condition.</h:p><h:ol>
    <h:li>First case.</h:li><h:li>Second case.</h:li></h:ol></Extended_Description>
    <Common_Consequences><Consequence><Scope>Availability</Scope><Impact>Crash</Impact>
    <Note>Only under this condition.</Note></Consequence><Consequence>
    <Scope>Integrity</Scope><Impact>Change</Impact></Consequence></Common_Consequences>
    <Detection_Methods><Detection_Method><Method>Manual</Method>
    <Description>Inspect the boundary.</Description><Effectiveness>Limited</Effectiveness>
    </Detection_Method></Detection_Methods><Potential_Mitigations><Mitigation>
    <Phase>Design</Phase><Strategy>Isolation</Strategy><Description>Separate components.</Description>
    </Mitigation></Potential_Mitigations>'''
    parsed = parse_cwe(catalog(tmp_path, weakness(content=content),
        '<Categories><Category ID="100"/></Categories><Views><View ID="200"/></Views>'))
    assert len(parsed.units) == 6
    assert parsed.units[0].source_text == "Do not lose inline words."
    assert "1. First case.\n2. Second case." in parsed.units[1].source_text
    first, second = parsed.units[2:4]
    assert first.source_text == "Scope: Availability\nImpact: Crash\nNote: Only under this condition."
    assert "Integrity" not in first.source_text
    assert first.source_locator.endswith("Consequence[1]")
    assert second.source_locator.endswith("Consequence[2]")
    assert "Method: Manual\nDescription: Inspect the boundary." in parsed.units[4].source_text
    assert parsed.units[5].source_text.startswith("Phase: Design\nStrategy: Isolation\nDescription:")
    assert parsed.statistics["excluded_categories"] == 1
    assert parsed.statistics["excluded_views"] == 1
    assert parsed.statistics["entries_included"] == 1
    assert sum(parsed.statistics["missing_fields"].values()) == 0


def test_missing_empty_long_and_duplicate_records(tmp_path):
    long_text = "Long source with conditions. " * 1000
    first = weakness(content=f"<Description>{long_text}</Description><Extended_Description> </Extended_Description>")
    parsed = parse_cwe(catalog(tmp_path, first + "\n" + first + weakness("2", "")))
    assert len(parsed.units) == 1
    assert parsed.units[0].source_text == long_text.strip()
    assert parsed.statistics["entries_read"] == 3
    assert parsed.statistics["entries_included"] == 1
    assert parsed.statistics["duplicate_entries"] == 1
    assert parsed.statistics["duplicate_source_units"] == 1
    assert parsed.statistics["empty_texts"] == 1
    assert parsed.statistics["missing_fields"]["description"] == 1


def test_conflicting_duplicate_entry_is_rejected(tmp_path):
    path = catalog(tmp_path, weakness() + weakness(content="<Description>Different.</Description>"))
    with pytest.raises(ValueError, match="conflicting duplicate"):
        parse_cwe(path)


def test_cross_source_identical_text_retains_distinct_stable_passages(tmp_path):
    path = catalog(tmp_path, weakness() + weakness("2"))
    parsed = parse_cwe(path)
    m = manifest(parsed)
    passages = [make_passage(u, m, 0, u.source_text) for u in parsed.units]
    assert passages[0].text == passages[1].text
    assert passages[0].passage_id != passages[1].passage_id
    assert passages[0].source_url != passages[1].source_url
    assert parsed.statistics["cross_source_identical_texts"] == 1
    later = manifest(parsed, processed_at="2026-11-14T10:00:00Z", registered_at="2026-11-14T09:00:00Z")
    assert m.snapshot_id == later.snapshot_id
    again = [make_passage(u, later, 0, u.source_text) for u in parse_cwe(path).units]
    assert passages == again
    assert Passage(**passages[0].to_dict()) == passages[0]
    expected = {"passage_id", "cwe_id", "title", "field_name", "source_locator", "chunk_index",
                "source_text", "text", "source_url", "dataset_version", "snapshot_id", "acquired_at",
                "content_sha256", "entry_status"}
    assert set(asdict(passages[0])) == expected
    assert passages[0].content_sha256 == hashlib.sha256(passages[0].text.encode()).hexdigest()
    altered = manifest(parsed, preprocessing_config={"normalization": "other"})
    assert altered.snapshot_id != m.snapshot_id


def test_utf8_hash_and_normalization(tmp_path):
    assert normalize_text("  Cafe\u0301\r\n\tline  two \r\n\r\n") == "Café\nline two"
    parsed = parse_cwe(catalog(tmp_path, weakness(content="<Description>Cafe\u0301</Description>")))
    p = make_passage(parsed.units[0], manifest(parsed), 0, "Café")
    assert p.content_sha256 == text_sha256("Café")
    with pytest.raises(ValueError, match="hash"):
        replace(p, content_sha256="0" * 64)
    with pytest.raises(ValueError, match="slice"):
        make_passage(parsed.units[0], manifest(parsed), 0, "Invented")
    with pytest.raises(ValueError, match="passage_id"):
        replace(p, passage_id="random-id")
    with pytest.raises(ValueError, match="snapshot_id"):
        replace(p, snapshot_id="unverified")


@pytest.mark.parametrize("changes", [
    {"acquired_at": "2026-11-13T00:00:00Z"},
    {"acquired_at_basis": "file_mtime"},
    {"registered_at": "2026-11-13T00:00:00"},
    {"processed_at": "bad"},
    {"raw_file_sha256": "bad"},
])
def test_bad_manifest_time_and_hash_contracts(tmp_path, changes):
    parsed = parse_cwe(catalog(tmp_path, weakness()))
    with pytest.raises(ValueError):
        manifest(parsed, **changes)


def test_observed_acquisition_metadata_does_not_change_identity(tmp_path):
    parsed = parse_cwe(catalog(tmp_path, weakness()))
    unknown = manifest(parsed)
    known = manifest(parsed, acquired_at="2026-11-13T00:00:00Z", acquired_at_basis="download_completed")
    assert known.snapshot_id == unknown.snapshot_id


def test_zip_and_xml_support_and_multifile_rejection(tmp_path):
    path = catalog(tmp_path, weakness())
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.write(path, "fixture.xml")
    xml_parsed, zip_parsed = parse_cwe(path), parse_cwe(archive)
    assert xml_parsed.units == zip_parsed.units
    assert xml_parsed.raw_file_sha256 != zip_parsed.raw_file_sha256
    assert zip_parsed.xml_member == "fixture.xml"
    with zipfile.ZipFile(archive, "a") as z:
        z.writestr("extra.xml", "<extra/>")
    with pytest.raises(ValueError, match="exactly one"):
        parse_cwe(archive)


@pytest.mark.parametrize("old,new", [
    (NAMESPACE, "https://invalid.example/ns"), ('Version="4.20"', 'Version="5.0"'),
    ('ID="1"', 'ID="bad"'), ('Name="Synthetic fixture"', 'Name=""'),
])
def test_rejects_unverified_formats_and_invalid_records(tmp_path, old, new):
    path = catalog(tmp_path, weakness())
    path.write_text(path.read_text().replace(old, new))
    with pytest.raises(ValueError):
        parse_cwe(path)


def test_rejects_dtd(tmp_path):
    path = catalog(tmp_path, weakness())
    path.write_text('<!DOCTYPE Weakness_Catalog []>' + path.read_text())
    with pytest.raises(ValueError, match="DTD"):
        parse_cwe(path)
