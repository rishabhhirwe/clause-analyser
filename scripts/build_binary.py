"""Builds the self-contained program for the computer this runs on (dist-bin/clause-analyser or .exe).

Run: .venv/bin/python -m scripts.build_binary
Python and every library the tool needs are packed inside, so the user installs nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]
PROGRAM_NAME = "clause-analyser"
OPTIONS = (
    "--onefile",
    "--collect-data", "dispute_clause_analyzer",
    "--collect-data", "reportlab",
    "--collect-submodules", "mcp.server",
    "--collect-submodules", "mcp.shared",
    "--collect-submodules", "mcp.types",
)


def build() -> Path:
    PyInstaller.__main__.run([
        *OPTIONS, "--name", PROGRAM_NAME, "--distpath", str(ROOT / "dist-bin"),
        "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
        "--paths", str(ROOT / "src"), str(ROOT / "scripts" / "launcher.py"),
    ])
    return next((ROOT / "dist-bin").glob(f"{PROGRAM_NAME}*"))


if __name__ == "__main__":
    print(build())
    sys.exit(0)
