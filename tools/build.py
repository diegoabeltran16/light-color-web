#!/usr/bin/env python3
"""Small allowlist-based static builder for Light Color."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from html.parser import HTMLParser
from html import escape as escape_html
from pathlib import Path, PurePosixPath
from urllib.parse import urlencode, urlsplit

from validate_public import sha256_file, validate_output_tree, validate_relative_output


class BuildError(ValueError):
    """A rejected configuration or unsafe build operation."""


KINDS = {"html", "css", "js", "asset"}
TEXT_KINDS = {"html", "css", "js"}
BASE_PATTERN = re.compile(r"^/(?:[a-zA-Z0-9][a-zA-Z0-9-]*/)*$")
FORBIDDEN_SOURCE_PARTS = {
    ".git", ".aws", ".codex", ".agents", "r002", "r003", "tests", "fixtures",
    "tools", "commands", "wp-content", "wp-includes",
}
FORBIDDEN_SOURCE_SUFFIXES = {".py", ".php", ".pem", ".key", ".p12", ".pfx", ".bak", ".old"}
COMPONENT_FILES = {
    "header": "components/header.html",
    "footer": "components/footer.html",
    "whatsapp": "components/whatsapp.html",
    "favicon": "components/favicon.html",
}
ACTIVE_ROUTES = {"inicio", "nosotros", "servicios", "productos"}
HEADER_VARIANTS = {"standard", "service-detail"}
PUBLIC_REQUIRED_OUTPUTS = {
    "index.html",
    "nosotros/index.html",
    "servicios/index.html",
    "servicios/corte-de-cabello/index.html",
    "servicios/coloracion-con-tinte/index.html",
    "servicios/henna-capilar/index.html",
    "productos/index.html",
}
PUBLIC_REVIEW_ASSET_BLOCKLIST = {
    "assets/home/review-400.jpg",
    "assets/home/review-300.jpg",
}
HOME_PREVIEW_ALLOWLIST = {
    ("pages/home.html", "index.html", "html"),
    ("styles/home.css", "assets/home.css", "css"),
    ("scripts/home.js", "assets/home.js", "js"),
    ("styles/shared.css", "assets/shared.css", "css"),
    ("scripts/shared.js", "assets/shared.js", "js"),
    ("assets/brand/logo.png", "assets/brand/logo.png", "asset"),
    ("assets/brand/favicon-32.png", "assets/brand/favicon-32.png", "asset"),
    ("assets/brand/favicon-192.png", "assets/brand/favicon-192.png", "asset"),
    ("assets/home/hero-silhouette-900.webp", "assets/home/hero-silhouette-900.webp", "asset"),
    ("assets/home/654729676-5fc380e1-e7af-4f92-b1fd-3f80f4c08387-300x300.webp", "assets/home/654729676-5fc380e1-e7af-4f92-b1fd-3f80f4c08387-300x300.webp", "asset"),
    ("assets/home/654729676-5fc380e1-e7af-4f92-b1fd-3f80f4c08387-600x600.webp", "assets/home/654729676-5fc380e1-e7af-4f92-b1fd-3f80f4c08387-600x600.webp", "asset"),
    ("assets/home/654729676-5fc380e1-e7af-4f92-b1fd-3f80f4c08387-768x768.webp", "assets/home/654729676-5fc380e1-e7af-4f92-b1fd-3f80f4c08387-768x768.webp", "asset"),
    ("assets/home/review-400.jpg", "assets/home/review-400.jpg", "asset"),
    ("assets/home/review-300.jpg", "assets/home/review-300.jpg", "asset"),
    ("assets/home/products-art-1254.png", "assets/home/products-art-1254.png", "asset"),
    ("assets/home/654749444-e086a15c-e50a-482a-a381-8a7c8ff00fed-300x300.png", "assets/home/654749444-e086a15c-e50a-482a-a381-8a7c8ff00fed-300x300.png", "asset"),
    ("assets/home/654749444-e086a15c-e50a-482a-a381-8a7c8ff00fed-600x600.png", "assets/home/654749444-e086a15c-e50a-482a-a381-8a7c8ff00fed-600x600.png", "asset"),
    ("assets/home/654749444-e086a15c-e50a-482a-a381-8a7c8ff00fed-768x768.png", "assets/home/654749444-e086a15c-e50a-482a-a381-8a7c8ff00fed-768x768.png", "asset"),
    ("assets/home/654749444-e086a15c-e50a-482a-a381-8a7c8ff00fed-1024x1024.png", "assets/home/654749444-e086a15c-e50a-482a-a381-8a7c8ff00fed-1024x1024.png", "asset"),
    ("assets/home/promo-backdrop.jpg", "assets/home/promo-backdrop.jpg", "asset"),
    ("assets/home/services-backdrop.png", "assets/home/services-backdrop.png", "asset"),
    ("assets/home/services-backdrop-tablet.jpg", "assets/home/services-backdrop-tablet.jpg", "asset"),
    ("assets/home/services-backdrop-mobile.png", "assets/home/services-backdrop-mobile.png", "asset"),
    ("assets/home/products-backdrop.jpg", "assets/home/products-backdrop.jpg", "asset"),
    ("assets/home/products-backdrop-mobile.jpg", "assets/home/products-backdrop-mobile.jpg", "asset"),
}
HOME_PREVIEW_COMPONENTS = {"header", "footer", "whatsapp", "favicon"}
ABOUT_PREVIEW_ADDITIONS = {
    ("pages/about.html", "nosotros/index.html", "html"),
    ("styles/about.css", "assets/about.css", "css"),
}
CONNECTED_PREVIEW_ALLOWLIST = HOME_PREVIEW_ALLOWLIST | ABOUT_PREVIEW_ADDITIONS
SERVICE_DETAIL_IDS = {
    "corte-de-cabello": "servicios/corte-de-cabello/index.html",
    "coloracion-con-tinte": "servicios/coloracion-con-tinte/index.html",
    "henna-capilar": "servicios/henna-capilar/index.html",
}
SERVICE_ASSET_FILES = {
    "assets/services/portada_servicios.png",
    "assets/services/corte-de-cabello/portada_catalogo.png",
    *(f"assets/services/corte-de-cabello/{number}.png" for number in range(1, 7)),
    "assets/services/coloracion-con-tinte/portada_catalogo.png",
    *(f"assets/services/coloracion-con-tinte/{number}.png" for number in range(1, 5)),
    "assets/services/henna-capilar/portada_catalogo.png",
    *(f"assets/services/henna-capilar/{number}.png" for number in range(1, 5)),
}
SERVICES_PREVIEW_ADDITIONS = {
    ("pages/services.html", "servicios/index.html", "html"),
    ("templates/service-detail.html", SERVICE_DETAIL_IDS["corte-de-cabello"], "html"),
    ("templates/service-detail.html", SERVICE_DETAIL_IDS["coloracion-con-tinte"], "html"),
    ("templates/service-detail.html", SERVICE_DETAIL_IDS["henna-capilar"], "html"),
    ("catalog-data/services.json", "assets/services/services.json", "asset"),
    ("styles/services.css", "assets/services.css", "css"),
    ("scripts/catalog.js", "assets/catalog.js", "js"),
    *((path, path, "asset") for path in SERVICE_ASSET_FILES),
}
PRODUCTS_PREVIEW_ADDITIONS = {
    ("pages/products.html", "productos/index.html", "html"),
    ("catalog-data/products.json", "assets/products/products.json", "asset"),
    ("styles/products.css", "assets/products.css", "css"),
}
CONNECTED_PREVIEW_ALLOWLIST |= SERVICES_PREVIEW_ADDITIONS | PRODUCTS_PREVIEW_ADDITIONS
PRODUCT_DEMO_IDS = ("demo-01", "demo-02", "demo-03")
PRODUCT_DEMO_GROUPS = ("Marca de prueba A", "Marca de prueba B", "Otros productos — prueba")
PRODUCT_DEMO_ASSETS = tuple(f"product-demo-{letter}{suffix}.svg" for letter in "abc" for suffix in ("", "-alt"))
PRODUCT_DEMO_ROUTES = {product_id: f"productos/{product_id}/index.html" for product_id in PRODUCT_DEMO_IDS}
INCLUDE_PATTERN = re.compile(r"<!--\s*lc:include\s+([a-z][a-z0-9-]*)\s*-->")
ANY_INCLUDE_PATTERN = re.compile(r"<!--\s*lc:include\b", re.DOTALL)
ACTIVE_PATTERN = re.compile(r"\{\{(active|current):([a-z][a-z0-9-]*)\}\}")
KNOWN_COMPONENTS = frozenset(COMPONENT_FILES)


class _ComponentHTMLAudit(HTMLParser):
    """Reject unsafe link schemes and remote embedded resources in fragments."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if any(name.lower().startswith("on") for name, _value in attrs):
            self.errors.append("manejadores JavaScript inline no permitidos en componentes")
        if tag == "script":
            self.errors.append("scripts inline no permitidos en componentes")
        for name in ("href", "src"):
            value = values.get(name)
            if not value:
                continue
            parsed = urlsplit(value.strip())
            if parsed.scheme.lower() == "javascript":
                self.errors.append("URL javascript: no permitida en componentes")
            embedded_resource = tag in {"img", "script", "link", "iframe", "source", "video", "audio"}
            if embedded_resource and (parsed.scheme.lower() in {"http", "https"} or value.strip().startswith("//")):
                self.errors.append("recurso remoto no permitido en componentes")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


