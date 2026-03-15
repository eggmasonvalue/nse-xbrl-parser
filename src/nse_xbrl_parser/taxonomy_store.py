from __future__ import annotations

import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

TAXONOMY_DIR = Path(__file__).parent / "taxonomies"
INDEX_PATH = TAXONOMY_DIR / "index.json"

ENTRY_POINT_EXCLUDE_TOKENS = (
    "-roles-",
    "-types",
    "-label",
    "-lab",
    "-ref",
    "-pre",
    "-def",
    "-cal",
)
FILE_SUFFIXES = {".xsd", ".xml"}
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*]+')
TARGET_NAMESPACE_FAMILY_PATTERN = re.compile(
    r"/xbrl/(?P<family>[^/]+)/(?P<version>\d{4}-\d{2}-\d{2})/"
)
RELEASE_ID_PATTERN = re.compile(r".+__([0-9a-f]{8})$")


@dataclass
class TaxonomyRelease:
    family: str
    release_id: str
    fingerprint: str
    version: Optional[str]
    entry_points: list[str]
    target_namespaces: list[str]
    imported_core_namespaces: list[str]
    files: list[str]
    source_url: Optional[str] = None
    provenance_name: Optional[str] = None
    stored_path: Optional[str] = None
    source_path: Optional[str] = None

    def to_index_entry(self) -> dict:
        return asdict(self)


def _safe_name(value: str, default: str) -> str:
    cleaned = INVALID_PATH_CHARS.sub("_", value).strip().replace(" ", "_")
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or default


def _read_xml_root(path: Path) -> Optional[ET.Element]:
    try:
        return ET.parse(path).getroot()
    except Exception:
        return None


def _read_target_namespace(path: Path) -> Optional[str]:
    root = _read_xml_root(path)
    if root is None:
        return None
    return root.attrib.get("targetNamespace")


def _iter_local_imports(path: Path) -> list[tuple[str, str]]:
    root = _read_xml_root(path)
    if root is None:
        return []

    imports: list[tuple[str, str]] = []
    for elem in root.iter():
        if not elem.tag.endswith("import"):
            continue
        namespace = elem.attrib.get("namespace")
        schema_location = elem.attrib.get("schemaLocation")
        if namespace and schema_location and "://" not in schema_location:
            imports.append((namespace, schema_location))
    return imports


def iter_entry_point_schemas(root: Path) -> list[Path]:
    schemas: list[Path] = []
    for path in root.rglob("*.xsd"):
        if "core" in path.parts:
            continue
        lower_name = path.name.lower()
        if any(token in lower_name for token in ENTRY_POINT_EXCLUDE_TOKENS):
            continue
        schemas.append(path)
    return sorted(schemas)


def _detect_family_from_metadata(root: Path) -> Optional[str]:
    package_xml = root / "META-INF" / "taxonomyPackage.xml"
    xml_root = _read_xml_root(package_xml)
    if xml_root is None:
        return None

    for elem in xml_root.iter():
        text = (elem.text or "").strip()
        if not text or "/" in text or len(text) < 3:
            continue
        return _safe_name(text, "taxonomy")
    return None


def _detect_version(entry_point: Path, target_namespace: Optional[str]) -> Optional[str]:
    candidates = [entry_point.name]
    if target_namespace:
        candidates.append(target_namespace)
    for candidate in candidates:
        match = DATE_PATTERN.search(candidate)
        if match:
            return match.group(0)
    return None


def _detect_family_and_version(entry_point: Path, bundle_root: Path) -> tuple[str, Optional[str], Optional[str]]:
    target_namespace = _read_target_namespace(entry_point)
    if target_namespace:
        match = TARGET_NAMESPACE_FAMILY_PATTERN.search(target_namespace)
        if match:
            return _safe_name(match.group("family"), entry_point.parent.name), match.group("version"), target_namespace

    metadata_family = _detect_family_from_metadata(bundle_root)
    if metadata_family:
        return metadata_family, _detect_version(entry_point, target_namespace), target_namespace

    return _safe_name(entry_point.parent.name, "taxonomy"), _detect_version(entry_point, target_namespace), target_namespace


