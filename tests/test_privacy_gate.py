"""The card and dashboard hide the results until the person confirms personal data was removed (DPDP Act)."""
from dispute_clause_analyzer.report_card import load_card_html
from dispute_clause_analyzer.rulebook import load_rulebook

CONFIRM = "I confirm that all personal information has been redacted."


def test_card_shows_the_warning_and_checkbox_before_any_result():
    html = load_card_html()
    render = html[html.index("  function render() {"):html.index("if (window.ResizeObserver)")]

    assert "function privacyGate(" in html
    assert CONFIRM in html
    assert 'type = "checkbox"' in html or "type: \"checkbox\"" in html or ".type = \"checkbox\"" in html
    assert "state.confirmed" in render


def test_the_gate_uses_the_approved_warning_text():
    warning = load_rulebook().warning

    assert warning.startswith("Warning - Please remove or redact all personal information")
    assert "DPDP Act" in warning


def test_claude_does_not_reveal_the_rating_before_the_box_is_ticked():
    text = load_rulebook().instructions

    assert "tick the confirmation on the card" in text
    assert "Do not state the rating" in text