class _PageProtocolAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            attribute = name.lower()
            if attribute.startswith("on"):
                self.errors.append("manejador JavaScript inline")
            if not value:
                continue
            if attribute in {"href", "src", "action", "formaction", "poster", "xlink:href"}:
                if urlsplit(value.strip()).scheme.lower() == "javascript":
                    self.errors.append("URL javascript:")
            if attribute == "srcset" and any(urlsplit(candidate.strip().split()[0]).scheme.lower() == "javascript" for candidate in value.split(",") if candidate.strip()):
                self.errors.append("URL javascript: en srcset")
            if tag == "script" and attribute == "src":
                parsed = urlsplit(value.strip())
                if parsed.scheme.lower() in {"http", "https"} or value.strip().startswith("//"):
                    self.errors.append("script de terceros no permitido")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def validate_base_path(value: str) -> str:
    if not isinstance(value, str) or not BASE_PATTERN.fullmatch(value):
        raise BuildError("base path debe comenzar y terminar con / y contener segmentos simples")
    return value


def validate_manifest_data(data: object) -> list[dict[str, str]]:
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        raise BuildError("manifiesto inválido: schema_version debe ser 1")
    if set(data) - {"schema_version", "site", "entries", "components"}:
        raise BuildError("manifiesto inválido: campo desconocido")
    if data.get("site") != "light-color-web":
        raise BuildError("manifiesto inválido: site no reconocido")
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise BuildError("manifiesto inválido: entries debe ser una lista")
    outputs: set[str] = set()
    validated: list[dict[str, str]] = []
    for index, item in enumerate(entries):
        required = {"source", "output", "kind"}
        optional = {"root", "active", "variant", "record"}
        if not isinstance(item, dict) or not required <= set(item) or set(item) - required - optional:
            raise BuildError(f"entrada {index}: se requieren source, output, kind y solo opciones documentadas")
        source = item["source"]
        kind = item["kind"]
        if not isinstance(source, str) or not source or "\\" in source or ":" in source or any(ord(char) < 32 for char in source):
            raise BuildError(f"entrada {index}: source debe ser ruta relativa POSIX")
        if re.match(r"^[a-zA-Z]:", source):
            raise BuildError(f"entrada {index}: source con prefijo de unidad no permitido")
        source_path = PurePosixPath(source)
        if source_path.is_absolute() or any(part in {"", ".", ".."} for part in source_path.parts):
            raise BuildError(f"entrada {index}: source inseguro")
        if source_path.as_posix() != source:
            raise BuildError(f"entrada {index}: source no normalizado")
        reserved_names = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
        if any(part.endswith((".", " ")) or part.split(".", 1)[0].lower() in reserved_names for part in source_path.parts):
            raise BuildError(f"entrada {index}: nombre de source no portable")
        source_parts_lower = {part.lower() for part in source_path.parts}
        if source_parts_lower & FORBIDDEN_SOURCE_PARTS or any(part.startswith(".") for part in source_path.parts):
            raise BuildError(f"entrada {index}: fuente privada o interna no permitida")
        if source_path.name.lower() in {".env", "credentials", "secrets.json"} or source_path.suffix.lower() in FORBIDDEN_SOURCE_SUFFIXES:
            raise BuildError(f"entrada {index}: tipo de fuente no publicable")
        try:
            output = validate_relative_output(item["output"])
        except ValueError as error:
            raise BuildError(str(error)) from error
        if output == "build-manifest.json":
            raise BuildError("build-manifest.json está reservado para el constructor")
        if not isinstance(kind, str) or kind not in KINDS:
            raise BuildError(f"entrada {index}: tipo no permitido")
        source_root = item.get("root", "fixture")
        if not isinstance(source_root, str) or source_root not in {"fixture", "src"}:
            raise BuildError(f"entrada {index}: root debe ser fixture o src")
        active = item.get("active")
        if active is not None and (kind != "html" or not isinstance(active, str) or active not in ACTIVE_ROUTES):
            raise BuildError(f"entrada {index}: active no permitido")
        variant = item.get("variant")
        if variant is not None and (kind != "html" or not isinstance(variant, str) or variant not in HEADER_VARIANTS):
            raise BuildError(f"entrada {index}: variant no permitido")
        if variant == "service-detail" and active != "servicios":
            raise BuildError(f"entrada {index}: service-detail requiere active=servicios")
        record = item.get("record")
        if record is not None:
            if kind != "html" or not isinstance(record, str) or record not in SERVICE_DETAIL_IDS:
                raise BuildError(f"entrada {index}: record solo admite una ficha aprobada de Servicios")
            if source != "templates/service-detail.html" or output != SERVICE_DETAIL_IDS[record] or active != "servicios":
                raise BuildError(f"entrada {index}: la ficha debe usar plantilla, ruta y estado activo canónicos")
        folded = output.casefold()
        if folded in {path.casefold() for path in outputs}:
            raise BuildError(f"colisión de destino: {output}")
        outputs.add(output)
        validated_entry = {"source": source, "output": output, "kind": kind, "root": source_root}
        if active is not None:
            validated_entry["active"] = active
        if variant is not None:
            validated_entry["variant"] = variant
        if record is not None:
            validated_entry["record"] = record
        validated.append(validated_entry)
    for output in outputs:
        for other in outputs:
            if output != other and other.startswith(output + "/"):
                raise BuildError(f"colisión entre archivo y directorio: {output} y {other}")
    return validated


