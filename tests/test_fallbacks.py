import pytest
from unittest.mock import MagicMock

# We use a fixture to mock arelle if it's not available or to ensure it doesn't
# interfere with tests that might need the real arelle.
# However, since the parser imports arelle at the module level, we still need
# to handle the sys.modules trick if we want to run these tests in an environment
# without arelle installed.

@pytest.fixture(autouse=True)
def mock_arelle(monkeypatch):
    mock = MagicMock()
    monkeypatch.setitem(sys.modules, "arelle", mock)
    monkeypatch.setitem(sys.modules, "arelle.api.Session", MagicMock())
    monkeypatch.setitem(sys.modules, "arelle.RuntimeOptions", MagicMock())

import sys
# If arelle is not installed, we must mock it BEFORE importing the parser
if "arelle" not in sys.modules:
    sys.modules["arelle"] = MagicMock()
    sys.modules["arelle.api.Session"] = MagicMock()
    sys.modules["arelle.RuntimeOptions"] = MagicMock()

from nse_xbrl_parser.parser import _find_schema_ref, _get_instance_namespaces

def test_find_schema_ref_regex_fallback():
    # Valid XML should work (though here it's still using the ET path first)
    valid_xml = b'<?xml version="1.0"?><xbrl><link:schemaRef href="test.xsd" xmlns:link="http://www.xbrl.org/2003/linkbase"/></xbrl>'
    assert _find_schema_ref(valid_xml) == "test.xsd"

    # Malformed XML should trigger regex fallback
    malformed_xml = b'<<<<< malformed <link:schemaRef href="regex-test.xsd" />'
    assert _find_schema_ref(malformed_xml) == "regex-test.xsd"

    # Another malformed case with single quotes
    malformed_single_quotes = b'broken xml <schemaRef key="val" href=\'single-quote.xsd\'>'
    assert _find_schema_ref(malformed_single_quotes) == "single-quote.xsd"

    # No schemaRef should return None
    no_ref = b'broken xml without any ref'
    assert _find_schema_ref(no_ref) is None

def test_get_instance_namespaces_regex_fallback():
    # Valid XML
    valid_xml = b'<?xml version="1.0"?><xbrl xmlns:test="http://example.com/test" xmlns="http://example.com/default"></xbrl>'
    namespaces = _get_instance_namespaces(valid_xml)
    assert "http://example.com/test" in namespaces
    assert "http://example.com/default" in namespaces

    # Malformed XML should trigger regex fallback
    malformed_xml = b'<<<< broken xmlns:test="http://fallback.com/test" xmlns=\'http://fallback.com/default\''
    namespaces = _get_instance_namespaces(malformed_xml)
    assert "http://fallback.com/test" in namespaces
    assert "http://fallback.com/default" in namespaces

    # No namespaces
    no_ns = b'broken xml without namespaces'
    assert _get_instance_namespaces(no_ns) == set()
