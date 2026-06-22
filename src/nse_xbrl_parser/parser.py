import logging
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

# Arelle session management
from arelle.api.Session import Session
from arelle.RuntimeOptions import RuntimeOptions

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
        for _event, (_prefix, uri) in ET.iterparse(BytesIO(xbrl_content), events=["start-ns"]):
            namespaces.add(uri)
    except Exception as e:
        logger.debug(f"Namespace extraction failed: {e}. Falling back to regex.")
        try:
            content_str = xbrl_content.decode("utf-8", errors="ignore")
            # Simple regex to find xmlns:prefix="uri" or xmlns="uri"
            matches = re.findall(r'xmlns(?::\w+)?=["\']([^"\']+)["\']', content_str)
            for match in matches:
                namespaces.add(match)
        except Exception:
            pass
    return namespaces


def _resolve_schema_candidates(xml_path: Path | str) -> tuple[Path, list[Path]]:
    """Resolve candidate local entrypoint schemas for an instance file."""
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
                        if (
                            release["family"] == family
                            and release["release_id"] == release_id
                        ):
                            # Primary match: target namespaces
                            if any(
                                ns in instance_namespaces
                                for ns in release.get("target_namespaces", [])
                            ):
                                target_namespace_matches.append(schema_path)
                                break
                            # Secondary match: imported namespaces
                            if any(
                                ns in instance_namespaces
                                for ns in release.get("imported_core_namespaces", [])
                            ):
                                imported_namespace_matches.append(schema_path)
                                break
            except ValueError:
                # Not in TAXONOMY_DIR (maybe it's a flat schema candidate)
                continue

        if target_namespace_matches:
            logger.debug(
                "Filtered %s schemas down to %s based on target_namespaces.",
                len(matching_schemas),
                len(target_namespace_matches),
            )
            matching_schemas = target_namespace_matches
        elif imported_namespace_matches:
            logger.debug(
                "Filtered %s schemas down to %s based on imported_core_namespaces.",
                len(matching_schemas),
                len(imported_namespace_matches),
            )
            matching_schemas = imported_namespace_matches

    compatible_schemas = [
        path for path in matching_schemas if _schema_has_matching_local_imports(path)
    ]
    if compatible_schemas:
        matching_schemas = compatible_schemas

    return final_xbrl_path, matching_schemas


def _iter_loaded_models(
    final_xbrl_path: Path, matching_schemas: list[Path]
) -> Iterator[Any]:
    """Yield successfully loaded Arelle models for the provided schema candidates."""
    with Session() as session:
        for target_schema_path in matching_schemas:
            target_schema_path = target_schema_path.absolute()

            # To support both absolute and relative resolution without violating read-only
            # package installations, we copy the XBRL XML into the SAME directory as the
            # located schema. This allows Arelle to resolve the schema and all its
            # relative dependencies (e.g. ../core/...) natively.
            temp_xml_path = target_schema_path.parent / f"_temp_{final_xbrl_path.name}"

            try:
                shutil.copy2(final_xbrl_path, temp_xml_path)

                options = RuntimeOptions(
                    entrypointFile=str(temp_xml_path),
                    logFile="logToBuffer",
                    keepOpen=True,
                    validate=True,
                )

                session.run(options)
                models = session.get_models()
                model_xbrl = models[-1] if models else None

                if model_xbrl is None or len(model_xbrl.facts) == 0:
                    try:
                        arelle_logs = session.get_logs("text")
                        logger.error(
                            "Arelle loaded model for %s but found 0 facts. Logs: %s",
                            target_schema_path,
                            arelle_logs,
                        )
                    except Exception:
                        logger.error(
                            "Arelle loaded model for %s but found 0 facts.",
                            target_schema_path,
                        )
                    continue

                yield model_xbrl

            except Exception as e:
                logger.debug(f"Validation failed for schema {target_schema_path}: {e}")

            finally:
                # Cleanup the temporary copy in the taxonomy directory
                if temp_xml_path.exists():
                    temp_xml_path.unlink()


