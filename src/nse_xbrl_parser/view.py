"""Taxonomy-backed human views for NSE XBRL filings."""

from __future__ import annotations

from collections import Counter, OrderedDict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .parser import _fact_to_row, load_xbrl_model

PRESENTATION_ARCROLE = "http://www.xbrl.org/2003/arcrole/parent-child"
CALCULATION_ARCROLE = "http://www.xbrl.org/2003/arcrole/summation-item"
TOLERANCE = Decimal("1")

Fact = Mapping[str, Any]
Cell = dict[str, Any]
DimensionSignature = tuple[tuple[str, str], ...]
ColumnKey = tuple[str, str]
ViewCacheKey = tuple[str, int, int, bool, bool, bool]

_VIEW_CACHE_MAXSIZE = 32
_VIEW_CACHE: OrderedDict[ViewCacheKey, dict[str, Any]] = OrderedDict()


def build_xbrl_view(
    xml_path: Path | str,
    *,
    include_trace: bool = False,
    include_validations: bool = True,
    validate: bool = True,
) -> dict[str, Any]:
    """Build a taxonomy-backed, JSON-serializable human view for an XBRL filing.

    The public view keeps human-facing rows and columns in the default payload.
    DTS plumbing such as concept QNames, context IDs, decimals, dimensions, and
    linkbase diagnostics is attached only when ``include_trace`` is true.
    """

    cache_key = _view_cache_key(
        xml_path,
        include_trace=include_trace,
        include_validations=include_validations,
        validate=validate,
    )
    if cache_key is not None and cache_key in _VIEW_CACHE:
        _VIEW_CACHE.move_to_end(cache_key)
        return deepcopy(_VIEW_CACHE[cache_key])

    with load_xbrl_model(xml_path, validate=validate) as model_xbrl:
        facts = _facts_from_model(model_xbrl)
        cells = [_cell(index, fact) for index, fact in enumerate(facts)]
        columns = _columns_from_cells(cells)
        column_index = {column["key"]: index for index, column in enumerate(columns)}

        presentation = _extract_presentation(model_xbrl, facts)
        sections = _sections_from_presentation(
            presentation,
            cells,
            column_index,
            include_trace=include_trace,
        )
        if not sections:
            sections = _flat_fallback_sections(
                cells,
                column_index,
                include_trace=include_trace,
            )

        calculation = (
            _extract_calculation(model_xbrl, facts)
            if include_validations
            else _skipped_calculation()
        )

    view: dict[str, Any] = {
        "title": _view_title(presentation, sections),
        "unit": _dominant_unit(cells),
        "columns": [column["label"] for column in columns],
        "sections": sections,
        "checks": _checks_payload(calculation),
    }

    if not presentation.get("available"):
        view["presentation"] = {
            "available": False,
            "reason": presentation.get("reason") or "presentation linkbase unavailable",
        }

    if include_trace:
        view["trace"] = {
            "fact_count": len(facts),
            "columns": columns,
            "presentation": presentation,
            "calculation": calculation,
            "validate": validate,
        }
        if calculation.get("validations"):
            view["checks"]["validations"] = calculation["validations"]

    if cache_key is not None:
        _VIEW_CACHE[cache_key] = deepcopy(view)
        _VIEW_CACHE.move_to_end(cache_key)
        while len(_VIEW_CACHE) > _VIEW_CACHE_MAXSIZE:
            _VIEW_CACHE.popitem(last=False)

    return view


