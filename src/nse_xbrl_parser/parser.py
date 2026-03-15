import logging
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

# Arelle initialization requires setting the plugin dir before import if needed
from arelle import Cntlr

from .taxonomy_store import (
    TAXONOMY_DIR,
    collect_flat_schema_candidates,
    collect_versioned_schema_candidates,
)

logger = logging.getLogger(__name__)


def _read_target_namespace(schema_path: Path) -> Optional[str]:
    """Read a schema file's targetNamespace without loading Arelle."""
    try:
        import xml.etree.ElementTree as ET

        root = ET.parse(schema_path).getroot()
        return root.attrib.get("targetNamespace")
    except Exception as e:
        logger.debug(f"Unable to read targetNamespace from {schema_path}: {e}")
        return None


def _schema_has_matching_local_imports(schema_path: Path) -> bool:
    """Check whether a candidate schema's relative local imports match their declared namespaces."""
    try:
        import xml.etree.ElementTree as ET

        root = ET.parse(schema_path).getroot()
        has_local_import = False

        for elem in root.iter():
            if not elem.tag.endswith("import"):
                continue

            namespace = elem.attrib.get("namespace")
            schema_location = elem.attrib.get("schemaLocation")
            if not namespace or not schema_location or "://" in schema_location:
                continue

            imported_path = (schema_path.parent / schema_location).resolve()
            if not imported_path.exists():
                return False

            has_local_import = True
            imported_namespace = _read_target_namespace(imported_path)
            if imported_namespace != namespace:
                return False

        return has_local_import
    except Exception as e:
        logger.debug(f"Unable to inspect local imports for {schema_path}: {e}")
        return False

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

def _get_instance_namespaces(xbrl_content: bytes) -> set[str]:
    """Extract all unique namespaces from the XBRL instance document."""
    namespaces = set()
    try:
        import xml.etree.ElementTree as ET
        from io import BytesIO

        # We need to capture all namespace declarations
        # iterparse with "start-ns" is perfect for this
        for event, (prefix, uri) in ET.iterparse(BytesIO(xbrl_content), events=["start-ns"]):
            namespaces.add(uri)
    except Exception as e:
        logger.debug(f"Namespace extraction failed: {e}. Falling back to regex.")
        try:
            content_str = xbrl_content.decode("utf-8", errors="ignore")
            # Simple regex to find xmlns:prefix="uri" or xmlns="uri"
            matches = re.findall(r'xmlns(?::\w+)?=["\']([^"\']+)["\']', content_str)
            for m in matches:
                namespaces.add(m)
        except Exception:
            pass
    return namespaces

def parse_xbrl_file(xml_path: Path | str) -> Dict[str, Any]:
    """Parse an NSE XBRL XML document and yield a dictionary of human-readable facts.

    This function utilizes the `arelle` engine to validate and extract facts.
    It searches bundled versioned taxonomy releases first, falls back to the
    current flat taxonomy tree when necessary, and then copies the instance XML
    into the selected schema directory so Arelle can resolve relative imports locally.

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

    instance_namespaces = _get_instance_namespaces(file_content)
    logger.debug(f"Detected instance namespaces: {instance_namespaces}")

    # Search versioned releases first, then fall back to the flat taxonomy tree.
    matching_schemas = collect_versioned_schema_candidates(schema_ref)
    if not matching_schemas:
        matching_schemas = collect_flat_schema_candidates(schema_ref, TAXONOMY_DIR)

    if not matching_schemas:
        raise FileNotFoundError(
            f"Schema '{schema_ref}' not found in the bundled taxonomy archive. "
            "The NSE may have published an unsupported taxonomy version."
        )

    # Disambiguation based on namespaces to avoid expensive multiple Arelle evaluations
    if len(matching_schemas) > 1:
        from .taxonomy_store import load_index
        index = load_index()
        
        target_namespace_matches = []
        imported_namespace_matches = []
        
        for schema_path in matching_schemas:
            # Find the release this schema belongs to
            # A versioned schema path is like .../family/release_id/schema_ref
            # or .../family/release_id/subfolder/schema_ref
            try:
                rel_parts = schema_path.relative_to(TAXONOMY_DIR).parts
                if len(rel_parts) >= 2:
                    family = rel_parts[0]
                    release_id = rel_parts[1]
                    
                    for release in index.get("releases", []):
                        if release["family"] == family and release["release_id"] == release_id:
                            # Primary match: target namespaces
                            if any(ns in instance_namespaces for ns in release.get("target_namespaces", [])):
                                target_namespace_matches.append(schema_path)
                                break
                            # Secondary match: imported namespaces
                            if any(ns in instance_namespaces for ns in release.get("imported_core_namespaces", [])):
                                imported_namespace_matches.append(schema_path)
                                break
            except ValueError:
                # Not in TAXONOMY_DIR (maybe it's a flat schema candidate)
                continue
        
        if target_namespace_matches:
            logger.debug(f"Filtered {len(matching_schemas)} schemas down to {len(target_namespace_matches)} based on target_namespaces.")
            matching_schemas = target_namespace_matches
        elif imported_namespace_matches:
            logger.debug(f"Filtered {len(matching_schemas)} schemas down to {len(imported_namespace_matches)} based on imported_core_namespaces.")
            matching_schemas = imported_namespace_matches

    compatible_schemas = [path for path in matching_schemas if _schema_has_matching_local_imports(path)]
    if compatible_schemas:
        matching_schemas = compatible_schemas

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

    return parsed_data
