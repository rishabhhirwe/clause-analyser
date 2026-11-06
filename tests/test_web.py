"""The connector online: the same tools over HTTPS, with PDFs handled by the card's button only."""
import asyncio
import importlib
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import dispute_clause_analyzer.server as server_module

ROOT = Path(__file__).parents[1]
HOST = "clause-analyser.example.test"
CLAUSE = (ROOT / "tests" / "fixtures" / "clauses" / "unilateral_lender_nominates.txt").read_text(encoding="utf-8")
ACCEPT = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
LOCAL_ONLY_TOOLS = {"save_report_pdf", "save_portfolio_pdf", "download_status"}


@pytest.fixture
def online(monkeypatch, tmp_path):
    """Load the server in online mode, as the hosting service runs it; put local mode back afterwards."""
    monkeypatch.setenv("CLAUSE_ANALYSER_MODE", "online")
    monkeypatch.setenv("PUBLIC_HOST", HOST)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000")
    monkeypatch.setenv("CLAUSE_ANALYSER_DOWNLOAD_DIR", str(tmp_path))
    tools = importlib.reload(server_module)
    web = importlib.reload(importlib.import_module("dispute_clause_analyzer.web"))
    yield web
    monkeypatch.delenv("CLAUSE_ANALYSER_MODE")
    importlib.reload(server_module)


def _message(response) -> dict:
    """The JSON-RPC message in a reply, whether it came back as JSON or as a server-sent event."""
    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json()
    data = [line[5:].strip() for line in response.text.splitlines() if line.startswith("data:")]
    return json.loads(data[-1])


class Session:
    """A minimal MCP client over the HTTP transport."""

    def __init__(self, client: TestClient):
        self.client = client
        self.headers = dict(ACCEPT)
        reply = self.client.post("/mcp", headers=self.headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}})
        assert reply.status_code == 200, reply.text
        self.headers["mcp-session-id"] = reply.headers["mcp-session-id"]
        self.client.post("/mcp", headers=self.headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.next_id = 2

    def call(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        reply = self.client.post("/mcp", headers=self.headers,
                                 json={"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}})
        assert reply.status_code == 200, reply.text
        return _message(reply)["result"]

    def tool(self, name: str, arguments: dict) -> dict:
        result = self.call("tools/call", {"name": name, "arguments": arguments})
        assert not result.get("isError"), result
        return result.get("structuredContent") or json.loads(result["content"][0]["text"])


@pytest.fixture
def client(online):
    with TestClient(online.create_app(), base_url=f"https://{HOST}") as test_client:
        yield test_client


def test_health_page_answers(client):
    reply = client.get("/health")

    assert reply.status_code == 200 and reply.json() == {"status": "ok"}


def test_online_tools_work_and_leave_out_saving_to_a_downloads_folder(client):
    names = {tool["name"] for tool in Session(client).call("tools/list")["tools"]}

    assert {"rate_clause", "show_report_card", "show_portfolio", "suggest_better_clause"} <= names
    assert not names & LOCAL_ONLY_TOOLS


def test_rating_over_the_internet_matches_the_rules(client):
    result = Session(client).tool("rate_clause", {"clause_text": CLAUSE})

    assert result["rating"] == 2 and result["type"] == "unilateral"


def test_card_and_dashboard_know_they_are_online(client):
    session = Session(client)

    assert session.tool("show_report_card", {"clause_text": CLAUSE})["hosted"] is True
    assert session.tool("show_portfolio", {"agreements": [{"clause_text": CLAUSE}]})["hosted"] is True


def test_download_button_pdf_is_returned_but_never_saved_on_the_server(client, tmp_path):
    result = Session(client).tool("download_report_pdf", {"original_arguments": {"clause_text": CLAUSE}, "save": True})

    assert result["pdf_base64"] and result["saved_to"] is None
    assert list(tmp_path.iterdir()) == []


def test_requests_for_an_unknown_address_are_refused(online):
    with TestClient(online.create_app(), base_url="https://evil.example.test") as other:
        reply = other.post("/mcp", headers=ACCEPT, json={"jsonrpc": "2.0", "id": 1, "method": "ping"})

    assert reply.status_code == 421


def test_too_many_requests_from_one_person_are_slowed_down(online, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    with TestClient(online.create_app(), base_url=f"https://{HOST}") as limited:
        codes = [limited.post("/mcp", headers=ACCEPT, json={"jsonrpc": "2.0", "id": n, "method": "ping"}).status_code
                 for n in range(3)]

    assert codes[-1] == 429
    assert limited.get("/health").status_code == 200


def test_people_behind_the_hosting_proxy_are_counted_separately(online, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    with TestClient(online.create_app(), base_url=f"https://{HOST}") as limited:
        first = limited.post("/mcp", headers={**ACCEPT, "x-forwarded-for": "1.1.1.1"}, json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        second = limited.post("/mcp", headers={**ACCEPT, "x-forwarded-for": "2.2.2.2"}, json={"jsonrpc": "2.0", "id": 2, "method": "ping"})

    assert first.status_code != 429 and second.status_code != 429


def test_online_mode_needs_its_public_address(online, monkeypatch):
    monkeypatch.delenv("PUBLIC_HOST")

    with pytest.raises(RuntimeError, match="PUBLIC_HOST"):
        online.create_app()


def test_online_instructions_point_to_the_download_button(online):
    instructions = server_module.server.instructions

    assert "Download PDF button" in instructions
    assert "Downloads folder" not in instructions and "save_report_pdf" not in instructions


def test_local_mode_is_unchanged():
    tools = importlib.reload(server_module)
    names = {t.name for t in asyncio.run(tools.server.list_tools())}

    assert LOCAL_ONLY_TOOLS <= names
    assert "save_report_pdf" in tools.server.instructions
    assert tools.HOSTED is False


def test_every_tool_has_a_title_and_says_whether_it_changes_anything():
    for tool in asyncio.run(importlib.reload(server_module).server.list_tools()):
        assert tool.annotations and tool.annotations.title, tool.name
        assert tool.annotations.read_only_hint is not None, tool.name


def test_card_handles_the_online_download_without_checking_the_users_disk():
    html = (ROOT / "src" / "dispute_clause_analyzer" / "ui" / "report-card.html").read_text(encoding="utf-8")
    download = html[html.index("function downloadPdf("):html.index("function pdfButton(")]

    assert ".hosted" in download


def test_hosting_files_run_the_online_mode():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "CLAUSE_ANALYSER_MODE=online" in docker and "clause-analyser-web" in docker
    assert "healthCheckPath: /health" in render and "PUBLIC_HOST" in render


def test_readme_has_a_privacy_policy():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "## Privacy Policy" in readme
    assert "not stored" in readme


def test_online_connector_shows_the_presolv360_icon(client):
    reply = client.post("/mcp", headers=ACCEPT, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}})
    info = _message(reply)["result"]["serverInfo"]

    assert info["icons"][0]["src"] == f"https://{HOST}/icon.png"
    assert info["icons"][0]["mimeType"] == "image/png"
    for path in ("/icon.png", "/favicon.ico"):
        image = client.get(path)
        assert image.status_code == 200 and image.headers["content-type"] == "image/png"
        assert image.content.startswith(b"\x89PNG")


def test_icon_ships_inside_the_package():
    assert (ROOT / "src" / "dispute_clause_analyzer" / "ui" / "icon.png").read_bytes().startswith(b"\x89PNG")
