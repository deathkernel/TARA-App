"""Static source-code architecture extraction for TARA repositories.

The explorer is intentionally offline and read-only. It never imports or executes
project code; it parses Python with the standard-library AST and uses bounded,
best-effort syntax patterns for JavaScript/TypeScript and C/C++.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import posixpath
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_IGNORES = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "__pycache__",
    "node_modules", "dist", "build", "coverage", ".next", ".turbo",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "vendor",
}
SOURCE_SUFFIXES = {".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh"}
MAX_FILE_BYTES = 1_000_000
MAX_FILES = 20_000


@dataclass(frozen=True)
class Symbol:
    id: str
    name: str
    kind: str
    path: str
    line: int


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str


class ArchitectureExplorer:
    """Build a deterministic, read-only symbol and dependency graph."""

    def __init__(self, root: Path, *, max_files: int = MAX_FILES) -> None:
        self.root = root.resolve()
        self.max_files = max(1, min(max_files, MAX_FILES))

    def scan(self) -> dict[str, object]:
        """Scan supported source files and return a JSON-serializable graph."""
        if not self.root.is_dir():
            raise ValueError("repository root must be an existing directory")

        files = list(self._source_files())
        symbols: list[Symbol] = []
        edges: list[Edge] = []
        diagnostics: list[dict[str, str]] = []
        module_index: dict[str, str] = {}

        for path in files:
            relative = path.relative_to(self.root).as_posix()
            module_index[relative] = self._module_id(relative)

        for path in files:
            relative = path.relative_to(self.root).as_posix()
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                diagnostics.append({"path": relative, "message": f"source could not be read: {type(exc).__name__}"})
                continue

            try:
                found_symbols, imports = self._parse_file(relative, source)
                symbols.extend(found_symbols)
                for imported in imports:
                    target = self._resolve_import(relative, imported, module_index)
                    if target:
                        edges.append(Edge(self._module_id(relative), target, "imports"))
            except (SyntaxError, ValueError) as exc:
                diagnostics.append({"path": relative, "message": f"source parse incomplete: {type(exc).__name__}"})

        nodes = [
            {"id": self._module_id(path), "name": Path(path).name, "kind": "file", "path": path}
            for path in module_index
        ]
        nodes.extend(asdict(symbol) for symbol in symbols)
        return {
            "schema_version": 1,
            "root": str(self.root),
            "summary": {
                "files": len(files),
                "symbols": len(symbols),
                "dependencies": len(edges),
                "diagnostics": len(diagnostics),
            },
            "nodes": nodes,
            "edges": [asdict(edge) for edge in self._deduplicate_edges(edges)],
            "symbols": [asdict(symbol) for symbol in symbols],
            "diagnostics": diagnostics,
        }

    def _source_files(self) -> Iterable[Path]:
        """Yield bounded, supported source files without following symlinks."""
        count = 0
        for current, directories, filenames in os.walk(self.root, topdown=True, followlinks=False):
            current_path = Path(current)
            directories[:] = sorted(
                name for name in directories
                if name not in DEFAULT_IGNORES
                and not (current_path / name).is_symlink()
            )
            for filename in sorted(filenames):
                path = current_path / filename
                if path.is_symlink() or path.suffix.lower() not in SOURCE_SUFFIXES:
                    continue
                try:
                    if path.stat().st_size > MAX_FILE_BYTES:
                        continue
                except OSError:
                    continue
                yield path
                count += 1
                if count >= self.max_files:
                    return

    def _parse_file(self, relative: str, source: str) -> tuple[list[Symbol], list[str]]:
        """Dispatch source text to the parser for its file extension."""
        suffix = Path(relative).suffix.lower()
        if suffix in {".py", ".pyi"}:
            return self._parse_python(relative, source)
        if suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
            return self._parse_ecmascript(relative, source)
        return self._parse_cpp(relative, source)

    def _parse_python(self, relative: str, source: str) -> tuple[list[Symbol], list[str]]:
        """Extract Python declarations and statically declared imports."""
        tree = ast.parse(source, filename=relative)
        symbols: list[Symbol] = []
        imports: list[str] = []
        module = self._module_id(relative)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                symbols.append(Symbol(f"{module}::{node.name}", node.name, kind, relative, node.lineno))
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append("." * node.level + node.module)
                elif node.level:
                    imports.extend("." * node.level + alias.name for alias in node.names)
        return symbols, imports

    def _parse_ecmascript(self, relative: str, source: str) -> tuple[list[Symbol], list[str]]:
        """Extract common JavaScript/TypeScript declarations and imports."""
        symbols: list[Symbol] = []
        imports = re.findall(r"""(?:import|export)\s+(?:[^;]*?\s+from\s+)?["']([^"']+)["']""", source)
        patterns = (
            ("class", r"\bclass\s+([A-Za-z_$][\w$]*)"),
            ("function", r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\("),
            ("function", r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"),
        )
        module = self._module_id(relative)
        for kind, pattern in patterns:
            for match in re.finditer(pattern, source):
                line = source.count("\n", 0, match.start()) + 1
                name = match.group(1)
                symbols.append(Symbol(f"{module}::{name}", name, kind, relative, line))
        return symbols, imports

    def _parse_cpp(self, relative: str, source: str) -> tuple[list[Symbol], list[str]]:
        """Extract C/C++ type/function declarations and include paths."""
        symbols: list[Symbol] = []
        imports = re.findall(r'^\s*#\s*include\s*["<]([^">]+)[">]', source, re.MULTILINE)
        patterns = (
            ("class", r"\b(?:class|struct)\s+([A-Za-z_][\w]*)"),
            ("function", r"(?m)^\s*(?:[A-Za-z_][\w:<>,*&\s]+)\s+([A-Za-z_][\w]*)\s*\([^;{}]*\)\s*(?:const\s*)?\{"),
        )
        module = self._module_id(relative)
        for kind, pattern in patterns:
            for match in re.finditer(pattern, source):
                line = source.count("\n", 0, match.start()) + 1
                name = match.group(1)
                symbols.append(Symbol(f"{module}::{name}", name, kind, relative, line))
        return symbols, imports

    def _resolve_import(self, source_path: str, imported: str, modules: dict[str, str]) -> str | None:
        """Resolve a static import/include to a scanned repository file."""
        source_parent = Path(source_path).parent
        raw = imported.strip()
        if not raw or raw.startswith(("http://", "https://")):
            return None

        if raw.startswith(("./", "../")):
            base = posixpath.normpath((source_parent / raw).as_posix())
            return self._match_module_candidates(
                base,
                modules,
                allow_dotted_basename=Path(source_path).suffix.lower()
                in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"},
            )
        if raw.startswith("."):
            level = len(raw) - len(raw.lstrip("."))
            module_name = raw[level:].lstrip("/").replace(".", "/")
            parent = source_parent
            for _ in range(max(0, level - 1)):
                parent = parent.parent
            base = (parent / module_name).as_posix()
        elif "/" in raw or Path(raw).suffix.lower() in SOURCE_SUFFIXES:
            # C/C++ include paths and explicit file paths must preserve their
            # suffix (e.g. engine.h); replacing dots would corrupt the path.
            base = (source_parent / raw).as_posix()
        else:
            module_path = raw.replace(".", "/")
            candidates = [
                module_path,
                "src/" + module_path,
                (source_parent / module_path).as_posix(),
            ]
            for base in candidates:
                resolved = self._match_module_candidates(base, modules)
                if resolved:
                    return resolved
            return None

        return self._match_module_candidates(base, modules)

    @staticmethod
    def _match_module_candidates(
        base: str,
        modules: dict[str, str],
        *,
        allow_dotted_basename: bool = False,
    ) -> str | None:
        """Match exact files, language extensions, or package index files."""
        normalized = Path(base).as_posix()
        candidates = [normalized]
        suffix = Path(normalized).suffix.lower()
        if not suffix or (allow_dotted_basename and suffix not in SOURCE_SUFFIXES):
            for suffix in (
                ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs",
                ".ts", ".tsx", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh",
            ):
                candidates.append(normalized + suffix)
            for filename in (
                "__init__.py", "index.js", "index.jsx", "index.ts", "index.tsx",
            ):
                candidates.append(normalized + "/" + filename)
        for candidate in candidates:
            if candidate in modules:
                return modules[candidate]
        return None

    @staticmethod
    def _module_id(path: str) -> str:
        """Return a stable graph identifier for a repository-relative path."""
        return "file:" + path

    @staticmethod
    def _deduplicate_edges(edges: list[Edge]) -> list[Edge]:
        """Remove duplicate dependency edges and sort the remaining edges."""
        return sorted(set(edges), key=lambda edge: (edge.source, edge.target, edge.kind))


def _mermaid_id(raw: str) -> str:
    """Return a Mermaid-safe identifier with a stable collision-resistant suffix."""
    safe = re.sub(r"[^A-Za-z0-9_]", "_", raw)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"{safe}_{digest}"


def to_mermaid(graph: dict[str, object]) -> str:
    """Render file-level dependency edges as a Mermaid flowchart."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    file_nodes = [node for node in nodes if node.get("kind") == "file"]
    lines = ["flowchart LR"]
    for node in file_nodes:
        identifier = _mermaid_id(str(node["id"]))
        label = str(node["path"]).replace('"', "'")
        lines.append(f'    {identifier}["{label}"]')
    for edge in edges:
        source = _mermaid_id(str(edge["source"]))
        target = _mermaid_id(str(edge["target"]))
        lines.append(f"    {source} -->|imports| {target}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, scan a repository, and write graph outputs."""
    parser = argparse.ArgumentParser(prog="tara-architecture", description="Extract a source-code architecture graph without executing project code")
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd(), help="repository root to scan")
    parser.add_argument("--json", dest="json_path", type=Path, default=Path("tara-architecture.json"), help="JSON graph output path")
    parser.add_argument("--mermaid", type=Path, default=Path("tara-architecture.mmd"), help="Mermaid graph output path")
    parser.add_argument("--max-files", type=int, default=MAX_FILES, help="maximum source files to inspect")
    args = parser.parse_args(argv)

    try:
        graph = ArchitectureExplorer(args.root, max_files=args.max_files).scan()
        root = Path(graph["root"])
        source_paths = {
            (root / node["path"]).resolve()
            for node in graph["nodes"]
            if node.get("kind") == "file"
        }
        output_paths = {args.json_path.resolve(), args.mermaid.resolve()}
        if len(output_paths) != 2:
            raise ValueError("JSON and Mermaid output paths must be different")
        if output_paths & source_paths:
            raise ValueError("output paths must not overwrite scanned source files")
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.mermaid.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        args.mermaid.write_text(to_mermaid(graph), encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"Architecture scan failed: {exc}", file=sys.stderr)
        return 2

    summary = graph["summary"]
    print(f"Scanned {summary['files']} files; found {summary['symbols']} symbols and {summary['dependencies']} internal dependencies.")
    print(f"JSON: {args.json_path} | Mermaid: {args.mermaid}")
    if summary["diagnostics"]:
        print(f"Warnings: {summary['diagnostics']} file(s) could not be fully parsed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
