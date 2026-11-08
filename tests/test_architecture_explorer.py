from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from tara_app.architecture_explorer import ArchitectureExplorer, main, to_mermaid


class ArchitectureExplorerTests(unittest.TestCase):
    def test_extracts_python_symbols_and_internal_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg/__init__.py").write_text("from .service import Service\n", encoding="utf-8")
            (root / "pkg/service.py").write_text(
                "import os\nclass Service:\n    def run(self):\n        return os.getcwd()\n",
                encoding="utf-8",
            )

            graph = ArchitectureExplorer(root).scan()

            names = {item["name"] for item in graph["symbols"]}
            self.assertIn("Service", names)
            self.assertIn("run", names)
            self.assertEqual(graph["summary"]["files"], 2)
            self.assertEqual(graph["summary"]["dependencies"], 1)

    def test_resolves_absolute_imports_in_src_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src/tara_app").mkdir(parents=True)
            (root / "src/tara_app/__init__.py").write_text("", encoding="utf-8")
            (root / "src/tara_app/runtime.py").write_text("class Runtime: pass\n", encoding="utf-8")
            (root / "src/tara_app/app.py").write_text("from tara_app.runtime import Runtime\n", encoding="utf-8")

            graph = ArchitectureExplorer(root).scan()

            self.assertEqual(graph["summary"]["dependencies"], 1)


    def test_resolves_module_less_python_relative_imports(self):
        """Resolve Python relative imports that omit the module name."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg/__init__.py").write_text("", encoding="utf-8")
            (root / "pkg/user.py").write_text("from . import sibling\n", encoding="utf-8")
            (root / "pkg/sibling.py").write_text("class Sibling: pass\n", encoding="utf-8")

            graph = ArchitectureExplorer(root).scan()

            self.assertEqual(graph["summary"]["dependencies"], 1)
            self.assertEqual(graph["edges"][0]["target"], "file:pkg/sibling.py")

    def test_resolves_dotted_relative_typescript_filenames(self):
        """Resolve relative TypeScript imports with dotted basenames."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/app.ts").write_text('import "./foo.bar";\n', encoding="utf-8")
            (root / "src/foo.bar.ts").write_text("export const value = 1;\n", encoding="utf-8")

            graph = ArchitectureExplorer(root).scan()

            self.assertEqual(graph["summary"]["dependencies"], 1)
            self.assertEqual(graph["edges"][0]["target"], "file:src/foo.bar.ts")

    def test_cli_refuses_to_overwrite_scanned_source_files(self):
        """Prevent CLI output from overwriting a scanned source file."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "app.py"
            original = "class App: pass\n"
            source.write_text(original, encoding="utf-8")
            mermaid = root / "architecture.mmd"
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                result = main([
                    str(root),
                    "--json", str(source),
                    "--mermaid", str(mermaid),
                ])

            self.assertEqual(result, 2)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertFalse(mermaid.exists())
            self.assertIn("must not overwrite scanned source files", stderr.getvalue())

    def test_extracts_typescript_symbols_and_relative_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/app.ts").write_text(
                'import { helper } from "./utils";\nexport class App {}\nexport const start = () => helper();\n',
                encoding="utf-8",
            )
            (root / "src/utils.ts").write_text("export function helper() {}\n", encoding="utf-8")

            graph = ArchitectureExplorer(root).scan()

            names = {item["name"] for item in graph["symbols"]}
            self.assertTrue({"App", "start", "helper"}.issubset(names))
            self.assertEqual(graph["summary"]["dependencies"], 1)

    def test_extracts_cpp_includes_and_types(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/main.cpp").write_text('#include "engine.h"\nint main() { return 0; }\n', encoding="utf-8")
            (root / "src/engine.h").write_text("class Engine {};\n", encoding="utf-8")

            graph = ArchitectureExplorer(root).scan()

            names = {item["name"] for item in graph["symbols"]}
            self.assertIn("Engine", names)
            self.assertEqual(graph["summary"]["dependencies"], 1)

    def test_ignores_generated_directories_and_symlinked_sources(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "node_modules/pkg").mkdir(parents=True)
            (root / "node_modules/pkg/vendor.py").write_text("class Vendor: pass\n", encoding="utf-8")
            external = Path(outside) / "external.py"
            external.write_text("class External: pass\n", encoding="utf-8")
            link = root / "src/external.py"
            try:
                link.symlink_to(external)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable")
            (root / "src/app.py").write_text("class App: pass\n", encoding="utf-8")

            graph = ArchitectureExplorer(root).scan()

            self.assertEqual(graph["summary"]["files"], 1)
            self.assertNotIn("External", {item["name"] for item in graph["symbols"]})

    def test_invalid_python_is_reported_without_aborting_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
            (root / "valid.py").write_text("class Valid: pass\n", encoding="utf-8")

            graph = ArchitectureExplorer(root).scan()

            self.assertEqual(graph["summary"]["files"], 2)
            self.assertEqual(graph["summary"]["diagnostics"], 1)
            self.assertIn("Valid", {item["name"] for item in graph["symbols"]})

    def test_mermaid_ids_do_not_collide_for_similar_paths(self):
        graph = {
            "nodes": [
                {"id": "file:src/a_b.py", "kind": "file", "path": "src/a_b.py"},
                {"id": "file:src/a/b.py", "kind": "file", "path": "src/a/b.py"},
            ],
            "edges": [],
        }

        rendered = to_mermaid(graph)
        identifiers = [
            line.strip().split("[", 1)[0]
            for line in rendered.splitlines()
            if "[" in line
        ]

        self.assertEqual(len(identifiers), 2)
        self.assertEqual(len(set(identifiers)), 2)

    def test_mermaid_output_contains_file_nodes_and_edges(self):
        graph = {
            "nodes": [
                {"id": "file:src/a.py", "kind": "file", "path": "src/a.py"},
                {"id": "file:src/b.py", "kind": "file", "path": "src/b.py"},
            ],
            "edges": [{"source": "file:src/a.py", "target": "file:src/b.py", "kind": "imports"}],
        }

        rendered = to_mermaid(graph)

        self.assertIn("flowchart LR", rendered)
        self.assertIn("src_a_py", rendered)
        self.assertIn("-->|imports|", rendered)


if __name__ == "__main__":
    unittest.main()
