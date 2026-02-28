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