def render_xbrl_markdown(view: Mapping[str, Any]) -> str:
    """Render a ``build_xbrl_view`` dictionary as human-readable markdown."""

    lines: list[str] = []
    title = str(view.get("title") or "XBRL filing")
    lines.extend([f"# {_escape_markdown_text(title)}", ""])

    unit = view.get("unit")
    if unit:
        lines.extend([f"**Unit:** {_escape_markdown_text(str(unit))}", ""])

    columns = [str(column) for column in view.get("columns", [])]
    for section in view.get("sections", []) or []:
        heading = str(section.get("heading") or "Facts")
        lines.extend([f"## {_escape_markdown_text(heading)}", ""])
        rows = section.get("rows", []) or []
        if rows:
            _append_markdown_table(lines, rows, columns)
        else:
            lines.append("_No facts reported._")
        lines.append("")

    checks = view.get("checks") or {}
    if checks:
        summary = checks.get("summary") or checks.get("status")
        if summary:
            lines.extend(["## Checks", "", _escape_markdown_text(str(summary)), ""])

    return "\n".join(lines).rstrip() + "\n"


def _view_cache_key(
    xml_path: Path | str,
    *,
    include_trace: bool,
    include_validations: bool,
    validate: bool,
) -> ViewCacheKey | None:
    path = Path(xml_path).absolute()
    try:
        stat = path.stat()
    except OSError:
        return None
    return (
        str(path),
        stat.st_mtime_ns,
        stat.st_size,
        include_trace,
        include_validations,
        validate,
    )


def _facts_from_model(model_xbrl: Any) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    unique_facts: set[tuple[Any, ...]] = set()

    for fact in getattr(model_xbrl, "facts", []) or []:
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
        row = _fact_to_row(fact)
        if not row.get("is_nil") and getattr(fact, "value", None) is not None:
            row["value"] = getattr(fact, "value")
        row["label"] = _concept_label(getattr(fact, "concept", None)) or _local_name(row)
        facts.append(row)

    return facts


def _extract_presentation(model_xbrl: Any, facts: Sequence[Fact]) -> dict[str, Any]:
    relationship_set = model_xbrl.relationshipSet(PRESENTATION_ARCROLE)
    relationships = list(getattr(relationship_set, "modelRelationships", []) or [])
    if not relationships:
        return {
            "available": False,
            "reason": "no presentation relationships found",
            "roles": [],
        }

    fact_cells = _fact_cells_by_concept(facts)
    roles = []
    linkroles = sorted({str(getattr(rel, "linkrole", "")) for rel in relationships})

    for linkrole in linkroles:
        role_relationships = [
            rel for rel in relationships if str(getattr(rel, "linkrole", "")) == linkrole
        ]
        tree = _presentation_tree_for_role(role_relationships, fact_cells)
        if not tree:
            continue
        roles.append(
            {
                "role_uri": linkrole,
                "role_id": _role_id(linkrole),
                "label": _role_label(model_xbrl, linkrole),
                "relationship_count": len(role_relationships),
                "tree": tree,
            }
        )

    if not roles:
        return {
            "available": False,
            "reason": "presentation relationships did not match reported facts",
            "roles": [],
        }

    return {
        "available": True,
        "arcrole": PRESENTATION_ARCROLE,
        "role_count": len(roles),
        "roles": roles,
    }


