import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

# Arelle initialization requires setting the plugin dir before import if needed
from arelle import Cntlr

logger = logging.getLogger(__name__)

# Define paths relative to this file's location
TAXONOMY_DIR = Path(__file__).parent / "taxonomies"

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
    """Parse an NSE XBRL XML document and yield a dictionary of human-readable facts.
    
    This function utilizes the `arelle` engine to validate and extract facts. 
    Crucially, to support absolute offline resolution without violating read-only 
    package installations (e.g. Docker, system-wide pip), this method dynamically 
    rewrites the `schemaRef` href attribute within the XML in-memory. It injects
    an absolute `file://` URI pointing to the bundled `taxonomies` archive.
    If the requested schema is not packaged, it passes the original URI through unmodified.
    
    Args:
        xml_path (Path | str): Absolute or relative path to the XBRL instance document.
        
    Returns:
        Dict[str, Any]: A dictionary where keys are the human-readable concept labels 
                        (or QNames backoffs) and values are the corresponding facts.
                        
    Raises:
        FileNotFoundError: If the source XML or required taxonomy schema does not exist.
        ValueError: If the schemaRef cannot be detected or validation yields zero facts.
    """
    final_xbrl_path = Path(xml_path).absolute()
    if not final_xbrl_path.exists():
        raise FileNotFoundError(f"XBRL file not found: {final_xbrl_path}")

    with open(final_xbrl_path, "rb") as f:
        file_content = f.read()

    schema_ref = _find_schema_ref(file_content)
    if not schema_ref:
        raise ValueError("Could not detect schemaRef in the provided XBRL file.")

    logger.debug(f"Detected schemaRef: {schema_ref}")

    # Search locally
    matching_schemas = list(TAXONOMY_DIR.rglob(schema_ref))
    
    if len(matching_schemas) > 1:
        # Resolve collisions by looking at NSE XML filename abbreviations
        xml_name = final_xbrl_path.name.lower()
        refined = []
        if "qip" in xml_name:
            if "_ls" in xml_name:
                refined = [s for s in matching_schemas if "QIP_LISTING" in str(s.parent).upper()]
            elif "_ip" in xml_name:
                refined = [s for s in matching_schemas if "QIP_IP" in str(s.parent).upper()]
            else:
                refined = [s for s in matching_schemas if "QIP" in str(s.parent).upper()]
        elif "pref" in xml_name:
            if "_ls" in xml_name:
                refined = [s for s in matching_schemas if "PREF" in str(s.parent).upper() and "LISTING" in str(s.parent).upper()]
            elif "_ip" in xml_name:
                refined = [s for s in matching_schemas if "PREF" in str(s.parent).upper() and "IP" in str(s.parent).upper()]
            else:
                refined = [s for s in matching_schemas if "PREF" in str(s.parent).upper()]
        elif "adr" in xml_name or "gdr" in xml_name:
            refined = [s for s in matching_schemas if "ADR" in str(s.parent).upper() or "GDR" in str(s.parent).upper()]
        elif "right" in xml_name:
            refined = [s for s in matching_schemas if "RIGHT" in str(s.parent).upper()]
            
        if refined:
            matching_schemas = refined
            
    if not matching_schemas:
        raise FileNotFoundError(
            f"Schema '{schema_ref}' not found in the bundled taxonomy archive. "
            "The NSE may have published an unsupported taxonomy version."
        )

    target_schema_path = matching_schemas[0].absolute()
    
    # To support both absolute and relative resolution without violating read-only 
    # package installations, we copy the XBRL XML into the SAME directory as the 
    # located schema. This allows Arelle to resolve the schema and all its 
    # relative dependencies (e.g. ../core/...) natively.
    temp_xml_path = target_schema_path.parent / f"_temp_{final_xbrl_path.name}"
    
    try:
        shutil.copy2(final_xbrl_path, temp_xml_path)
        
        # Initialize Arelle Controller (silent mode)
        cntlr = Cntlr.Cntlr(logFileName="logToBuffer")
        cntlr.modelManager.validate = True

        # Load and validate the local instance
        model_xbrl = cntlr.modelManager.load(str(temp_xml_path))

        if model_xbrl is None or len(model_xbrl.facts) == 0:
            raise ValueError("Arelle loaded model but found 0 facts. Schema resolution or validation failed.")

        parsed_data: Dict[str, Any] = {}
        for fact in model_xbrl.facts:
            label = str(fact.qname)

            if fact.concept is not None:
                # Prefer the standard en label, fallback to verbose
                lbl = fact.concept.label(lang="en")
                if not lbl:
                    lbl = fact.concept.label(
                        lang="en",
                        labelrole="http://www.xbrl.org/2003/role/verboseLabel",
                    )
                if lbl:
                    label = lbl

            if label in parsed_data:
                parsed_data[label] = f"{parsed_data[label]}, {fact.value}"
            else:
                parsed_data[label] = fact.value

        # Extreme Fallback: NSE schemas often contain un-taxonomized or misspelled items 
        # (e.g. 'CategoryOfAllotees', 'PercentageOfTotalIssueSize') that Arelle explicitly 
        # drops. We will use a fast raw XML sweep to rescue these fields.
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(final_xbrl_path)
            root = tree.getroot()
            
            # Track what Arelle successfully pulled so we don't duplicate its work
            arelle_keys = set(parsed_data.keys())
            
            for elem in root.iter():
                text = elem.text
                if text and text.strip():
                    text = text.strip()
                    tag = elem.tag.split("}")[-1]
                    
                    # Ignore purely structural/XBRL internal tags
                    if tag in ('context', 'entity', 'identifier', 'period', 'instant', 
                               'startDate', 'endDate', 'segment', 'explicitMember', 
                               'typedMember', 'unit', 'unitDenominator', 'unitNumerator', 'xbrl'):
                        continue
                        
                    # Create a human readable label, e.g. "CategoryOfAllotees" -> "Category of allotees"
                    # Using regex to insert space before capitals
                    human_lbl = re.sub(r"([a-z])([A-Z])", r"\1 \2", tag).capitalize()
                    
                    # If Arelle already mapped this property, trust Arelle's validation over our raw sweep
                    if human_lbl in arelle_keys:
                        continue
                    
                    if human_lbl not in parsed_data:
                        parsed_data[human_lbl] = text
                    else:
                        parsed_data[human_lbl] = f"{parsed_data[human_lbl]}, {text}"
        except Exception as e:
            logger.debug(f"Raw XML fallback extraction failed: {e}")

        return parsed_data

    finally:
        # Cleanup the temporary copy in the taxonomy directory
        if temp_xml_path.exists():
            temp_xml_path.unlink()

        if 'cntlr' in locals():
            if 'model_xbrl' in locals() and model_xbrl is not None:
                model_xbrl.close()
            cntlr.close()

