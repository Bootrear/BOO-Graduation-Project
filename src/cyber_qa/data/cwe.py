"""CWE 4.20 XML/ZIP parsing, verified against the real MITRE archive.

Each nested consequence, detection method or mitigation remains one source unit.
Token-aware splitting is a separate stage; these are not index-ready passages.
"""

from __future__ import annotations

import hashlib
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from .contracts import SourceUnit, normalize_text

PARSER_VERSION = "cwe-xml-4.20-v1"
NAMESPACE = "http://cwe.mitre.org/cwe-7"
NS = {"c": NAMESPACE}
FIELD_PATHS = {
    "description": "Description",
    "extended_description": "Extended_Description",
    "common_consequences": "Common_Consequences/Consequence",
    "detection_methods": "Detection_Methods/Detection_Method",
    "potential_mitigations": "Potential_Mitigations/Mitigation",
}
MAX_XML_BYTES = 64 * 1024 * 1024


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _render(element: ET.Element) -> str:
    parts = [element.text or ""]
    for index, child in enumerate(element, 1):
        tag = _local(child.tag)
        block = tag in {"p", "div", "li", "br", "pre", "tr", "ul", "ol"}
        if block:
            parts.append("\n")
        if tag == "li":
            parts.append(f"{index}. " if _local(element.tag) == "ol" else "- ")
        parts.append(_render(child))
        if block:
            parts.append("\n")
        parts.append(child.tail or "")
    return "".join(parts)


def _source_text(element: ET.Element, *, nested: bool) -> str:
    if not nested:
        return normalize_text(_render(element))
    lines = []
    for child in element:
        value = normalize_text(_render(child))
        if value:
            # Labels come directly from source tags; no security claims are added.
            lines.append(f"{_local(child.tag)}: {value}")
    return normalize_text("\n".join(lines))


@dataclass(frozen=True)
class ParsedCWE:
    units: tuple[SourceUnit, ...]
    dataset_version: str
    namespace: str
    raw_file_sha256: str
    xml_member: str | None
    statistics: dict


def parse_cwe(path: str | Path) -> ParsedCWE:
    path = Path(path)
    if path.stat().st_size > MAX_XML_BYTES:
        raise ValueError("input exceeds supported 64 MiB size limit")
    raw = path.read_bytes()
    member = None
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = [i for i in archive.infolist() if not i.is_dir()]
            if len(members) != 1 or not members[0].filename.endswith(".xml"):
                raise ValueError("CWE ZIP must contain exactly one XML file")
            if members[0].file_size > MAX_XML_BYTES:
                raise ValueError("uncompressed XML exceeds 64 MiB")
            member = members[0].filename
            xml = archive.read(member)
    else:
        xml = raw
    # Initial support is UTF-8 only; reject entity/DTD inputs explicitly.
    decoded = xml.decode("utf-8-sig")
    if "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
        raise ValueError("DTD/entity declarations are not supported")
    root = ET.fromstring(decoded)
    if root.tag != f"{{{NAMESPACE}}}Weakness_Catalog":
        raise ValueError("unsupported CWE root or namespace")
    version = root.attrib.get("Version")
    if version != "4.20":
        raise ValueError(f"unsupported CWE version: {version!r}; validated version is 4.20")
    weaknesses = root.find("c:Weaknesses", NS)
    if weaknesses is None:
        raise ValueError("CWE Weaknesses container is missing")
    missing = Counter({key: 0 for key in FIELD_PATHS})
    stats = {"entries_read": 0, "entries_included": 0, "empty_texts": 0,
             "duplicate_entries": 0, "duplicate_source_units": 0,
             "cross_source_identical_texts": 0, "source_units": 0,
             "excluded_categories": len(root.findall("c:Categories/c:Category", NS)),
             "excluded_views": len(root.findall("c:Views/c:View", NS))}
    seen_entries: dict[str, bytes] = {}
    seen_texts: set[str] = set()
    units = []
    for weakness in weaknesses.findall("c:Weakness", NS):
        stats["entries_read"] += 1
        number = weakness.attrib.get("ID", "")
        if re.fullmatch(r"[0-9]+", number) is None or int(number) <= 0:
            raise ValueError(f"invalid CWE ID: {number!r}")
        cwe_id = f"CWE-{int(number)}"
        tail = weakness.tail
        weakness.tail = None  # Sibling formatting is not part of an entry.
        serialized = ET.tostring(weakness, encoding="utf-8")
        weakness.tail = tail
        duplicate = cwe_id in seen_entries
        if duplicate and seen_entries[cwe_id] != serialized:
            raise ValueError(f"conflicting duplicate entry: {cwe_id}")
        if duplicate:
            stats["duplicate_entries"] += 1
        seen_entries[cwe_id] = serialized
        title = normalize_text(weakness.attrib.get("Name", ""))
        if not title:
            raise ValueError(f"missing title for {cwe_id}")
        included = False
        for field_name, xpath in FIELD_PATHS.items():
            nodes = weakness.findall("/".join("c:" + tag for tag in xpath.split("/")), NS)
            if not nodes and not duplicate:
                missing[field_name] += 1
            for index, node in enumerate(nodes, 1):
                text = _source_text(node, nested="/" in xpath)
                if not text:
                    if not duplicate:
                        stats["empty_texts"] += 1
                    continue
                if duplicate:
                    stats["duplicate_source_units"] += 1
                    continue
                locator = f"/Weakness_Catalog/Weaknesses/Weakness[@ID='{number}']/{xpath}[{index}]"
                unit = SourceUnit(cwe_id=cwe_id, title=title, field_name=field_name,
                                  source_locator=locator, source_text=text,
                                  source_url=f"https://cwe.mitre.org/data/definitions/{int(number)}.html",
                                  dataset_version=version, entry_status=weakness.attrib.get("Status"))
                units.append(unit)
                included = True
                stats["cross_source_identical_texts"] += int(text in seen_texts)
                seen_texts.add(text)
        stats["entries_included"] += int(included)
    stats["missing_fields"] = dict(missing)
    stats["source_units"] = len(units)
    # This is pre-chunking output: final passage count is deliberately not claimed.
    return ParsedCWE(tuple(units), version, NAMESPACE, hashlib.sha256(raw).hexdigest(), member, stats)
