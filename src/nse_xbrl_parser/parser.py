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

    if not matching_schemas:
        raise FileNotFoundError(
            f"Schema '{schema_ref}' not found in the bundled taxonomy archive. "
            "The NSE may have published an unsupported taxonomy version."
        )

    # We will aggregate all facts across every matching schema definition
    parsed_data: Dict[str, Any] = {}

    # Track unique facts to avoid duplication across multiple schema evaluations
    # Key: (label, contextID, value)
    unique_facts = set()

    found_facts = False

    for target_schema_path in matching_schemas:
        target_schema_path = target_schema_path.absolute()

        # To support both absolute and relative resolution without violating read-only
        # package installations, we copy the XBRL XML into the SAME directory as the
        # located schema. This allows Arelle to resolve the schema and all its
        # relative dependencies (e.g. ../core/...) natively.
        temp_xml_path = target_schema_path.parent / f"_temp_{final_xbrl_path.name}"

        cntlr = None
        model_xbrl = None
        try:
            shutil.copy2(final_xbrl_path, temp_xml_path)

            # Initialize Arelle Controller (silent mode)
            cntlr = Cntlr.Cntlr(logFileName="logToBuffer")
            cntlr.modelManager.validate = True

            # Load and validate the local instance
            model_xbrl = cntlr.modelManager.load(str(temp_xml_path))

            if model_xbrl is None or len(model_xbrl.facts) == 0:
                logger.debug(f"Arelle loaded model for {target_schema_path} but found 0 facts.")
                continue

            found_facts = True
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

                val = fact.value
                context_id = fact.contextID if hasattr(fact, "contextID") else None

                fact_key = (label, context_id, val)

                if fact_key not in unique_facts:
                    unique_facts.add(fact_key)

                    if label in parsed_data:
                        existing = parsed_data[label]
                        if isinstance(existing, list):
                            existing.append(val)
                        else:
                            parsed_data[label] = [existing, val]
                    else:
                        parsed_data[label] = val

        except Exception as e:
            logger.debug(f"Validation failed for schema {target_schema_path}: {e}")

        finally:
            # Cleanup the temporary copy in the taxonomy directory
            if temp_xml_path.exists():
                temp_xml_path.unlink()

            if model_xbrl is not None:
                model_xbrl.close()
            if cntlr is not None:
                cntlr.close()

    if not found_facts:
        raise ValueError("Arelle loaded model but found 0 facts. Schema resolution or validation failed.")

    # Extreme Fallback: NSE schemas often contain un-taxonomized or misspelled items
    # (e.g. 'CategoryOfAllotees', 'PercentageOfTotalIssueSize') that Arelle explicitly
    # drops entirely across all taxonomy versions. We will use a fast raw XML sweep
    # to rescue these fields.
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(final_xbrl_path)
        root = tree.getroot()

        # Track what Arelle successfully pulled so we don't duplicate its work
        arelle_keys = set([k.lower().replace(" ", "") for k in parsed_data.keys()])

        # Track raw fallback uniqueness via context and label to safely build arrays
        unique_fallback_facts = set()

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
                human_lbl = ""
                for i, char in enumerate(tag):
                    if i > 0 and char.isupper() and tag[i-1].islower():
                        human_lbl += " " + char
                    else:
                        human_lbl += char
                human_lbl = human_lbl.capitalize()

                # If Arelle already mapped this property, trust Arelle's validation over our raw sweep
                if human_lbl.lower().replace(" ", "") in arelle_keys:
                    continue

                # We need to distinguish duplicates within the fallback itself (like arrays of CategoryOfAllotees).
                # We can use the element's contextRef attribute.
                ctx_ref = elem.attrib.get("contextRef")
                if ctx_ref:
                    fact_key = (human_lbl, ctx_ref, text)
                    if fact_key in unique_fallback_facts:
                        continue
                    unique_fallback_facts.add(fact_key)

                if human_lbl not in parsed_data:
                    parsed_data[human_lbl] = text
                else:
                    existing = parsed_data[human_lbl]
                    if isinstance(existing, list):
                        existing.append(text)
                    else:
                        parsed_data[human_lbl] = [existing, text]
    except Exception as e:
        logger.debug(f"Raw XML fallback extraction failed: {e}")

    return parsed_data
