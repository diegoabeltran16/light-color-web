"""Validation helpers for an explicitly enumerated static site output."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath


FORBIDDEN_PARTS = {
    ".git", ".aws", ".codex", ".agents", "r002", "r003",
    "tests", "fixtures", "tools", "commands", "wp-content", "wp-includes",
}
FORBIDDEN_NAMES = {".env", "id_rsa", "credentials", "secrets.json"}
FORBIDDEN_SUFFIXES = {".php", ".pem", ".key", ".p12", ".pfx"}
FORBIDDEN_TEXT = (
    "products-demo.json",
    'data-demo-mode="true"',
    "Producto de prueba",
    "Grupo de prueba",
    "product-demo-a.svg",
    "product-demo-b.svg",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 128), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_relative_output(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or any(ord(char) < 32 for char in value):
        raise ValueError("destino debe ser una ruta POSIX relativa")
    if re.match(r"^[a-zA-Z]:", value):
        raise ValueError("destino con prefijo de unidad no permitido")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"destino inseguro: {value!r}")
    if any(part.startswith(".") for part in path.parts):
        raise ValueError(f"destino oculto no permitido: {value!r}")
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
    if any(part.endswith((".", " ")) or part.split(".", 1)[0].lower() in reserved for part in path.parts):
        raise ValueError(f"nombre de destino no portable: {value!r}")
    if path.as_posix() != value:
        raise ValueError(f"destino no normalizado: {value!r}")
    return value


def validate_output_tree(root: Path, expected: dict[str, str], allow_demo: bool = False) -> list[str]:
    """Return errors if output is not exactly the generated allowlist."""
    errors: list[str] = []
    if not root.is_dir() or root.is_symlink():
        return ["la raíz de salida no es un directorio regular"]

    found: set[str] = set()
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        found.add(rel)
        parts_lower = {part.lower() for part in PurePosixPath(rel).parts}
        if parts_lower & FORBIDDEN_PARTS:
            errors.append(f"directorio prohibido en salida: {rel}")
        if path.is_symlink():
            errors.append(f"enlace simbólico en salida: {rel}")
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            errors.append(f"elemento que no es archivo en salida: {rel}")
            continue
        if path.name.lower() in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"archivo privado o ejecutable no permitido: {rel}")
        if rel not in expected:
            errors.append(f"archivo no declarado: {rel}")
            continue
        actual_hash = sha256_file(path)
        if expected[rel] != actual_hash:
            errors.append(f"hash no coincide con el inventario: {rel}")
        if path.suffix.lower() in {".html", ".css", ".js", ".json", ".svg", ".xml"}:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                errors.append(f"recurso de texto ilegible o no UTF-8: {rel}")
                continue
            if not allow_demo:
                for marker in FORBIDDEN_TEXT:
                    if marker in text:
                        errors.append(f"marcador demostrativo en {rel}")
                if re.search(r"producto-de-prueba-\d+|products-demo\.json|product-demo-[a-z0-9-]+\.svg", text, re.I):
                    errors.append(f"identificador demostrativo en {rel}")

    expected_paths = set(expected)
    for missing in sorted(expected_paths - found):
        errors.append(f"archivo autorizado ausente: {missing}")
    return errors
