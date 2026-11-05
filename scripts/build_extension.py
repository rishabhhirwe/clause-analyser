"""Builds the Claude Desktop extension file (dist/Clause-Analyser.mcpb).

The extension holds a self-contained program for each type of computer (see build_binary.py), so the
user installs nothing else. Run: .venv/bin/python -m scripts.build_extension [out_dir] [programs_dir]
"""
from __future__ import annotations

import json
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_NAME = "Clause-Analyser.mcpb"
TOP_LEVEL_FILES = ("LICENSE", "README.md")
ICON = "icon.png"  # the Presolv360 mark, shown next to the extension in Claude
RUNNABLE = 0o755 << 16  # the Mac program must keep its permission to run


def _version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def _manifest() -> str:
    manifest = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
    return json.dumps({**manifest, "version": _version()}, indent=2) + "\n"


def _programs(programs_dir: Path) -> list[Path]:
    found = sorted(path for path in programs_dir.glob("clause-analyser*") if path.is_file())
    if not found:
        raise FileNotFoundError(f"No program found in {programs_dir}. Build one first with scripts.build_binary.")
    return found


def build(out_dir: Path = ROOT / "dist", programs_dir: Path = ROOT / "dist-bin") -> Path:
    """Write the extension file into out_dir and return its path."""
    programs = _programs(programs_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / BUNDLE_NAME
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _manifest())
        for name in TOP_LEVEL_FILES:
            archive.write(ROOT / name, name)
        archive.write(ROOT / "extension" / ICON, ICON)
        for program in programs:
            info = zipfile.ZipInfo(f"server/{program.name}")
            info.external_attr = RUNNABLE
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, program.read_bytes())
    return bundle


if __name__ == "__main__":
    args = [Path(a) for a in sys.argv[1:]]
    print(build(*args))
