"""End-to-end UI tests for the Streamlit GUI (gui/scrapegraph_gui.py).

Uses streamlit.testing.v1.AppTest to execute the real app script headlessly.
Scraping itself is stubbed through ``gui_core.run_scrape`` so these tests are
fast and offline; real end-to-end scraping is covered separately by the
integration test in this file (marked ``integration``).
"""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUI_DIR = REPO_ROOT / "gui"
GUI_SCRIPT = GUI_DIR / "scrapegraph_gui.py"

sys.path.insert(0, str(GUI_DIR))

import gui_core  # noqa: E402

SCRAPE_LABEL = "⚡ Scrape"
EXTRACT_LABEL = "🎯 Extract"
SEARCH_LABEL = "🔎 Search"
CRAWL_LABEL = "🕸️ Crawl"


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
    # 4 operation modes
    assert len(app.radio) == 1
    assert set(app.radio[0].options) == {
        SCRAPE_LABEL,
        EXTRACT_LABEL,
        SEARCH_LABEL,
        CRAWL_LABEL,
    }
    # Submit button present
    assert any("SCRAPING" in b.label for b in app.button)
    # Default mode is Scrape: Target URL input rendered
    assert app.text_input(key="scrape_url").label == "Target URL"


def test_sidebar_controls_present():
    app = _make_app()
    assert app.text_input(key="model").value == gui_core.DEFAULT_MODEL
    assert app.text_input(key="base_url").value == gui_core.DEFAULT_BASE_URL
    assert app.slider(key="max_results").value == 3
    assert app.slider(key="crawl_depth").value == 1
    assert app.selectbox(key="output_format").value == "json"


def test_mode_switching_changes_inputs():
    app = _make_app()

    # Switch to Extract
    app.radio[0].set_value(EXTRACT_LABEL)
    app.run()
    assert not app.exception
    assert app.text_input(key="extract_url").label == "Target URL"
    assert app.text_area(key="extract_prompt").label == "Extraction Prompt"

    # Switch to Search
    app.radio[0].set_value(SEARCH_LABEL)
    app.run()
    assert not app.exception
    assert app.text_area(key="search_prompt").label == "Search Query & Prompt"

    # Switch to Crawl
    app.radio[0].set_value(CRAWL_LABEL)
    app.run()
    assert not app.exception
    assert app.text_area(key="crawl_urls").label == "Target URLs (one per line)"


def test_scrape_mode_validation():
    app = _make_app()
    # Default is Scrape, click run with empty URL
    app.button(key="run").click().run()
    assert not app.exception
    assert any("provide a target URL" in e.value for e in app.error)


def test_extract_mode_requires_prompt_and_valid_url():
    app = _make_app()
    app.radio[0].set_value(EXTRACT_LABEL)
    app.run()
    app.text_input(key="extract_url").set_value("not-a-url")
    app.button(key="run").click().run()
    assert not app.exception
    assert any("not a valid http(s) URL" in e.value for e in app.error)


def test_crawl_url_live_validation_warns():
    app = _make_app()
    app.radio[0].set_value(CRAWL_LABEL)
    app.run()
    app.text_area(key="crawl_urls").set_value(
        "https://example.com\nbogus-url\nhttps://iana.org"
    )
    app.run()
    assert any("bogus-url" in w.value for w in app.warning)
    assert any("2 valid URL(s)" in c.value for c in app.caption)


def test_successful_scrape_run_renders_results(monkeypatch):
    monkeypatch.setattr(
        gui_core, "run_scrape", lambda **kwargs: _fake_result(kwargs["mode"])
    )
    app = _make_app()
    app.text_input(key="scrape_url").set_value("https://example.com")
    app.button(key="run").click().run()

    assert not app.exception
    assert not app.error
    assert any(s.value == "Result Output" for s in app.subheader)
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Duration"] == "1.5s"

    downloads = {b.label for b in app.get("download_button")}
    assert "⬇️ Download JSON" in downloads
    assert "⬇️ Download CSV" in downloads

    assert len(app.session_state["history"]) == 1


def test_scrape_failure_surfaces_error(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("LLM backend unreachable")

    monkeypatch.setattr(gui_core, "run_scrape", boom)
    app = _make_app()
    app.text_input(key="scrape_url").set_value("https://example.com")
    app.button(key="run").click().run()

    assert not app.exception
    assert any("LLM backend unreachable" in e.value for e in app.error)


def test_clear_history_button(monkeypatch):
    monkeypatch.setattr(
        gui_core, "run_scrape", lambda **kwargs: _fake_result(kwargs["mode"])
    )
    app = _make_app()
    app.text_input(key="scrape_url").set_value("https://example.com")
    app.button(key="run").click().run()
    assert len(app.session_state["history"]) == 1

    app.button(key="clear_history").click().run()
    assert not app.exception
    assert app.session_state["history"] == []
