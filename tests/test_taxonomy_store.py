import json
from pathlib import Path

from nse_xbrl_parser.taxonomy_store import (
    collect_flat_schema_candidates,
    collect_versioned_schema_candidates,
    discover_release_units,
    install_release,
    release_is_self_contained,
)


def _write_qip_bundle(root: Path, company_name: str = "Demo Co") -> None:
    (root / "QIP_Listing").mkdir(parents=True, exist_ok=True)
    (root / "core").mkdir(parents=True, exist_ok=True)

    (root / "QIP_Listing" / "in-capmkt-ent-2022-06-30.xsd").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    targetNamespace="https://www.sebi.gov.in/xbrl/QIP_Listing/2022-06-30/in-capmkt/in-capmkt-ent">
  <xsd:import namespace="https://www.sebi.gov.in/xbrl/2022-06-30/in-capmkt" schemaLocation="../core/in-capmkt.xsd"/>
</xsd:schema>
""",
        encoding="utf-8",
    )
    (root / "core" / "in-capmkt.xsd").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    targetNamespace="https://www.sebi.gov.in/xbrl/2022-06-30/in-capmkt">
  <xsd:annotation><xsd:documentation>{company_name}</xsd:documentation></xsd:annotation>
</xsd:schema>
""",
        encoding="utf-8",
    )


def test_discover_release_units_builds_family_and_release_id(tmp_path):
    _write_qip_bundle(tmp_path)

    releases = discover_release_units(tmp_path)

    assert len(releases) == 1
    release = releases[0]
    assert release.family == "QIP_Listing"
    assert release.version == "2022-06-30"
    assert release.release_id.startswith("2022-06-30__")
    assert "QIP_Listing/in-capmkt-ent-2022-06-30.xsd" in release.entry_points
    assert "core/in-capmkt.xsd" in release.files


def test_install_release_skips_duplicate_content(tmp_path):
    source_a = tmp_path / "source_a"
    source_b = tmp_path / "source_b"
    taxonomy_root = tmp_path / "taxonomies"
    _write_qip_bundle(source_a)
    _write_qip_bundle(source_b)

    release_a = discover_release_units(source_a)[0]
    release_b = discover_release_units(source_b)[0]

    was_added_a, stored_a = install_release(release_a, destination_root=taxonomy_root, provenance_name="source_a")
    was_added_b, stored_b = install_release(release_b, destination_root=taxonomy_root, provenance_name="source_b")

    assert was_added_a is True
    assert was_added_b is False
    assert stored_a == stored_b

    index = json.loads((taxonomy_root / "index.json").read_text(encoding="utf-8"))
    assert len(index["releases"]) == 1
    assert index["releases"][0]["stored_path"].startswith("QIP_Listing/")


def test_install_release_writes_versioned_family_layout(tmp_path):
    source = tmp_path / "source"
    taxonomy_root = tmp_path / "taxonomies"
    _write_qip_bundle(source)

    release = discover_release_units(source)[0]
    was_added, stored_path = install_release(release, destination_root=taxonomy_root, provenance_name="source")

    assert was_added is True
    assert (stored_path / "QIP_Listing" / "in-capmkt-ent-2022-06-30.xsd").exists()
    assert (stored_path / "core" / "in-capmkt.xsd").exists()
    assert len(collect_versioned_schema_candidates("in-capmkt-ent-2022-06-30.xsd", taxonomy_root)) == 1
    assert len(collect_flat_schema_candidates("in-capmkt-ent-2022-06-30.xsd", taxonomy_root)) == 0


def test_release_is_self_contained_detects_missing_core(tmp_path):
    bundle = tmp_path / "bundle"
    _write_qip_bundle(bundle)
    (bundle / "core" / "in-capmkt.xsd").unlink()

    release = discover_release_units(bundle)[0]

    assert release_is_self_contained(release) is False
