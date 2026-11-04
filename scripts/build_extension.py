"""Builds the Claude Desktop extension file (dist/Clause-Analyser.mcpb) from the project.

Run: .venv/bin/python -m scripts.build_extension
The bundle holds only what the tool needs to run; tests, local files and caches are left out.
"""
from __future__ import annotations

import json
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_NAME = "Clause-Analyser.mcpb"
TOP_LEVEL_FILES = ("pyproject.toml", "LICENSE", "README.md")
SKIPPED_PARTS = ("__pycache__", ".egg-info")


def _version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def _manifest() -> str:
    manifest = json.loads((ROOT / "extension" / "manifest.json").read_text())
    return json.dumps({**manifest, "version": _version()}, indent=2) + "\n"


def _source_files() -> list[Path]:
    return sorted(
        path for path in (ROOT / "src").rglob("*")
        if path.is_file() and not any(part in str(path) for part in SKIPPED_PARTS)
    )


def build(out_dir: Path = ROOT / "dist") -> Path:
    """Write the extension file into out_dir and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / BUNDLE_NAME
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _manifest())
        for name in TOP_LEVEL_FILES:
            archive.write(ROOT / name, name)
        for path in _source_files():
            archive.write(path, path.relative_to(ROOT).as_posix())
    return bundle


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist"))