def _find_bundle_root(entry_point_dir: Path, container_root: Path) -> Path:
    current = entry_point_dir
    while current != container_root and container_root in current.parents:
        parent = current.parent
        if (parent / "core").exists():
            return parent
        current = parent
    if (container_root / "core").exists():
        return container_root
    return entry_point_dir


def _bundle_files(bundle_root: Path, family_dir: Path) -> list[Path]:
    files: list[Path] = []
    for scoped_root in (family_dir, bundle_root / "core", bundle_root / "META-INF"):
        if not scoped_root.exists():
            continue
        files.extend(
            path for path in scoped_root.rglob("*") if path.is_file() and path.suffix.lower() in FILE_SUFFIXES
        )
    return sorted(files)


def _storage_relpath(family: str, rel_path: str) -> str:
    normalized = rel_path.replace("\\", "/")
    if normalized.startswith("core/") or normalized.startswith("META-INF/"):
        return normalized
    if normalized.startswith(f"{family}/"):
        return normalized
    return f"{family}/{normalized}"


def build_release_from_entry_point(entry_point: Path, container_root: Path) -> TaxonomyRelease:
    family_dir = entry_point.parent
    bundle_root = _find_bundle_root(family_dir, container_root)
    family, version, target_namespace = _detect_family_and_version(entry_point, bundle_root)
    raw_files = _bundle_files(bundle_root, family_dir)

    raw_entry_points = iter_entry_point_schemas(family_dir)
    entry_points = sorted(
        _storage_relpath(family, str(path.relative_to(bundle_root)).replace("\\", "/"))
        for path in raw_entry_points
    )
    target_namespaces = sorted({_read_target_namespace(path) for path in raw_entry_points if _read_target_namespace(path)})
    imported_core_namespaces = sorted(
        {namespace for path in raw_entry_points for namespace, _ in _iter_local_imports(path)}
    )

    manifest_lines = [f"family={family}", f"version={version or ''}"]
    stored_files: list[str] = []
    for file_path in raw_files:
        rel_path = str(file_path.relative_to(bundle_root)).replace("\\", "/")
        stored_rel_path = _storage_relpath(family, rel_path)
        stored_files.append(stored_rel_path)
        digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        manifest_lines.append(f"path={stored_rel_path}")
        manifest_lines.append(f"sha256={digest}")
        if file_path.suffix.lower() == ".xsd":
            namespace = _read_target_namespace(file_path)
            if namespace:
                manifest_lines.append(f"targetNamespace={namespace}")
            for import_namespace, schema_location in _iter_local_imports(file_path):
                manifest_lines.append(f"import={schema_location}|{import_namespace}")

    fingerprint = hashlib.sha256("\n".join(manifest_lines).encode("utf-8")).hexdigest()
    release_id = f"{version or 'undated'}__{fingerprint[:8]}"

    return TaxonomyRelease(
        family=family,
        release_id=release_id,
        fingerprint=fingerprint,
        version=version,
        entry_points=entry_points,
        target_namespaces=target_namespaces,
        imported_core_namespaces=imported_core_namespaces,
        files=sorted(stored_files),
        source_path=str(bundle_root),
    )


def discover_release_units(container_root: Path) -> list[TaxonomyRelease]:
    releases: dict[tuple[str, str], TaxonomyRelease] = {}
    for entry_point in iter_entry_point_schemas(container_root):
        release = build_release_from_entry_point(entry_point, container_root)
        releases[(release.family, release.fingerprint)] = release
    return sorted(releases.values(), key=lambda item: (item.family, item.release_id))


def release_is_self_contained(release: TaxonomyRelease) -> bool:
    release_root = Path(release.source_path) if release.source_path else None
    if release_root is None:
        return False

    family_root = release_root / release.family
    for entry_point in release.entry_points:
        if not entry_point.startswith(f"{release.family}/"):
            continue
        entry_point_path = release_root / Path(entry_point[len(release.family) + 1 :])
        if not entry_point_path.exists():
            entry_point_path = family_root / Path(entry_point).name
        if not entry_point_path.exists():
            return False
        for namespace, schema_location in _iter_local_imports(entry_point_path):
            imported_path = (entry_point_path.parent / schema_location).resolve()
            if not imported_path.exists():
                return False
            imported_namespace = _read_target_namespace(imported_path)
            if imported_namespace != namespace:
                return False
    return True