def _presentation_tree_for_role(
    relationships: Sequence[Any], fact_cells: Mapping[str, list[Cell]]
) -> list[dict[str, Any]]:
    children_by_parent: dict[str, list[Any]] = {}
    from_objects: dict[str, Any] = {}
    to_keys: set[str] = set()

    for rel in relationships:
        parent = getattr(rel, "fromModelObject", None)
        child = getattr(rel, "toModelObject", None)
        parent_key = _concept_key(parent)
        child_key = _concept_key(child)
        if not parent_key or not child_key:
            continue
        children_by_parent.setdefault(parent_key, []).append(rel)
        from_objects[parent_key] = parent
        to_keys.add(child_key)

    root_keys = [key for key in from_objects if key not in to_keys]
    if not root_keys and relationships:
        root = getattr(relationships[0], "fromModelObject", None)
        root_key = _concept_key(root)
        root_keys = [root_key] if root_key else []

    def build(
        concept_obj: Any,
        incoming_rel: Any | None,
        path: tuple[str, ...],
    ) -> dict[str, Any] | None:
        concept = _concept_payload(concept_obj, incoming_rel)
        qname = concept.get("qname")
        local_name = concept.get("local_name")
        node_cells = list(fact_cells.get(str(qname), [])) if qname else []
        if not node_cells and local_name:
            node_cells = list(fact_cells.get(str(local_name), []))

        child_rels = sorted(
            children_by_parent.get(_concept_key(concept_obj), []),
            key=lambda rel: (
                _to_decimal(getattr(rel, "order", None)) or Decimal("0"),
                _concept_key(getattr(rel, "toModelObject", None)),
            ),
        )
        children = []
        for child_rel in child_rels:
            child_path = (*path, str(qname)) if qname else path
            child = build(getattr(child_rel, "toModelObject", None), child_rel, child_path)
            if child is not None:
                children.append(child)

        if not node_cells and not children:
            return None

        node_ref = {
            "role_uri": (
                str(getattr(incoming_rel, "linkrole", ""))
                if incoming_rel is not None
                else None
            ),
            "path": [part for part in path if part],
            "concept": qname,
            "local_name": local_name,
        }
        order = _to_decimal(getattr(incoming_rel, "order", None))
        return {
            **concept,
            "order": _decimal_to_str(order) if incoming_rel is not None else None,
            "preferred_label": str(getattr(incoming_rel, "preferredLabel", "") or "")
            or None,
            "node_ref": node_ref,
            "cells": node_cells,
            "children": children,
        }

    roots = []
    for root_key in sorted(root_keys):
        root_node = build(from_objects[root_key], None, ())
        if root_node is not None:
            roots.append(root_node)
    return roots


def _extract_calculation(model_xbrl: Any, facts: Sequence[Fact]) -> dict[str, Any]:
    relationship_set = model_xbrl.relationshipSet(CALCULATION_ARCROLE)
    relationships = list(getattr(relationship_set, "modelRelationships", []) or [])
    if not relationships:
        return {
            "available": False,
            "reason": "no calculation relationships found",
            "validations": [],
            "summary": {"pass": 0, "fail": 0, "missing": 0},
        }

    facts_by_concept_context = _fact_values_by_concept_context(facts)
    validations = []

    grouped: dict[tuple[str, str], list[Any]] = {}
    for rel in relationships:
        parent_key = _concept_key(getattr(rel, "fromModelObject", None))
        if not parent_key:
            continue
        grouped.setdefault((str(getattr(rel, "linkrole", "")), parent_key), []).append(rel)

    for (linkrole, parent_key), parent_relationships in sorted(grouped.items()):
        parent_values = facts_by_concept_context.get(parent_key, {})
        if not parent_values:
            continue
        for context_key, parent_cell in sorted(parent_values.items()):
            period_key = parent_cell["period_key"]
            child_cells = []
            missing_children = []
            expected = Decimal("0")
            ordered_relationships = sorted(
                parent_relationships,
                key=lambda item: _to_decimal(getattr(item, "order", None)) or Decimal("0"),
            )
            for rel in ordered_relationships:
                child_obj = getattr(rel, "toModelObject", None)
                child_key = _concept_key(child_obj)
                weight = _to_decimal(getattr(rel, "weight", None)) or Decimal("1")
                child_cell = facts_by_concept_context.get(child_key, {}).get(context_key)
                child_concept = _concept_payload(child_obj, rel)
                if child_cell is None or child_cell.get("numeric_value") is None:
                    missing_children.append(child_concept)
                    continue
                child_value = Decimal(str(child_cell["numeric_value"]))
                expected += child_value * weight
                child_cells.append(
                    {
                        "concept": child_concept,
                        "weight": _decimal_to_str(weight),
                        "value": child_cell["value"],
                        "numeric_value": child_cell["numeric_value"],
                        "source_ref": child_cell["source_ref"],
                    }
                )

            reported_value = _to_decimal(parent_cell.get("numeric_value"))
            if reported_value is None:
                continue
            diff = reported_value - expected
            status = "missing" if missing_children else "pass"
            if not missing_children and abs(diff) > TOLERANCE:
                status = "fail"
            parent_obj = getattr(parent_relationships[0], "fromModelObject", None)
            role_label = _role_label(model_xbrl, linkrole)
            parent_label = _concept_label(parent_obj)
            validations.append(
                {
                    "status": status,
                    "source": "calculation_linkbase",
                    "statement": _role_id(linkrole),
                    "role": _snake(parent_key.rsplit(":", 1)[-1]),
                    "label": f"{role_label} — {parent_label}",
                    "linkrole_uri": linkrole,
                    "period_key": period_key,
                    "parent": {
                        "concept": _concept_payload(parent_obj, None),
                        "value": parent_cell["value"],
                        "numeric_value": parent_cell["numeric_value"],
                        "source_ref": parent_cell["source_ref"],
                    },
                    "children": child_cells,
                    "missing_children": missing_children,
                    "reported": _decimal_to_str(reported_value),
                    "expected": _decimal_to_str(expected),
                    "difference": _decimal_to_str(diff),
                    "tolerance": _decimal_to_str(TOLERANCE),
                }
            )

    summary = {
        "pass": sum(1 for item in validations if item["status"] == "pass"),
        "fail": sum(1 for item in validations if item["status"] == "fail"),
        "missing": sum(1 for item in validations if item["status"] == "missing"),
    }
    return {
        "available": True,
        "arcrole": CALCULATION_ARCROLE,
        "relationship_count": len(relationships),
        "summary": summary,
        "validations": validations,
    }


