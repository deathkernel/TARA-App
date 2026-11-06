from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tara_app.architecture_explorer import ArchitectureExplorer, to_mermaid


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