def load_index(index_path: Path = INDEX_PATH) -> dict:
    if not index_path.exists():
        return {"releases": []}
    return json.loads(index_path.read_text(encoding="utf-8"))


def write_index(entries: list[dict], index_path: Path = INDEX_PATH) -> None:
    payload = {"releases": sorted(entries, key=lambda item: (item["family"], item["release_id"]))}
    index_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def install_release(
    release: TaxonomyRelease,
    destination_root: Path = TAXONOMY_DIR,
    source_url: Optional[str] = None,
    provenance_name: Optional[str] = None,
) -> tuple[bool, Path]:
    release_root = Path(release.source_path) if release.source_path else None
    if release_root is None:
        raise ValueError("Release source_path is required for installation.")

    existing_index = load_index(destination_root / "index.json")
    existing = {
        (entry["family"], entry["fingerprint"]): entry for entry in existing_index.get("releases", [])
    }
    if (release.family, release.fingerprint) in existing:
        return False, destination_root / existing[(release.family, release.fingerprint)]["stored_path"]

    target_dir = destination_root / release.family / release.release_id
    target_dir.mkdir(parents=True, exist_ok=True)
    for rel_path in release.files:
        source_path = release_root / Path(rel_path)
        if not source_path.exists() and rel_path.startswith(f"{release.family}/"):
            source_path = release_root / Path(rel_path[len(release.family) + 1 :])
        destination_path = target_dir / Path(rel_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)

    entry = release.to_index_entry()
    entry["source_url"] = source_url
    entry["provenance_name"] = provenance_name
    entry["stored_path"] = str(target_dir.relative_to(destination_root)).replace("\\", "/")
    updated_releases = existing_index.get("releases", [])
    updated_releases.append(entry)
    write_index(updated_releases, destination_root / "index.json")
    return True, target_dir


def iter_versioned_release_roots(taxonomy_root: Path = TAXONOMY_DIR) -> list[Path]:
    release_roots: list[Path] = []
    for family_dir in taxonomy_root.iterdir():
        if not family_dir.is_dir() or family_dir.name == "legacy":
            continue
        for release_dir in family_dir.iterdir():
            if release_dir.is_dir() and RELEASE_ID_PATTERN.fullmatch(release_dir.name):
                release_roots.append(release_dir)
    return sorted(release_roots)


def collect_versioned_schema_candidates(schema_ref: str, taxonomy_root: Path = TAXONOMY_DIR) -> list[Path]:
    """Search versioned releases for a schema reference using the index for speed."""
    index = load_index(taxonomy_root / "index.json")
    candidates: list[Path] = []
    
    for release in index.get("releases", []):
        stored_path = release.get("stored_path")
        if not stored_path:
            continue
            
        # Check if the schema_ref is in the files of this release
        # We need to match the filename part of the path
        for file_rel_path in release.get("files", []):
            if file_rel_path.split("/")[-1] == schema_ref:
                candidates.append(taxonomy_root / stored_path / file_rel_path)
            elif file_rel_path == schema_ref: # Just in case it's a flat path
                candidates.append(taxonomy_root / stored_path / file_rel_path)
                
    return sorted(list(set(candidates)))


def collect_flat_schema_candidates(schema_ref: str, taxonomy_root: Path = TAXONOMY_DIR) -> list[Path]:
    candidates: list[Path] = []
    for path in taxonomy_root.rglob(schema_ref):
        rel_parts = path.relative_to(taxonomy_root).parts
        if not rel_parts:
            continue
        if len(rel_parts) >= 2 and RELEASE_ID_PATTERN.fullmatch(rel_parts[1]):
            continue
        candidates.append(path)
    return sorted(candidates)