def validate_component_names(data: dict[str, object]) -> list[str]:
    names = data.get("components", [])
    if not isinstance(names, list) or any(not isinstance(name, str) or name not in KNOWN_COMPONENTS for name in names):
        raise BuildError("manifiesto inválido: components contiene un nombre no permitido")
    if len(names) != len(set(names)):
        raise BuildError("manifiesto inválido: components contiene duplicados")
    return names


def validate_public_entries(entries: list[dict[str, str]]) -> None:
    for entry in entries:
        if entry["root"] != "src":
            raise BuildError("la modalidad pública solo admite fuentes con root=src")
        parts = {part.lower() for part in PurePosixPath(entry["source"]).parts}
        if parts & {"tests", "fixtures", "r002", "r003", ".git", ".aws", ".codex", ".agents"}:
            raise BuildError("fuente pública fuera de la frontera canónica")
    outputs = {entry["output"] for entry in entries if entry["kind"] == "html"}
    if not PUBLIC_REQUIRED_OUTPUTS <= outputs:
        missing = ", ".join(sorted(PUBLIC_REQUIRED_OUTPUTS - outputs))
        raise BuildError(f"sitio público incompleto: faltan páginas aprobadas ({missing})")
    historical_reviews = {
        entry["source"] for entry in entries
    } & PUBLIC_REVIEW_ASSET_BLOCKLIST
    if historical_reviews:
        raise BuildError("calificaciones históricas D'Castell bloqueadas hasta revisión editorial")
    if any(entry["output"].startswith("productos/demo-") or "product-demo-" in entry["output"] for entry in entries):
        raise BuildError("rutas o recursos de demostración de Productos no publicables")
    product_registry = [entry for entry in entries if entry["output"] == "assets/products/products.json"]
    if len(product_registry) != 1 or product_registry[0]["source"] != "catalog-data/products.json":
        raise BuildError("Productos requiere el registro comercial canónico vacío")