def _skipped_calculation() -> dict[str, Any]:
    return {
        "available": False,
        "reason": "calculation validations skipped by caller",
        "validations": [],
        "summary": {"pass": 0, "fail": 0, "missing": 0},
        "skipped": True,
    }


def _sections_from_presentation(
    presentation: Mapping[str, Any],
    cells: Sequence[Cell],
    column_index: Mapping[ColumnKey, int],
    *,
    include_trace: bool,
) -> list[dict[str, Any]]:
    if not presentation.get("available"):
        return []

    signatures = _dimension_signatures(cells)
    sections: list[dict[str, Any]] = []

    for role in presentation.get("roles", []) or []:
        for signature in signatures:
            rows = []
            for root in role.get("tree", []) or []:
                row = _row_from_presentation_node(
                    root,
                    signature,
                    column_index,
                    include_trace=include_trace,
                )
                if row is not None:
                    rows.append(row)
            if not rows:
                continue

            heading = str(role.get("label") or role.get("role_id") or "Statement")
            if signature:
                heading = f"{heading} — {_dimension_heading(signature)}"
            section: dict[str, Any] = {"heading": heading, "rows": rows}
            if include_trace:
                section["role_uri"] = role.get("role_uri")
                section["dimensions"] = dict(signature)
            sections.append(section)

    return sections


def _row_from_presentation_node(
    node: Mapping[str, Any],
    signature: DimensionSignature,
    column_index: Mapping[ColumnKey, int],
    *,
    include_trace: bool,
) -> dict[str, Any] | None:
    node_cells = [cell for cell in node.get("cells", []) or [] if _dimension_signature(cell) == signature]
    values, traces, has_reported_cells = _align_cells_to_columns(node_cells, column_index)

    child_rows = []
    for child in node.get("children", []) or []:
        child_row = _row_from_presentation_node(
            child,
            signature,
            column_index,
            include_trace=include_trace,
        )
        if child_row is not None:
            child_rows.append(child_row)

    if not has_reported_cells and not child_rows:
        return None

    row: dict[str, Any] = {
        "label": str(node.get("label") or node.get("local_name") or node.get("qname") or ""),
        "values": values if has_reported_cells else [],
    }
    if child_rows:
        row["rows"] = child_rows

    if include_trace:
        row.update(
            {
                "concept": node.get("qname"),
                "local_name": node.get("local_name"),
                "abstract": node.get("abstract"),
                "preferred_label": node.get("preferred_label"),
                "node_ref": node.get("node_ref"),
                "trace": traces,
            }
        )

    return row