def _normalize_atomic_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _extract_period(context: Any) -> Dict[str, Any]:
    if context is None:
        return {}

    if getattr(context, "isInstantPeriod", False):
        instant_value = (
            getattr(context, "instantDate", None)
            or getattr(context, "instantDatetime", None)
            or getattr(context, "instantValue", None)
        )
        return {"instant": _normalize_atomic_value(instant_value)}

    if getattr(context, "isStartEndPeriod", False):
        start_value = (
            getattr(context, "startDate", None)
            or getattr(context, "startDatetime", None)
            or getattr(context, "startValue", None)
        )
        end_value = (
            getattr(context, "endDate", None)
            or getattr(context, "endDatetime", None)
            or getattr(context, "endValue", None)
        )
        return {
            "start": _normalize_atomic_value(start_value),
            "end": _normalize_atomic_value(end_value),
        }

    if getattr(context, "isForeverPeriod", False):
        return {"forever": True}

    return {}


def _extract_dimension_member(dimension_value: Any) -> str:
    if dimension_value is None:
        return ""

    if getattr(dimension_value, "isExplicit", False):
        member_qname = getattr(dimension_value, "memberQname", None)
        if member_qname is not None:
            return str(member_qname)

    typed_member = getattr(dimension_value, "typedMember", None)
    if typed_member is not None:
        try:
            if hasattr(typed_member, "itertext"):
                text_parts = [part.strip() for part in typed_member.itertext() if part.strip()]
                if text_parts:
                    return " ".join(text_parts)
        except Exception:
            pass
        return str(typed_member)

    member_qname = getattr(dimension_value, "memberQname", None)
    if member_qname is not None:
        return str(member_qname)

    return str(dimension_value)


def _dimension_axis_key(axis_candidate: Any, dimension_value: Any) -> str:
    axis_qname = getattr(axis_candidate, "qname", None)
    if axis_qname is not None:
        return str(axis_qname)

    dim_qname = getattr(dimension_value, "dimensionQname", None)
    if dim_qname is not None:
        return str(dim_qname)

    return str(axis_candidate)


def _extract_dimensions(context: Any) -> Dict[str, str]:
    if context is None:
        return {}

    dimensions: Dict[str, str] = {}
    qname_dims = getattr(context, "qnameDims", None)

    if isinstance(qname_dims, dict):
        for axis_qname in sorted(qname_dims.keys(), key=lambda item: str(item)):
            dimensions[str(axis_qname)] = _extract_dimension_member(qname_dims[axis_qname])

    for dim_attr in ("segDimValues", "scenDimValues"):
        dim_values = getattr(context, dim_attr, None)
        if isinstance(dim_values, dict):
            for axis_candidate in sorted(dim_values.keys(), key=lambda item: str(item)):
                dimension_value = dim_values[axis_candidate]
                axis_key = _dimension_axis_key(axis_candidate, dimension_value)
                dimensions.setdefault(axis_key, _extract_dimension_member(dimension_value))

    return dimensions


def _extract_unit(fact: Any) -> Optional[str]:
    unit = getattr(fact, "unit", None)
    if unit is None:
        unit_id = getattr(fact, "unitID", None)
        return str(unit_id) if unit_id else None

    measures = getattr(unit, "measures", None)
    if isinstance(measures, (tuple, list)) and len(measures) == 2:
        numerators, denominators = measures
        numerator_str = "*".join(sorted(str(item) for item in numerators))
        denominator_str = "*".join(sorted(str(item) for item in denominators))
        if denominator_str:
            return f"{numerator_str}/{denominator_str}" if numerator_str else f"1/{denominator_str}"
        if numerator_str:
            return numerator_str

    unit_id = getattr(fact, "unitID", None) or getattr(unit, "id", None)
    if unit_id:
        return str(unit_id)

    return str(unit)