def validate_home_preview_entries(entries: list[dict[str, str]], components: list[str]) -> None:
    actual = {(entry["source"], entry["output"], entry["kind"]) for entry in entries}
    if actual != CONNECTED_PREVIEW_ALLOWLIST or any(entry["root"] != "src" for entry in entries):
        raise BuildError("vista previa conjunta rechazada: entradas fuera de la allowlist explícita")
    if set(components) != HOME_PREVIEW_COMPONENTS or len(components) != len(HOME_PREVIEW_COMPONENTS):
        raise BuildError("vista previa conjunta rechazada: componentes fuera de la allowlist")
    routes = {entry["output"]: entry for entry in entries if entry["kind"] == "html"}
    if routes.get("index.html", {}).get("active") != "inicio" or routes.get("index.html", {}).get("variant") != "standard":
        raise BuildError("vista previa conjunta requiere Inicio con active=inicio")
    if routes.get("nosotros/index.html", {}).get("active") != "nosotros" or routes.get("nosotros/index.html", {}).get("variant") != "standard":
        raise BuildError("vista previa conjunta requiere Nosotros con active=nosotros")


def validate_connected_preview_entries(entries: list[dict[str, str]], components: list[str]) -> None:
    actual = {(entry["source"], entry["output"], entry["kind"]) for entry in entries}
    if actual != CONNECTED_PREVIEW_ALLOWLIST or any(entry["root"] != "src" for entry in entries):
        raise BuildError("vista previa conjunta rechazada: entradas fuera de la allowlist explícita")
    if set(components) != HOME_PREVIEW_COMPONENTS or len(components) != len(HOME_PREVIEW_COMPONENTS):
        raise BuildError("vista previa conjunta rechazada: componentes fuera de la allowlist")
    routes = {entry["output"]: entry for entry in entries if entry["kind"] == "html"}
    for output, active in (("index.html", "inicio"), ("nosotros/index.html", "nosotros"), ("servicios/index.html", "servicios")):
        if routes.get(output, {}).get("active") != active or routes[output].get("variant") != "standard":
            raise BuildError("vista previa conjunta requiere Inicio, Nosotros y Servicios con cabecera global")
    detail_records = {entry.get("record"): entry["output"] for entry in entries if "record" in entry}
    if detail_records != SERVICE_DETAIL_IDS:
        raise BuildError("vista previa conjunta requiere exactamente las tres fichas aprobadas")
    if routes.get("productos/index.html", {}).get("active") != "productos" or routes["productos/index.html"].get("variant") != "standard":
        raise BuildError("vista previa conjunta requiere Productos con cabecera global")


