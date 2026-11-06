# Source-Code Architecture Explorer

TARA's architecture explorer derives a repository graph from implementation files instead of treating README references as the architecture source of truth.

## What it extracts

- Python: classes, functions, async functions, and statically declared imports (using the standard-library AST parser).
- JavaScript/TypeScript: class declarations, named functions, arrow-function variables, and static import/export-from paths.
- C/C++: class/struct declarations, best-effort function definitions, and quoted/angle-bracket include paths.
- Internal file-to-file dependency edges when an import/include resolves to a supported file in the scanned repository.

The JavaScript/TypeScript and C/C++ extractors are intentionally best-effort syntax scanners, not full compiler frontends. Dynamic imports, macro expansion, generated code, package-manager resolution, and runtime dependency discovery are not inferred.

## Safety and limits

- Read-only: source files are never imported, executed, or modified.
- Offline: no model/API call and no network access.
- Symlinks are not followed; common virtualenv, dependency, build, and generated directories are pruned.
- Files larger than 1 MB are skipped; scans are capped at 20,000 source files by default.
- Parse failures are returned as diagnostics without aborting the whole scan.
- The output is a structural starting point, not a security audit or proof of runtime call relationships.

## Usage

Install TARA-App in editable mode, then run:

```powershell
python -m pip install -e .
tara-architecture .
```

Custom output paths:

```powershell
tara-architecture . --json artifacts/architecture.json --mermaid artifacts/architecture.mmd
```

The JSON output contains file nodes, symbol nodes, import/include edges, counts, and diagnostics. The Mermaid output is a file-level dependency view suitable for GitHub Markdown or Mermaid-compatible viewers.
