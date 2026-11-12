"""Validate the downloaded starter cybersecurity datasets with stdlib only."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_nvd(year: int) -> dict[str, object]:
    archive = RAW / "nvd" / f"nvdcve-2.0-{year}.json.gz"
    metadata_path = archive.with_suffix("").with_suffix(".meta")
    metadata = {}
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        key, value = line.split(":", maxsplit=1)
        metadata[key] = value

    expected_gz_size = int(metadata["gzSize"])
    if archive.stat().st_size != expected_gz_size:
        raise ValueError(
            f"{archive.name}: compressed size {archive.stat().st_size} != {expected_gz_size}"
        )

    digest = hashlib.sha256()
    decompressed_size = 0
    with gzip.open(archive, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            decompressed_size += len(chunk)
            digest.update(chunk)

    if decompressed_size != int(metadata["size"]):
        raise ValueError(
            f"{archive.name}: decompressed size {decompressed_size} != {metadata['size']}"
        )
    if digest.hexdigest().upper() != metadata["sha256"].upper():
        raise ValueError(f"{archive.name}: decompressed SHA-256 mismatch")

    return {
        "dataset": f"NVD {year}",
        "records": "verified by official metadata",
        "sha256": file_sha256(archive),
    }


def validate_cwe() -> dict[str, object]:
    path = RAW / "cwe" / "cwec_v4.20.xml.zip"
    with ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"{path.name}: corrupt member {bad_member}")
        xml_members = [name for name in archive.namelist() if name.endswith(".xml")]
        if len(xml_members) != 1:
            raise ValueError(f"{path.name}: expected one XML member, found {xml_members}")
        with archive.open(xml_members[0]) as stream:
            root = ElementTree.parse(stream).getroot()
        weaknesses = sum(
            element.tag.rsplit("}", maxsplit=1)[-1] == "Weakness"
            for element in root.iter()
        )
    return {
        "dataset": "CWE 4.20",
        "records": weaknesses,
        "sha256": file_sha256(path),
    }


def validate_capec() -> dict[str, object]:
    path = RAW / "capec" / "capec_v3.9.xml"
    root = ElementTree.parse(path).getroot()
    namespace = root.tag[: -len("Attack_Pattern_Catalog")]
    patterns = root.findall(
        f"{namespace}Attack_Patterns/{namespace}Attack_Pattern"
    )
    active_patterns = sum(
        pattern.get("Status") != "Deprecated"
        for pattern in patterns
    )
    if not patterns or active_patterns == 0:
        raise ValueError(f"{path.name}: unexpected XML structure")
    return {
        "dataset": "CAPEC 3.9",
        "records": active_patterns,
        "sha256": file_sha256(path),
    }


def validate_attack() -> dict[str, object]:
    path = RAW / "attack" / "enterprise-attack-20.0.json"
    with path.open(encoding="utf-8") as stream:
        bundle = json.load(stream)
    if bundle.get("type") != "bundle" or not bundle.get("objects"):
        raise ValueError(f"{path.name}: expected a non-empty STIX bundle")
    return {
        "dataset": "ATT&CK Enterprise 20.0",
        "records": len(bundle["objects"]),
        "sha256": file_sha256(path),
    }


def validate_kev() -> dict[str, object]:
    path = RAW / "cisa_kev" / "known_exploited_vulnerabilities_2026-10-20.json"
    with path.open(encoding="utf-8") as stream:
        catalog = json.load(stream)
    vulnerabilities = catalog.get("vulnerabilities", [])
    if not vulnerabilities:
        raise ValueError(f"{path.name}: no vulnerabilities found")
    return {
        "dataset": f"CISA KEV {catalog.get('dateReleased', 'snapshot')}",
        "records": len(vulnerabilities),
        "sha256": file_sha256(path),
    }


def main() -> None:
    results = [
        *(validate_nvd(year) for year in (2024, 2025, 2026)),
        validate_cwe(),
        validate_capec(),
        validate_attack(),
        validate_kev(),
    ]
    for result in results:
        print(
            f"OK  {result['dataset']}: records={result['records']}, "
            f"file_sha256={result['sha256']}"
        )


if __name__ == "__main__":
    main()