def validate_product_demo_registry(repo: Path) -> list[dict[str, object]]:
    fixture_root = repo / "tests" / "fixtures" / "products-demo"
    try:
        records = json.loads(validate_source(fixture_root, "products-demo.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildError("no se pudo leer el fixture aislado de Productos") from error
    if not isinstance(records, list) or len(records) != len(PRODUCT_DEMO_IDS):
        raise BuildError("la vista previa requiere exactamente tres productos ficticios")
    seen: set[str] = set()
    declared = {f"assets/products/product-demo-{letter}{suffix}.svg" for letter in "abc" for suffix in ("", "-alt")}
    used: set[str] = set()
    for index, record in enumerate(records, 1):
        expected_id = f"demo-{index:02d}"
        if not isinstance(record, dict) or record.get("id") != expected_id or record.get("name") != f"Producto de prueba {index:02d}":
            raise BuildError("identificadores y nombres de Productos demo deben coincidir con la muestra fija")
        if record.get("group") != PRODUCT_DEMO_GROUPS[index - 1] or record.get("demo") is not True:
            raise BuildError("grupos y bandera de demostración de Productos no válidos")
        if record.get("detailPath") != f"productos/{expected_id}/" or not isinstance(record.get("gallery"), list) or len(record["gallery"]) < 2:
            raise BuildError("cada producto demo requiere ficha permitida y galería local")
        for asset in record["gallery"]:
            if asset not in declared or asset in used:
                raise BuildError("recurso fuera de la allowlist de Productos demo")
            validate_source(fixture_root, asset.rsplit("/", 1)[1])
            used.add(asset)
        seen.add(expected_id)
    if seen != set(PRODUCT_DEMO_IDS) or used != declared:
        raise BuildError("el fixture de Productos no usa exactamente las seis imágenes demo aprobadas")
    return records


def validate_empty_product_registry(src_root: Path) -> None:
    try:
        data = json.loads(validate_source(src_root, "catalog-data/products.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildError("no se pudo leer el registro comercial canónico de Productos") from error
    if data != []:
        raise BuildError("el registro comercial de Productos debe permanecer vacío hasta aprobación editorial")


def _no_symlink_components(root: Path, candidate: Path) -> None:
    root_abs = root.absolute()
    candidate_abs = candidate.absolute()
    try:
        relative = candidate_abs.relative_to(root_abs)
    except ValueError as error:
        raise BuildError("fuente fuera de la raíz permitida") from error
    current = root_abs
    if current.is_symlink():
        raise BuildError("raíz fuente simbólica no permitida")
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise BuildError(f"enlace simbólico en fuente: {part}")


def validate_source(root: Path, relative: str) -> Path:
    try:
        safe_rel = PurePosixPath(relative)
        if safe_rel.is_absolute() or any(part in {"", ".", ".."} for part in safe_rel.parts):
            raise BuildError("ruta fuente insegura")
        candidate = root.joinpath(*safe_rel.parts)
        _no_symlink_components(root, candidate)
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise BuildError(f"fuente inexistente o inaccesible: {relative}") from error
    if not resolved.is_file() or not candidate.is_file():
        raise BuildError(f"fuente no es un archivo regular: {relative}")
    return resolved


def validate_destination(output: Path, repo_root: Path) -> tuple[Path, Path]:
    if ".." in output.parts:
        raise BuildError("destino con traversal no permitido")
    requested = output.expanduser().absolute()
    parent = requested.parent
    if not parent.is_dir():
        raise BuildError("el directorio padre de salida debe existir")
    current = Path(requested.anchor)
    for part in requested.parts[1:-1]:
        current = current / part
        if current.is_symlink():
            raise BuildError("padre de salida contiene enlace simbólico")
    if requested.exists() or requested.is_symlink():
        raise BuildError("la ruta de salida ya existe; no se sobrescribe")
    resolved_parent = parent.resolve(strict=True)
    resolved_repo = repo_root.resolve(strict=True)
    if resolved_parent == resolved_repo or resolved_repo in resolved_parent.parents:
        raise BuildError("salida dentro del repositorio no permitida en esta fase")
    temporary_root = Path(tempfile.gettempdir()).resolve(strict=True)
    if resolved_parent == temporary_root or temporary_root not in resolved_parent.parents:
        raise BuildError("salida fuera de un directorio temporal dedicado")
    return requested, resolved_parent


def _load_inputs(repo: Path, mode: str) -> tuple[Path, Path, list[dict[str, str]], list[str]]:
    if mode in {"public", "preview-home", "preview-connected"}:
        manifest_path = repo / "src" / "site-manifest.json"
        source_root = repo / "src"
    else:
        fixture_root = repo / "tests" / "fixtures" / "build-minimal"
        manifest_path = fixture_root / "site-manifest.json"
        source_root = fixture_root
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise BuildError("no existe el manifiesto canónico para esta modalidad")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildError("no se pudo leer el JSON del manifiesto") from error
    entries = validate_manifest_data(data)
    components = validate_component_names(data)
    if mode == "public":
        validate_public_entries(entries)
        validate_empty_product_registry(repo / "src")
    if mode == "preview-home":
        validate_home_preview_entries(entries, components)
    if mode == "preview-connected":
        validate_connected_preview_entries(entries, components)
    if mode == "test" and any(entry["root"] == "src" and PurePosixPath(entry["source"]).parts[0] in {"tests", "tools", "docs"} for entry in entries):
        raise BuildError("modo técnico no puede importar fixtures o herramientas como fuentes canónicas")
    return source_root, repo / "src", entries, components


def _audit_component(name: str, content: str) -> None:
    if ANY_INCLUDE_PATTERN.search(content):
        raise BuildError(f"inclusión anidada o circular no permitida en componente: {name}")
    audit = _ComponentHTMLAudit()
    audit.feed(content)
    if audit.errors:
        raise BuildError(f"componente {name} rechazado: {'; '.join(audit.errors)}")


def _load_components(repo: Path, names: list[str]) -> tuple[dict[str, str], list[dict[str, str]]]:
    contents: dict[str, str] = {}
    records: list[dict[str, str]] = []
    for name in names:
        relative = COMPONENT_FILES[name]
        path = validate_source(repo / "src", relative)
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise BuildError(f"componente no UTF-8 o inaccesible: {name}") from error
        _audit_component(name, content)
        contents[name] = content
        records.append({"name": name, "source": f"src/{relative}", "sha256": sha256_file(path)})
    return contents, records


def compose_html(
    source: str,
    allowed_components: list[str],
    component_contents: dict[str, str],
    active: str | None,
    variant: str | None,
) -> str:
    """Expand only fixed component names and fixed route/variant tokens."""
    used: list[str] = []

    def include(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in allowed_components:
            raise BuildError(f"componente no declarado en manifiesto: {name}")
        if name not in component_contents:
            raise BuildError(f"componente inexistente: {name}")
        used.append(name)
        return component_contents[name]

    result = INCLUDE_PATTERN.sub(include, source)
    if ANY_INCLUDE_PATTERN.search(result):
        raise BuildError("marcador de inclusión desconocido o mal formado")

    if "{{header-variant}}" in result:
        if variant is None:
            variant = "standard"
        if variant not in HEADER_VARIANTS:
            raise BuildError("variante de cabecera no permitida")
        variant_class = " lc-site-header--detail" if variant == "service-detail" else ""
        result = result.replace("{{header-variant}}", variant_class)

    def active_token(match: re.Match[str]) -> str:
        token_type, route = match.groups()
        if route not in ACTIVE_ROUTES:
            raise BuildError(f"marcador de navegación no permitido: {route}")
        if active is None:
            raise BuildError("una cabecera compartida requiere active en la entrada")
        if token_type == "active":
            return " is-active" if active == route else ""
        return 'aria-current="page"' if active == route else ""

    result = ACTIVE_PATTERN.sub(active_token, result)
    if "{{active:" in result or "{{current:" in result or "{{header-variant}}" in result:
        raise BuildError("marcador de configuración no resuelto")
    return result


def validate_service_registry(src_root: Path, entries: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    """Load the canonical service registry and require exact, declared local assets."""
    data_path = src_root / "catalog-data" / "services.json"
    try:
        records = json.loads(validate_source(src_root, "catalog-data/services.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildError("no se pudo leer el registro canónico de Servicios") from error
    if not isinstance(records, list) or len(records) != 24:
        raise BuildError("el registro de Servicios debe contener exactamente 24 servicios")
    declared_assets = {
        entry["source"] for entry in entries
        if entry["kind"] == "asset" and entry["root"] == "src" and entry["source"].startswith("assets/services/")
        and entry["output"] == entry["source"]
    }
    ids: set[str] = set()
    counts = {"Cabello": 0, "Rostro": 0, "Uñas": 0, "Piel": 0}
    ready: dict[str, dict[str, object]] = {}
    for item in records:
        if not isinstance(item, dict):
            raise BuildError("cada servicio debe ser un objeto JSON")
        service_id = item.get("id")
        category = item.get("category")
        if not isinstance(service_id, str) or not re.fullmatch(r"[a-z0-9-]+", service_id) or service_id in ids:
            raise BuildError("identificador de servicio inválido o duplicado")
        if not isinstance(category, str) or category not in counts:
            raise BuildError(f"categoría no aprobada para {service_id}")
        if item.get("listed") is not True or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise BuildError(f"el servicio {service_id} debe estar listado y tener nombre")
        if not isinstance(item.get("variants"), list) or not all(isinstance(value, str) for value in item["variants"]):
            raise BuildError(f"variantes inválidas para {service_id}")
        if not isinstance(item.get("description"), list) or not all(isinstance(value, str) for value in item["description"]):
            raise BuildError(f"descripción inválida para {service_id}")
        if not isinstance(item.get("gallery"), list):
            raise BuildError(f"galería inválida para {service_id}")
        ids.add(service_id)
        counts[category] += 1
        status = item.get("detailStatus")
        cover = item.get("cover")
        gallery = item["gallery"]
        for asset in ([cover] if cover is not None else []) + gallery:
            if not isinstance(asset, str) or not re.fullmatch(r"assets/services/[a-z0-9-]+/[a-z0-9_-]+\.png", asset) or ".." in asset:
                raise BuildError(f"recurso no autorizado para {service_id}: {asset!r}")
            if asset not in declared_assets:
                raise BuildError(f"recurso de Servicios fuera de la allowlist: {asset}")
            validate_source(src_root, asset)
        if status == "ready":
            if service_id not in SERVICE_DETAIL_IDS or item.get("detailPath") != f"servicios/{service_id}/":
                raise BuildError(f"ficha no aprobada o ruta inválida para {service_id}")
            if not item["description"] or not isinstance(cover, str) or not gallery:
                raise BuildError(f"faltan contenido o imágenes en {service_id}")
            if not isinstance(item.get("imageAlt"), str) or not item["imageAlt"].strip():
                raise BuildError(f"falta texto alternativo para {service_id}")
            if not isinstance(item.get("whatsappMessage"), str) or not item["whatsappMessage"].strip():
                raise BuildError(f"falta mensaje aprobado para {service_id}")
            ready[service_id] = item
        elif status == "pending":
            if item.get("detailPath") is not None:
                raise BuildError(f"el servicio pendiente {service_id} no debe enlazar a una ficha")
        else:
            raise BuildError(f"estado de ficha inválido para {service_id}")
    if counts != {"Cabello": 8, "Rostro": 7, "Uñas": 6, "Piel": 3}:
        raise BuildError("los conteos de categorías de Servicios no coinciden con la taxonomía aprobada")
    if set(ready) != set(SERVICE_DETAIL_IDS):
        raise BuildError("solo Corte, Coloración y Henna tienen ficha aprobada")
    if declared_assets != SERVICE_ASSET_FILES:
        raise BuildError("la allowlist de recursos gráficos de Servicios no coincide con el inventario aprobado")
    if not any(entry["source"] == "catalog-data/services.json" and entry["output"] == "assets/services/services.json" and entry["kind"] == "asset" and entry["root"] == "src" for entry in entries):
        raise BuildError("el registro de Servicios debe estar declarado en el manifiesto")
    return ready


def render_service_detail(template: str, service: dict[str, object], base_path: str) -> str:
    """Render one approved static detail page from the shared template and data."""
    service_id = str(service["id"])
    name = str(service["name"])
    cover = str(service["cover"])
    gallery = [cover, *service["gallery"]]
    thumbs: list[str] = []
    for index, image_path in enumerate(gallery, 1):
        active = index == 1
        alt = str(service["imageAlt"]) if active else f"Ilustración de referencia {index} para {name}"
        src = escape_html(base_path + str(image_path), quote=True)
        escaped_alt = escape_html(alt, quote=True)
        active_class = ' class="is-active"' if active else ""
        thumbs.append(
            '<figure><button type="button" data-gallery-thumb '
            f'data-image-src="{src}" data-image-alt="{escaped_alt}" '
            f'aria-pressed="{str(active).lower()}" aria-label="Mostrar imagen {index} de {escape_html(name, quote=True)}"{active_class}>'
            f'<img src="{src}" width="1254" height="1254" alt="" loading="lazy" decoding="async">'
            f'<span class="lc-services-screen-reader">Imagen {index}</span></button></figure>'
        )
    descriptions = "".join(f"<p>{escape_html(paragraph)}</p>" for paragraph in service["description"])
    note = service.get("editorialNote", "")
    note_html = f'<p class="lc-service-detail__editorial-note">{escape_html(note)}</p>' if note else ""
    variants = " · ".join(service["variants"]) if service["variants"] else "Consulta los detalles del servicio"
    whatsapp = "https://api.whatsapp.com/send?" + urlencode({"phone": "573125973539", "text": service["whatsappMessage"]})
    values = {
        "DETAIL_META_DESCRIPTION": escape_html(f"Conoce el servicio de {name} de Light Color y consulta sus detalles.", quote=True),
        "DETAIL_TITLE": escape_html(name),
        "DETAIL_ID": escape_html(service_id, quote=True),
        "DETAIL_COVER": escape_html(base_path + cover, quote=True),
        "DETAIL_IMAGE_ALT": escape_html(service["imageAlt"], quote=True),
        "DETAIL_THUMBNAILS": "\n".join(thumbs),
        "DETAIL_CATEGORY": escape_html(service["category"]),
        "DETAIL_VARIANTS": escape_html(variants),
        "DETAIL_DESCRIPTION": descriptions,
        "DETAIL_EDITORIAL_NOTE": note_html,
        "DETAIL_WHATSAPP_URL": escape_html(whatsapp, quote=True),
    }
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    unresolved = re.search(r"\{\{DETAIL_[A-Z_]+\}\}", rendered)
    if unresolved:
        raise BuildError(f"token de ficha sin resolver: {unresolved.group(0)}")
    return rendered


def render_product_detail(template: str, product: dict[str, object], base_path: str) -> str:
    """Render a preview-only demo detail; it is never sourced by public mode."""
    product_id = str(product["id"])
    name = str(product["name"])
    gallery = [str(asset) for asset in product["gallery"]]
    thumbs: list[str] = []
    for index, asset in enumerate(gallery, 1):
        src = escape_html(base_path + asset, quote=True)
        active = index == 1
        thumbs.append(
            '<figure><button type="button" data-gallery-thumb '
            f'data-image-src="{src}" data-image-alt="Ilustración demo {index} para {escape_html(name, quote=True)}" '
            f'aria-pressed="{str(active).lower()}" aria-label="Mostrar ilustración {index} de {escape_html(name, quote=True)}"'
            f'{" class=\"is-active\"" if active else ""}>'
            f'<img src="{src}" width="800" height="800" alt="" loading="lazy" decoding="async">'
            f'<span class="lc-product-screen-reader">Imagen {index}</span></button></figure>'
        )
    values = {
        "PRODUCT_META_DESCRIPTION": escape_html("Ficha de demostración local; no es una oferta comercial.", quote=True),
        "PRODUCT_TITLE": escape_html(name),
        "PRODUCT_ID": escape_html(product_id, quote=True),
        "PRODUCT_COVER": escape_html(base_path + gallery[0], quote=True),
        "PRODUCT_IMAGE_ALT": escape_html(f"Ilustración de demostración para {name}", quote=True),
        "PRODUCT_THUMBNAILS": "\n".join(thumbs),
        "PRODUCT_GROUP": escape_html(str(product["group"])),
    }
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    unresolved = re.search(r"\{\{PRODUCT_[A-Z_]+\}\}", rendered)
    if unresolved:
        raise BuildError(f"token de ficha de Productos sin resolver: {unresolved.group(0)}")
    return rendered


def _render(
    entry: dict[str, str],
    source: Path,
    base_path: str,
    allowed_components: list[str],
    component_contents: dict[str, str],
    service_registry: dict[str, dict[str, object]] | None = None,
) -> tuple[bytes, list[str]]:
    used_components: list[str] = []
    raw = source.read_bytes()
    if entry["kind"] in TEXT_KINDS:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BuildError(f"recurso de texto no es UTF-8: {entry['source']}") from error
        if entry["kind"] == "html":
            record_id = entry.get("record")
            if record_id is not None:
                if service_registry is None or record_id not in service_registry:
                    raise BuildError("ficha de Servicios sin datos canónicos validados")
                text = render_service_detail(text, service_registry[record_id], base_path)
            markers = list(INCLUDE_PATTERN.finditer(text))
            if markers or ANY_INCLUDE_PATTERN.search(text):
                text = compose_html(
                    text, allowed_components, component_contents,
                    entry.get("active"), entry.get("variant"),
                )
                used_components = [match.group(1) for match in markers]
        elif ANY_INCLUDE_PATTERN.search(text):
            raise BuildError(f"los componentes solo pueden incluirse desde HTML: {entry['source']}")
        text = text.replace("{{base}}", base_path)
        if "{{base}}" in text:
            raise BuildError(f"placeholder de ruta no resuelto: {entry['source']}")
        if entry["kind"] == "html":
            audit = _PageProtocolAudit()
            audit.feed(text)
            if audit.errors:
                raise BuildError(f"HTML rechazado en {entry['source']}: {', '.join(sorted(set(audit.errors)))}")
        return text.encode("utf-8"), used_components
    return raw, used_components


def build(mode: str, base_path: str, output: Path, repo: Path) -> dict[str, object]:
    if mode not in {"test", "public", "preview-home", "preview-connected"}:
        raise BuildError("modalidad no permitida")
    base_path = validate_base_path(base_path)
    fixture_root, src_root, entries, component_names = _load_inputs(repo, mode)
    requested_output, parent = validate_destination(output, repo)
    component_contents, component_records = _load_components(repo, component_names)
    service_registry = validate_service_registry(src_root, entries) if any("record" in entry for entry in entries) else None
    product_demo_records = validate_product_demo_registry(repo) if mode == "preview-connected" else []

    resolved_sources: list[tuple[dict[str, str], Path]] = []
    for entry in entries:
        source_root = src_root if entry["root"] == "src" else fixture_root
        if mode == "preview-connected" and entry["output"] == "assets/products/products.json":
            demo_root = repo / "tests" / "fixtures" / "products-demo"
            resolved_sources.append(({"source": "products-demo.json", "output": entry["output"], "kind": "asset", "root": "fixture"}, validate_source(demo_root, "products-demo.json")))
        else:
            resolved_sources.append((entry, validate_source(source_root, entry["source"])))

    staged_files: dict[str, bytes] = {}
    used_by_output: dict[str, list[str]] = {}
    for entry, source in resolved_sources:
        output_name = entry["output"]
        if output_name in staged_files:
            raise BuildError(f"colisión de destino: {output_name}")
        staged_files[output_name], used_by_output[output_name] = _render(
            entry, source, base_path, component_names, component_contents, service_registry,
        )

    generated_entries: list[dict[str, str]] = []
    if mode == "preview-connected":
        demo_root = repo / "tests" / "fixtures" / "products-demo"
        for asset_name in PRODUCT_DEMO_ASSETS:
            output_name = "assets/products/" + asset_name
            source = validate_source(demo_root, asset_name)
            staged_files[output_name] = source.read_bytes()
            used_by_output[output_name] = []
            generated_entries.append({"source": asset_name, "output": output_name, "kind": "asset", "root": "fixture"})
        template_path = validate_source(src_root, "templates/product-detail.html")
        template = template_path.read_text(encoding="utf-8")
        for product in product_demo_records:
            output_name = PRODUCT_DEMO_ROUTES[str(product["id"])]
            raw = render_product_detail(template, product, base_path)
            html = compose_html(raw, component_names, component_contents, "productos", "standard")
            html = html.replace("{{base}}", base_path)
            if "{{base}}" in html:
                raise BuildError("placeholder sin resolver en ficha demo de Productos")
            audit = _PageProtocolAudit()
            audit.feed(html)
            if audit.errors:
                raise BuildError("ficha demo de Productos rechazada: " + ", ".join(sorted(set(audit.errors))))
            staged_files[output_name] = html.encode("utf-8")
            used_by_output[output_name] = ["favicon", "header", "footer", "whatsapp"]
            generated_entries.append({"source": "templates/product-detail.html", "output": output_name, "kind": "html", "root": "src"})

    inventory = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in sorted(staged_files.items())
    }
    build_record = {
        "schema_version": 1,
        "mode": mode,
        "base_path": base_path,
        "files": [
            {
                "path": entry["output"],
                "kind": entry["kind"],
                "source": entry["source"],
                "root": entry["root"],
                "sha256": inventory[entry["output"]],
                "components": used_by_output[entry["output"]],
                "validated": True,
                **({"record": entry["record"]} if "record" in entry else {}),
            }
        for entry, _source in sorted([*resolved_sources, *((entry, Path(".")) for entry in generated_entries)], key=lambda pair: pair[0]["output"])
        ],
        "components": component_records,
    }
    inventory_bytes = (json.dumps(build_record, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    staged_files["build-manifest.json"] = inventory_bytes
    expected = {name: hashlib.sha256(content).hexdigest() for name, content in staged_files.items()}

    stage = Path(tempfile.mkdtemp(prefix=".light-color-build-", dir=parent))
    output_created = False
    try:
        for name, content in staged_files.items():
            destination = stage.joinpath(*PurePosixPath(name).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        errors = validate_output_tree(stage, expected, allow_demo=(mode == "preview-connected"))
        if errors:
            raise BuildError("auditoría de salida falló: " + "; ".join(errors))
        # mkdir is exclusive: never replace a destination that appeared after
        # the initial check. The output directory is created only after the
        # staged tree has passed its full audit.
        requested_output.mkdir()
        output_created = True
        (requested_output / ".BUILDING").write_text("incomplete\n", encoding="ascii")
        children = sorted(stage.iterdir(), key=lambda child: (child.name == "build-manifest.json", child.name))
        manifest_child = None
        for child in children:
            if child.name == "build-manifest.json":
                manifest_child = child
                continue
            target = requested_output / child.name
            if target.exists() or target.is_symlink():
                raise BuildError(f"el destino cambió durante la construcción: {target.name}")
            child.rename(target)
        (requested_output / ".BUILDING").unlink()
        if manifest_child is None:
            raise BuildError("falta el manifiesto de salida generado")
        manifest_child.rename(requested_output / "build-manifest.json")
        stage.rmdir()
        final_errors = validate_output_tree(requested_output, expected, allow_demo=(mode == "preview-connected"))
        if final_errors:
            raise BuildError("auditoría final falló: " + "; ".join(final_errors))
    except Exception:
        if stage.exists() and stage.parent == parent and stage.name.startswith(".light-color-build-"):
            shutil.rmtree(stage)
        if output_created and requested_output.is_dir() and requested_output.parent == parent:
            # This directory was created only after validation by this process.
            shutil.rmtree(requested_output)
        raise
    return {"output": str(requested_output), "mode": mode, "files": len(staged_files), "base_path": base_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("test", "public", "preview-home", "preview-connected"), required=True)
    parser.add_argument("--base-path", default="/")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    try:
        result = build(args.mode, args.base_path, args.output, repo)
    except (BuildError, OSError) as error:
        print(f"BUILD RECHAZADO: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