def _extract_entity(context: Any) -> Optional[Dict[str, Optional[str]]]:
    if context is None:
        return None

    entity_identifier = getattr(context, "entityIdentifier", None)
    if isinstance(entity_identifier, tuple) and len(entity_identifier) >= 2:
        scheme, identifier = entity_identifier[0], entity_identifier[1]
        return {
            "scheme": str(scheme) if scheme is not None else None,
            "identifier": str(identifier) if identifier is not None else None,
        }

    return None


def _infer_basis(context_id: Optional[str], dimensions: Dict[str, str]) -> Optional[str]:
    for axis, member in dimensions.items():
        axis_lower = axis.lower()
        member_lower = member.lower()

        if "consolidated" in member_lower or "consolidated" in axis_lower:
            return "consolidated"
        if "standalone" in member_lower or "standalone" in axis_lower:
            return "standalone"
        if "basis" in axis_lower:
            return member

    if context_id:
        context_lower = context_id.lower()
        if "consolidated" in context_lower:
            return "consolidated"
        if "standalone" in context_lower:
            return "standalone"

    return None


def _fact_to_row(fact: Any) -> dict[str, Any]:
    fact_qname = getattr(fact, "qname", None)
    concept = {
        "qname": str(fact_qname) if fact_qname is not None else None,
        "local_name": getattr(fact_qname, "localName", None),
        "namespace": getattr(fact_qname, "namespaceURI", None),
    }

    context = getattr(fact, "context", None)
    context_id = getattr(fact, "contextID", None) or getattr(context, "id", None)
    dimensions = _extract_dimensions(context)

    is_nil = bool(getattr(fact, "isNil", False))
    is_tuple = bool(getattr(fact, "isTuple", False))

    value: Any
    if is_nil:
        value = None
    else:
        x_value = getattr(fact, "xValue", None)
        value = _normalize_atomic_value(x_value)
        if value is None:
            value = _normalize_atomic_value(getattr(fact, "value", None))

    return {
        "concept": concept,
        "value": value,
        "unit": _extract_unit(fact),
        "decimals": getattr(fact, "decimals", None),
        "period": _extract_period(context),
        "context_id": context_id,
        "dimensions": dimensions,
        "basis": _infer_basis(context_id, dimensions),
        "entity": _extract_entity(context),
        "is_nil": is_nil,
        "is_tuple": is_tuple,
    }


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
    final_xbrl_path, matching_schemas = _resolve_schema_candidates(xml_path)

    # We will aggregate all facts across every matching schema definition
    parsed_data: Dict[str, Any] = {}

    # Track unique facts to avoid duplication across multiple schema evaluations
    # Key: (label, contextID, value)
    unique_facts = set()

    found_facts = False

    for model_xbrl in _iter_loaded_models(final_xbrl_path, matching_schemas):
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

    if not found_facts:
        raise ValueError(
            "Arelle loaded model but found 0 facts. Schema resolution or validation failed."
        )

    return parsed_data


def parse_xbrl_facts(xml_path: Path | str) -> list[dict[str, Any]]:
    """Parse an NSE XBRL XML document and return a context-preserving fact table.

    Each row preserves context-level detail for one fact, including period,
    dimensions, and entity metadata.
    """
    final_xbrl_path, matching_schemas = _resolve_schema_candidates(xml_path)

    rows: list[dict[str, Any]] = []
    unique_facts: set[tuple[Any, ...]] = set()
    found_facts = False

    for model_xbrl in _iter_loaded_models(final_xbrl_path, matching_schemas):
        found_facts = True
        for fact in model_xbrl.facts:
            fact_key = (
                str(getattr(fact, "qname", None)),
                getattr(fact, "contextID", None),
                getattr(fact, "value", None),
                getattr(fact, "unitID", None),
                getattr(fact, "decimals", None),
            )
            if fact_key in unique_facts:
                continue

            unique_facts.add(fact_key)
            rows.append(_fact_to_row(fact))

    if not found_facts:
        raise ValueError(
            "Arelle loaded model but found 0 facts. Schema resolution or validation failed."
        )

    return rows
