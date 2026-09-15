"""End-to-end UI tests for the Streamlit GUI (gui/scrapegraph_gui.py).

Uses streamlit.testing.v1.AppTest to execute the real app script headlessly.
Scraping itself is stubbed through ``gui_core.run_scrape`` so these tests are
fast and offline; real end-to-end scraping is covered separately by the
integration test in this file (marked ``integration``).
"""

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUI_DIR = REPO_ROOT / "gui"
GUI_SCRIPT = GUI_DIR / "scrapegraph_gui.py"

sys.path.insert(0, str(GUI_DIR))

import gui_core  # noqa: E402

SINGLE_LABEL = "🔗 Single URL"
MULTI_LABEL = "📚 Multiple URLs"
SEARCH_LABEL = "🔍 Web search (natural language)"


def _fake_result(mode: str) -> gui_core.ScrapeResult:
    return gui_core.ScrapeResult(
        mode=mode,
        answer={"title": "Example Domain"},
        considered_urls=["https://example.com", "https://iana.org"],
        site_results=[
            {"url": "https://example.com", "result": {"title": "Example Domain"}},
            {"url": "https://iana.org", "result": {"title": "IANA"}},
        ],
        execution_info='{"node": "ok"}',
        elapsed_seconds=1.5,
    )


def _make_app() -> AppTest:
    app = AppTest.from_file(str(GUI_SCRIPT), default_timeout=30)
    app.run()
    assert not app.exception
    return app


def test_app_loads_without_errors():
    app = _make_app()
    assert app.title[0].value == "🕷️ ScrapeGraphAI"
    # Mode picker with three options
    assert len(app.radio) == 1
    assert set(app.radio[0].options) == {SINGLE_LABEL, MULTI_LABEL, SEARCH_LABEL}
    # Run button present
    assert any(b.label == "🚀 Run" for b in app.button)
    # Default mode is search: prompt box rendered
    assert app.text_area[0].label == "Ask anything"


def test_sidebar_controls_present():
    app = _make_app()
    assert app.text_input(key="model").value == gui_core.DEFAULT_MODEL
    assert app.text_input(key="base_url").value == gui_core.DEFAULT_BASE_URL
    assert app.slider(key="max_results").value == 3
    assert app.selectbox(key="output_format").value == "json"


def test_mode_switching_changes_inputs():
    app = _make_app()
    app.radio[0].set_value(SINGLE_LABEL)
    app.run()
    assert not app.exception
    assert app.text_input(key="single_url").label == "Source URL"

    app.radio[0].set_value(MULTI_LABEL)
    app.run()
    assert not app.exception
    assert app.text_area(key="multi_urls").label == "Source URLs (one per line)"


def test_run_requires_prompt():
    app = _make_app()
    app.button(key="run").click().run()
    assert not app.exception
    assert any(
        "describe what you want" in e.value for e in app.error
    ), "expected a validation error for an empty prompt"


def test_single_url_requires_valid_url():
    app = _make_app()
    app.radio[0].set_value(SINGLE_LABEL)
    app.run()
    app.text_input(key="single_url").set_value("not-a-url")
    app.text_area(key="prompt_single").set_value("Summarize this page.")
    app.button(key="run").click().run()
    assert not app.exception
    assert any("not a valid http(s) URL" in e.value for e in app.error)


def test_multi_url_live_validation_warns():
    app = _make_app()
    app.radio[0].set_value(MULTI_LABEL)
    app.run()
    app.text_area(key="multi_urls").set_value(
        "https://example.com\nbogus-url\nhttps://iana.org"
    )
    app.run()
    assert any("bogus-url" in w.value for w in app.warning)
    # The readiness caption counts only valid URLs.
    assert any("2 valid URL(s) ready to scrape." in c.value for c in app.caption)


def test_successful_single_run_renders_results(monkeypatch):
    monkeypatch.setattr(
        gui_core, "run_scrape", lambda **kwargs: _fake_result(kwargs["mode"])
    )
    app = _make_app()
    app.radio[0].set_value(SINGLE_LABEL)
    app.run()
    app.text_input(key="single_url").set_value("https://example.com")
    app.text_area(key="prompt_single").set_value("What is the title?")
    app.button(key="run").click().run()

    assert not app.exception
    assert not app.error
    # Answer section + metrics
    assert any(s.value == "Answer" for s in app.subheader)
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Elapsed"] == "1.5s"
    # Per-site results and websites-used sections rendered
    assert any(s.value == "Per-site results" for s in app.subheader)
    # Download buttons (no dedicated AppTest accessor; use generic get)
    downloads = {b.label for b in app.get("download_button")}
    assert "⬇️ Download JSON" in downloads
    assert "⬇️ Download CSV" in downloads
    # History got one entry
    assert len(app.session_state["history"]) == 1
    assert app.session_state["history"][0]["prompt"] == "What is the title?"


def test_successful_search_run_shows_considered_urls(monkeypatch):
    monkeypatch.setattr(
        gui_core, "run_scrape", lambda **kwargs: _fake_result(kwargs["mode"])
    )
    app = _make_app()
    app.text_area(key="prompt_search").set_value("What is example.com for?")
    app.button(key="run").click().run()

    assert not app.exception
    assert not app.error
    assert any(s.value == "Answer" for s in app.subheader)
    assert any("Websites used (2)" in (e.label or "") for e in app.expander)


def test_scrape_failure_surfaces_error(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("LLM backend unreachable")

    monkeypatch.setattr(gui_core, "run_scrape", boom)
    app = _make_app()
    app.text_area(key="prompt_search").set_value("Anything")
    app.button(key="run").click().run()

    assert not app.exception
    assert any("LLM backend unreachable" in e.value for e in app.error)


def test_clear_history_button(monkeypatch):
    monkeypatch.setattr(
        gui_core, "run_scrape", lambda **kwargs: _fake_result(kwargs["mode"])
    )
    app = _make_app()
    app.text_area(key="prompt_search").set_value("Question?")
    app.button(key="run").click().run()
    assert len(app.session_state["history"]) == 1

    app.button(key="clear_history").click().run()
    assert not app.exception
    assert app.session_state["history"] == []


@pytest.mark.integration
def test_real_single_url_scrape_through_ui():
    """True end-to-end: the UI drives a real SmartScraperGraph scrape.

    Requires a live Ollama backend; run with ``pytest --integration``.
    """
    app = _make_app()
    app.radio[0].set_value(SINGLE_LABEL)
    app.run()
    app.text_input(key="single_url").set_value("https://example.com")
    app.text_area(key="prompt_single").set_value("What is the page title?")
    app.button(key="run").click().run()

    assert not app.exception
    assert not app.error
    assert any(s.value == "Answer" for s in app.subheader)
    result = app.session_state["last_result"]
    assert result.answer
    assert result.elapsed_seconds > 0
