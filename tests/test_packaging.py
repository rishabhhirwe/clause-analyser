"""Packaging: the Claude Desktop extension file and the Claude Code plugin."""
import json
import tomllib
import zipfile
from pathlib import Path

from scripts.build_extension import build

ROOT = Path(__file__).parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def test_extension_bundle_holds_the_tool_and_nothing_private(tmp_path):
    bundle = build(tmp_path)
    names = zipfile.ZipFile(bundle).namelist()

    assert bundle.name == "Clause-Analyser.mcpb"
    assert {"manifest.json", "pyproject.toml", "LICENSE", "README.md"} <= set(names)
    assert "src/dispute_clause_analyzer/server.py" in names
    assert "src/dispute_clause_analyzer/ui/report-card.html" in names
    for name in names:
        assert not name.startswith(("tests/", "_session-files/", ".venv/", ".git/")), name
        assert "__pycache__" not in name and not name.endswith((".pdf", ".docx")), name


def test_extension_manifest_runs_the_server_with_uv(tmp_path):
    manifest = json.loads(zipfile.ZipFile(build(tmp_path)).read("manifest.json"))

    assert manifest["manifest_version"] == "0.4"
    assert manifest["version"] == VERSION
    assert manifest["server"]["type"] == "uv"
    assert manifest["server"]["mcp_config"]["command"] == "uv"
    assert "${__dirname}" in manifest["server"]["mcp_config"]["args"]
    assert manifest["license"] == "MIT"
    assert (ROOT / manifest["server"]["entry_point"]).is_file()


def test_claude_code_plugin_and_marketplace_point_at_this_repo():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())

    assert plugin["name"] == "clause-analyser"
    assert plugin["version"] == VERSION
    server = plugin["mcpServers"]["dispute-clause-analyzer"]
    assert server["command"] == "uv" and "${CLAUDE_PLUGIN_ROOT}" in server["args"]
    assert market["name"] == "clause-analyser"
    assert market["plugins"][0]["name"] == "clause-analyser" and market["plugins"][0]["source"] == "./"


def test_build_output_is_kept_out_of_git():
    assert "dist/" in (ROOT / ".gitignore").read_text().split()
