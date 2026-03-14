import pytest
from nse_xbrl_parser import parse_xbrl_file

def test_parse_xbrl_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_xbrl_file("does_not_exist.xml")

def test_parse_xbrl_file_invalid_schema_ref(tmp_path):
    # Create a dummy XML with no schemaRef
    dummy_xml = tmp_path / "dummy.xml"
    dummy_xml.write_text("<xbrl></xbrl>")
    
    with pytest.raises(ValueError, match="Could not detect schemaRef"):
        parse_xbrl_file(dummy_xml)

def test_parse_xbrl_file_unsupported_schema(tmp_path):
    # XML with a fake schemaRef
    dummy_xml = tmp_path / "dummy.xml"
    dummy_xml.write_text('<xbrl><link:schemaRef href="fake-schema-2099-01-01.xsd"/></xbrl>')
    
    with pytest.raises(FileNotFoundError, match="found in the bundled taxonomy archive"):
        parse_xbrl_file(dummy_xml)

def test_parse_xbrl_file_with_archive_scoped_fraud_taxonomy(tmp_path):
    filing = tmp_path / "fraud_case.xml"
    filing.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:in-capmkt="https://www.sebi.gov.in/xbrl/2024-02-29/in-capmkt" xmlns:in-capmkt-ent="https://www.sebi.gov.in/xbrl/Announcement_For_Fraud_Or_Default/2024-02-29/in-capmkt/in-capmkt-ent" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xbrli="http://www.xbrl.org/2003/instance">
  <link:schemaRef xlink:type="simple" xlink:href="in-capmkt-ent-2024-02-29.xsd"/>
  <xbrli:context id="MainI">
    <xbrli:entity>
      <xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">543386</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2026-03-02</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <in-capmkt:NameOfTheCompany contextRef="MainI">Fino Payments Bank Limited</in-capmkt:NameOfTheCompany>
  <in-capmkt:NSESymbol contextRef="MainI">FINOPB</in-capmkt:NSESymbol>
</xbrli:xbrl>
""",
        encoding="utf-8",
    )

    facts = parse_xbrl_file(filing)

    assert facts["Name of the company"] == "Fino Payments Bank Limited"
    assert facts.get("NSE symbol", facts.get("NSE Symbol", facts.get("Nsesymbol"))) == "FINOPB"
