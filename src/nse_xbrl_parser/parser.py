import logging
import re
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

# Arelle initialization requires setting the plugin dir before import if needed
from arelle import Cntlr

logger = logging.getLogger(__name__)

# The directory containing all historically assembled NSE taxonomies
GOLDEN_TAXONOMY_DIR = Path(__file__).parent / "golden_taxonomy_v1"

def _find_schema_ref(xbrl_content: bytes) -> Optional[str]:
    """Find the schemaRef href inside the raw XBRL instance bytes."""
    try:
        import xml.etree.ElementTree as ET
        from io import BytesIO

        tree = ET.parse(BytesIO(xbrl_content))
        root = tree.getroot()

        for elem in root.iter():
            if elem.tag.endswith("schemaRef"):
                for attr_key, attr_val in elem.attrib.items():
                    if attr_key.endswith("href") or attr_key == "href":
                        return attr_val
    except Exception as e:
        logger.debug(f"XML parsing for schemaRef failed: {e}. Falling back to regex.")
        try:
            content_str = xbrl_content.decode("utf-8", errors="ignore")
            match = re.search(r'schemaRef[^>]*href=["\']([^"\']+)["\']', content_str)
            if match:
                return match.group(1)
        except Exception:
            pass
    return None

def parse_xbrl_file(xml_path: Path | str) -> Dict[str, Any]:
    """Parse an NSE XBRL XML file and return human-readable JSON facts.
    
    This uses a dynamic absolute path rewriting strategy to force Arelle
    to resolve schemas against the bundled golden_taxonomy_v1 archive,
    without requiring massive disk copy operations.
    """
    final_xbrl_path = Path(xml_path).absolute()
    if not final_xbrl_path.exists():
        raise FileNotFoundError(f"XBRL file not found: {final_xbrl_path}")

    # Read the content to find the required schema
    with open(final_xbrl_path, "rb") as f:
        file_content = f.read()

    schema_ref = _find_schema_ref(file_content)
    if not schema_ref:
        raise ValueError("Could not detect schemaRef in the provided XBRL file.")

    logger.debug(f"Detected schemaRef: {schema_ref}")

    # Search for this exact schema inside our golden taxonomy
    matching_schemas = list(GOLDEN_TAXONOMY_DIR.rglob(schema_ref))
    if not matching_schemas:
        raise FileNotFoundError(
            f"Schema '{schema_ref}' not found in the golden taxonomy archive. "
            "The NSE might have published a new taxonomy version."
        )

    # Use the first match
    target_schema_path = matching_schemas[0].absolute()
    logger.debug(f"Resolved schema locally to: {target_schema_path}")

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        
        # In order for Arelle to reliably resolve all relative imports embedded inside 
        # the NSE schemas, the XML instance file MUST exist as a sibling to the 
        # root entry-point schema.
        # So we write a temporary copy of our target schema's directory tree explicitly 
        # linked to our XML file.
        # Wait - instead of copying the heavy taxonomy to the temporary file, we can
        # securely copy the lightweight XML file into the permanent golden taxonomy tree temporarily!
        temp_xml_in_golden = target_schema_path.parent / f"_temp_instance_{os.urandom(4).hex()}.xml"
        
        try:
            # Drop the tiny XML filing right next to its schema deep in the golden vault
            shutil.copy(final_xbrl_path, temp_xml_in_golden)

            # Initialize Arelle
            cntlr = Cntlr.Cntlr(logFileName="logToBuffer")
            cntlr.modelManager.validate = True

            # Process the instance
            model_xbrl = cntlr.modelManager.load(str(temp_xml_in_golden))

            if model_xbrl is None or len(model_xbrl.facts) == 0:
                raise ValueError("Arelle loaded model but found 0 facts. Schema validation may have failed.")

            parsed_data = {}
            for fact in model_xbrl.facts:
                label = str(fact.qname)

                if fact.concept is not None:
                    lbl = fact.concept.label(lang="en")
                    if not lbl:
                        lbl = fact.concept.label(
                            lang="en",
                            labelrole="http://www.xbrl.org/2003/role/verboseLabel",
                        )
                    if lbl:
                        label = lbl

                parsed_data[label] = fact.value

            return parsed_data

        finally:
            # Clean up the controller
            if 'cntlr' in locals():
                if 'model_xbrl' in locals() and model_xbrl:
                    model_xbrl.close()
                cntlr.close()
            
            # Clean up the injected XML from the golden taxonomy directory
            if temp_xml_in_golden.exists():
                os.remove(temp_xml_in_golden)