def _flat_fallback_sections(
    cells: Sequence[Cell],
    column_index: Mapping[ColumnKey, int],
    *,
    include_trace: bool,
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    cells_by_signature: OrderedDict[DimensionSignature, list[Cell]] = OrderedDict()
    for signature in _dimension_signatures(cells):
        cells_by_signature[signature] = []
    for cell in cells:
        cells_by_signature.setdefault(_dimension_signature(cell), []).append(cell)

    for signature, signature_cells in cells_by_signature.items():
        rows = []
        for concept_cells in _group_cells_by_concept(signature_cells).values():
            values, traces, has_reported_cells = _align_cells_to_columns(
                concept_cells,
                column_index,
            )
            if not has_reported_cells:
                continue
            first_cell = concept_cells[0]
            row: dict[str, Any] = {
                "label": str(first_cell.get("label") or _local_name(first_cell)),
                "values": values,
            }
            if include_trace:
                concept = first_cell.get("concept") or {}
                row.update(
                    {
                        "concept": concept.get("qname"),
                        "local_name": concept.get("local_name"),
                        "abstract": False,
                        "trace": traces,
                    }
                )
            rows.append(row)

        if not rows:
            continue
        heading = "Facts" if not signature else f"Facts — {_dimension_heading(signature)}"
        section: dict[str, Any] = {"heading": heading, "rows": rows}
        if include_trace:
            section["dimensions"] = dict(signature)
        sections.append(section)

    return sections


def _columns_from_cells(cells: Sequence[Cell]) -> list[dict[str, Any]]:
    columns: dict[ColumnKey, dict[str, Any]] = {}
    for cell in cells:
        key = _column_key(cell)
        columns.setdefault(
            key,
            {
                "key": key,
                "label": _column_label(cell),
                "basis": cell.get("basis"),
                "period": cell.get("period"),
                "period_key": cell.get("period_key"),
            },
        )

    return sorted(columns.values(), key=_column_sort_key)


def _column_key(cell: Mapping[str, Any]) -> ColumnKey:
    return (str(cell.get("basis") or ""), str(cell.get("period_key") or ""))


def _column_label(cell: Mapping[str, Any]) -> str:
    period_label = _period_label(cell.get("period") or {})
    basis = cell.get("basis")
    if basis:
        return f"{str(basis).title()} · {period_label}"
    return period_label


def _column_sort_key(column: Mapping[str, Any]) -> tuple[str, str, str]:
    period = column.get("period") or {}
    period_end = ""
    period_start = ""
    if isinstance(period, Mapping):
        period_end = str(period.get("instant") or period.get("end") or "")
        period_start = str(period.get("start") or "")
    return (period_end, period_start, str(column.get("basis") or ""))


def _align_cells_to_columns(
    cells: Sequence[Cell], column_index: Mapping[ColumnKey, int]
) -> tuple[list[Any], list[Any], bool]:
    values: list[Any] = [None] * len(column_index)
    traces: list[Any] = [None] * len(column_index)
    has_reported_cells = False

    for cell in sorted(cells, key=lambda item: item.get("source_ref", {}).get("fact_index", 0)):
        index = column_index.get(_column_key(cell))
        if index is None:
            continue
        has_reported_cells = True
        values[index] = _merge_cell_value(values[index], cell.get("value"))
        traces[index] = _merge_cell_value(traces[index], _trace_for_cell(cell))

    return values, traces, has_reported_cells


def _merge_cell_value(existing: Any, value: Any) -> Any:
    if existing is None:
        return value
    if isinstance(existing, list):
        existing.append(value)
        return existing
    return [existing, value]


def _trace_for_cell(cell: Mapping[str, Any]) -> dict[str, Any]:
    source_fact = cell.get("source_fact") or {}
    concept = source_fact.get("concept") or cell.get("concept") or {}
    return {
        "concept": concept.get("qname"),
        "local_name": concept.get("local_name"),
        "context_id": cell.get("context_id"),
        "decimals": cell.get("decimals"),
        "dimensions": dict(cell.get("dimensions") or {}),
        "period_key": cell.get("period_key"),
        "period": cell.get("period"),
        "basis": cell.get("basis"),
        "unit": cell.get("unit"),
        "source_ref": cell.get("source_ref"),
    }


def _checks_payload(calculation: Mapping[str, Any]) -> dict[str, Any]:
    summary = calculation.get("summary") or {}
    passed = int(summary.get("pass") or 0)
    failed = int(summary.get("fail") or 0)
    missing = int(summary.get("missing") or 0)

    if calculation.get("skipped"):
        return {
            "status": "skipped",
            "summary": "Calculation checks skipped by caller",
        }

    if not calculation.get("available"):
        reason = calculation.get("reason") or "calculation linkbase unavailable"
        return {
            "status": "unavailable",
            "summary": f"Calculation checks unavailable: {reason}",
            "available": False,
            "reason": reason,
        }

    status = "ok"
    if failed:
        status = "fail"
    elif missing:
        status = "warning"

    return {
        "status": status,
        "summary": f"{passed} passed, {failed} failed, {missing} unavailable",
        "available": True,
        "passed": passed,
        "failed": failed,
        "unavailable": missing,
    }


def _fact_cells_by_concept(facts: Sequence[Fact]) -> dict[str, list[Cell]]:
    cells: dict[str, list[Cell]] = {}
    for source_index, fact in enumerate(facts):
        cell = _cell(source_index, fact)
        qname = str((fact.get("concept") or {}).get("qname") or "")
        local_name = _local_name(fact)
        if qname:
            cells.setdefault(qname, []).append(cell)
        if local_name:
            cells.setdefault(local_name, []).append(cell)
    return cells


def _fact_values_by_concept_context(
    facts: Sequence[Fact],
) -> dict[str, dict[str, Cell]]:
    values: dict[str, dict[str, Cell]] = {}
    for source_index, fact in enumerate(facts):
        numeric = _to_decimal(fact.get("value"))
        if numeric is None:
            continue
        qname = str((fact.get("concept") or {}).get("qname") or "")
        if not qname:
            continue
        cell = _cell(source_index, fact)
        values.setdefault(qname, {})[_context_key(cell)] = cell
    return values


def _group_cells_by_concept(cells: Sequence[Cell]) -> OrderedDict[str, list[Cell]]:
    grouped: OrderedDict[str, list[Cell]] = OrderedDict()
    for cell in cells:
        concept = cell.get("concept") or {}
        key = str(concept.get("qname") or concept.get("local_name") or cell.get("label") or "")
        grouped.setdefault(key, []).append(cell)
    return grouped


def _context_key(cell: Mapping[str, Any]) -> str:
    dimensions = cell.get("dimensions") or {}
    dimension_key = "|".join(f"{key}={value}" for key, value in sorted(dimensions.items()))
    return f"{cell.get('context_id')}|{cell.get('period_key')}|{dimension_key}"


def _cell(source_index: int, fact: Fact) -> Cell:
    value = fact.get("value")
    numeric_value = _to_decimal(value)
    return {
        "value": value,
        "numeric_value": _decimal_to_str(numeric_value),
        "unit": fact.get("unit"),
        "decimals": fact.get("decimals"),
        "context_id": str(fact.get("context_id") or fact.get("ctx") or ""),
        "basis": fact.get("basis"),
        "period_key": _period_key(fact),
        "period": _period_descriptor(fact),
        "dimensions": dict(fact.get("dimensions") or fact.get("dims") or {}),
        "concept": dict(fact.get("concept") or {}),
        "label": fact.get("label") or _local_name(fact),
        "source_ref": _source_ref(source_index, fact),
        "source_fact": deepcopy(dict(fact)),
    }


def _source_ref(source_index: int, fact: Fact) -> dict[str, Any]:
    concept = fact.get("concept") if isinstance(fact.get("concept"), Mapping) else {}
    return {
        "fact_index": source_index,
        "context_id": str(fact.get("context_id") or fact.get("ctx") or ""),
        "concept": concept.get("qname") or fact.get("label"),
        "local_name": _local_name(fact),
    }


def _period_descriptor(fact: Fact) -> dict[str, Any]:
    period = fact.get("period") or {}
    descriptor = {
        "period_key": _period_key(fact),
        "context_id": str(fact.get("context_id") or fact.get("ctx") or ""),
        "duration": _duration_kind(str(fact.get("context_id") or ""), period),
        "basis": fact.get("basis"),
    }
    if isinstance(period, Mapping):
        descriptor.update(period)
    else:
        descriptor["raw"] = period
    return descriptor


def _period_key(fact: Fact) -> str:
    period = fact.get("period") or {}
    basis = fact.get("basis") or "unknown_basis"
    context_id = str(fact.get("context_id") or fact.get("ctx") or "")
    duration = _duration_kind(context_id, period)
    if isinstance(period, Mapping):
        if "instant" in period:
            value = period["instant"]
        elif "forever" in period:
            value = "forever"
        else:
            value = f"{period.get('start')}..{period.get('end')}"
    else:
        value = str(period)
    return f"{basis}:{duration}:{value}"


def _duration_kind(context_id: str, period: Any) -> str:
    if isinstance(period, Mapping) and "instant" in period:
        return "instant"
    if isinstance(period, Mapping) and "forever" in period:
        return "forever"
    if context_id.startswith("One"):
        return "one_period"
    if context_id.startswith("Four"):
        return "four_period"
    return "duration"


def _period_label(period: Mapping[str, Any]) -> str:
    if "instant" in period:
        return f"As at {_format_date(period['instant'])}"
    if "forever" in period:
        return "Forever"

    start = period.get("start")
    end = period.get("end")
    if start and end:
        start_date = _parse_date(start)
        end_date = _parse_date(end)
        if start_date and end_date:
            if start_date == end_date:
                return f"On {_format_date(end)}"
            days = (end_date - start_date).days + 1
            if 360 <= days <= 370:
                return f"Year ended {_format_date(end)}"
            if 80 <= days <= 95:
                return f"Quarter ended {_format_date(end)}"
        return f"Period {_format_date(start)} to {_format_date(end)}"

    raw = period.get("raw")
    if raw:
        return str(raw)
    return "As reported"


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _format_date(value: Any) -> str:
    parsed = _parse_date(value)
    if parsed is None:
        return str(value)
    return parsed.strftime("%d %b %Y").lstrip("0")


def _dimension_signatures(cells: Sequence[Cell]) -> list[DimensionSignature]:
    signatures = {_dimension_signature(cell) for cell in cells}
    return sorted(signatures, key=lambda signature: (bool(signature), str(signature)))


def _dimension_signature(cell: Mapping[str, Any]) -> DimensionSignature:
    dimensions = cell.get("dimensions") or {}
    return tuple((str(key), str(value)) for key, value in sorted(dimensions.items()))


def _dimension_heading(signature: DimensionSignature) -> str:
    parts = []
    for axis, member in signature:
        axis_label = _qname_tail(axis)
        member_label = _qname_tail(member)
        parts.append(f"{axis_label}: {member_label}")
    return ", ".join(parts)


def _qname_tail(value: Any) -> str:
    text = str(value)
    if ":" in text:
        return text.rsplit(":", 1)[-1]
    if "}" in text:
        return text.rsplit("}", 1)[-1]
    return text


def _dominant_unit(cells: Sequence[Cell]) -> str | None:
    units = [str(cell.get("unit")) for cell in cells if cell.get("unit")]
    if not units:
        return None
    unique_units = set(units)
    if len(unique_units) == 1:
        return units[0]
    unit_counts = Counter(units)
    unit, _count = unit_counts.most_common(1)[0]
    return f"mixed (most common: {unit})"


def _view_title(
    presentation: Mapping[str, Any], sections: Sequence[Mapping[str, Any]]
) -> str:
    if presentation.get("available"):
        roles = presentation.get("roles") or []
        if len(roles) == 1:
            return str(roles[0].get("label") or roles[0].get("role_id") or "XBRL filing")
        if roles:
            return "XBRL filing"
    if sections:
        heading = str(sections[0].get("heading") or "")
        if heading and heading != "Facts":
            return heading
    return "XBRL filing"


def _concept_payload(concept_obj: Any, rel: Any | None) -> dict[str, Any]:
    qname = getattr(concept_obj, "qname", None)
    preferred_label = getattr(rel, "preferredLabel", None) if rel is not None else None
    return {
        "qname": str(qname) if qname is not None else None,
        "local_name": getattr(qname, "localName", None),
        "namespace": getattr(qname, "namespaceURI", None),
        "label": _concept_label(concept_obj, preferred_label),
        "abstract": bool(getattr(concept_obj, "isAbstract", False)),
        "period_type": getattr(concept_obj, "periodType", None),
        "balance": getattr(concept_obj, "balance", None),
    }


def _concept_label(concept_obj: Any, preferred_label: str | None = None) -> str | None:
    if concept_obj is None:
        return None
    try:
        if preferred_label:
            label = concept_obj.label(lang="en", labelrole=preferred_label)
            if label:
                return str(label)
        label = concept_obj.label(lang="en")
        if label:
            return str(label)
        verbose = concept_obj.label(
            lang="en",
            labelrole="http://www.xbrl.org/2003/role/verboseLabel",
        )
        if verbose:
            return str(verbose)
    except Exception:
        pass
    qname = getattr(concept_obj, "qname", None)
    return str(qname) if qname is not None else None


def _concept_key(concept_obj: Any) -> str:
    qname = getattr(concept_obj, "qname", None)
    return str(qname) if qname is not None else ""


def _role_label(model_xbrl: Any, linkrole: str) -> str:
    try:
        role_types = (getattr(model_xbrl, "roleTypes", {}) or {}).get(linkrole) or []
        if len(role_types) > 0:
            definition = getattr(role_types[0], "definition", None)
            if definition:
                return str(definition)
    except Exception:
        pass
    return _role_id(linkrole)


def _role_id(linkrole: str) -> str:
    return str(linkrole).rstrip("/").rsplit("/", 1)[-1]


def _local_name(fact: Fact) -> str:
    concept = fact.get("concept")
    if isinstance(concept, Mapping):
        return str(concept.get("local_name") or concept.get("qname") or "")
    return str(fact.get("label") or "")


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _decimal_to_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _snake(value: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0 and value[index - 1].islower():
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


def _append_markdown_table(
    lines: list[str], rows: Sequence[Mapping[str, Any]], columns: Sequence[str]
) -> None:
    header = ["Line item", *columns]
    lines.append("| " + " | ".join(_escape_table_cell(item) for item in header) + " |")
    lines.append("| " + " | ".join("---" for _item in header) + " |")
    for row, depth in _flatten_rows(rows):
        label = f"{'&nbsp;&nbsp;' * depth}{row.get('label', '')}"
        values = list(row.get("values") or [])
        padded_values = values + [None] * max(0, len(columns) - len(values))
        table_row = [label, *[_format_markdown_value(value) for value in padded_values]]
        lines.append("| " + " | ".join(_escape_table_cell(item) for item in table_row) + " |")


def _flatten_rows(
    rows: Sequence[Mapping[str, Any]], depth: int = 0
) -> list[tuple[Mapping[str, Any], int]]:
    flattened: list[tuple[Mapping[str, Any], int]] = []
    for row in rows:
        flattened.append((row, depth))
        flattened.extend(_flatten_rows(row.get("rows", []) or [], depth + 1))
    return flattened


def _format_markdown_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, list):
        return "; ".join(_format_markdown_value(item) for item in value)
    return str(value)


def _escape_table_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _escape_markdown_text(value: str) -> str:
    return value.replace("|", "\\|")
