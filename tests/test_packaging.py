"""Packaging: the Claude Desktop extension file, built around a self-contained program for each computer type."""
import json
import tomllib
import zipfile
from pathlib import Path

import pytest

from scripts.build_extension import build

ROOT = Path(__file__).parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


@pytest.fixture
def programs(tmp_path) -> Path:
    folder = tmp_path / "programs"
    folder.mkdir()
    (folder / "clause-analyser").write_bytes(b"mac program")
    (folder / "clause-analyser.exe").write_bytes(b"windows program")
    return folder


def test_extension_holds_the_programs_and_nothing_private(tmp_path, programs):
    bundle = build(tmp_path / "out", programs)
    archive = zipfile.ZipFile(bundle)
    names = archive.namelist()

    assert bundle.name == "Clause-Analyser.mcpb"
    assert sorted(names) == ["LICENSE", "README.md", "manifest.json", "server/clause-analyser", "server/clause-analyser.exe"]
    assert archive.read("server/clause-analyser") == b"mac program"


def test_the_mac_program_keeps_its_permission_to_run(tmp_path, programs):
    archive = zipfile.ZipFile(build(tmp_path / "out", programs))

    assert (archive.getinfo("server/clause-analyser").external_attr >> 16) & 0o111


def test_manifest_runs_the_program_and_needs_nothing_installed(tmp_path, programs):
    manifest = json.loads(zipfile.ZipFile(build(tmp_path / "out", programs)).read("manifest.json"))
    server = manifest["server"]

    assert manifest["manifest_version"] == "0.4" and manifest["version"] == VERSION
    assert server["type"] == "binary"
    assert server["mcp_config"]["command"] == "${__dirname}/server/clause-analyser"
    assert server["mcp_config"]["platform_overrides"]["win32"]["command"] == "${__dirname}/server/clause-analyser.exe"
    assert manifest["compatibility"]["platforms"] == ["darwin", "win32"]
    assert "runtimes" not in manifest["compatibility"]
    assert manifest["license"] == "MIT"


def test_building_without_a_program_fails_clearly(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(FileNotFoundError, match="program"):
        build(tmp_path / "out", empty)


def test_github_builds_both_programs_and_the_extension_file():
    flow = (ROOT / ".github" / "workflows" / "build-extension.yml").read_text()

    assert "macos-latest" in flow and "windows-latest" in flow
    assert "scripts.build_binary" in flow and "scripts.build_extension" in flow
    assert "pytest" in flow
    assert "dist/Clause-Analyser.mcpb" in flow
    assert "contents: write" in flow


def test_only_the_extension_file_is_committed_from_dist():
    rules = (ROOT / ".gitignore").read_text().split()

    assert "dist/*" in rules and "!dist/Clause-Analyser.mcpb" in rules
    assert "dist-bin/" in rules and "build/" in rules


def test_the_terminal_plugin_is_gone():
    assert not (ROOT / ".claude-plugin").exists()
