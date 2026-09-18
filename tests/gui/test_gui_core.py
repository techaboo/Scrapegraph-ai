"""Unit tests for the Streamlit GUI core logic (gui/gui_core.py).

gui_core is loaded by file path (the gui/ directory is not a package), so no
Streamlit import is required and these tests stay fast and offline.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

GUI_CORE_PATH = Path(__file__).resolve().parents[2] / "gui" / "gui_core.py"

spec = importlib.util.spec_from_file_location("gui_core", GUI_CORE_PATH)
gui_core = importlib.util.module_from_spec(spec)
sys.modules.setdefault("gui_core", gui_core)
spec.loader.exec_module(gui_core)


class TestParseUrls:
    def test_one_url_per_line(self):
        text = "https://example.com\nhttps://iana.org\n"
        assert gui_core.parse_urls(text) == [
            "https://example.com",
            "https://iana.org",
        ]

    def test_comma_separated(self):
        text = "https://example.com, https://iana.org"
        assert gui_core.parse_urls(text) == [
            "https://example.com",
            "https://iana.org",
        ]

    def test_strips_whitespace_and_ignores_blank_lines(self):
        text = "  https://example.com  \n\n   \nhttps://iana.org\t"
        assert gui_core.parse_urls(text) == [
            "https://example.com",
            "https://iana.org",
        ]

    def test_deduplicates_preserving_order(self):
        text = "https://a.com\nhttps://b.com\nhttps://a.com"
        assert gui_core.parse_urls(text) == ["https://a.com", "https://b.com"]

    def test_empty_input(self):
        assert gui_core.parse_urls("") == []
        assert gui_core.parse_urls("   \n , \n") == []


class TestIsValidHttpUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com",
            "http://example.com/path?q=1",
            "https://sub.example.co.uk:8080/x",
        ],
    )
    def test_valid_urls(self, url):
        assert gui_core.is_valid_http_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "example.com",
            "ftp://example.com",
            "https://",
            "not a url",
            "//example.com",
        ],
    )
    def test_invalid_urls(self, url):
        assert gui_core.is_valid_http_url(url) is False


class TestInvalidUrls:
    def test_filters_invalid(self):
        urls = ["https://ok.com", "bad", "http://also-ok.com", "nope"]
        assert gui_core.invalid_urls(urls) == ["bad", "nope"]


class TestBuildGraphConfig:
    def test_defaults(self):
        config = gui_core.build_graph_config()
        assert config["llm"]["model"] == gui_core.DEFAULT_MODEL
        assert config["llm"]["base_url"] == gui_core.DEFAULT_BASE_URL
        assert config["llm"]["temperature"] == 0.0
        assert config["llm"]["format"] == "json"
        assert config["verbose"] is False
        assert "max_results" not in config

    def test_max_results_only_when_set(self):
        config = gui_core.build_graph_config(max_results=5)
        assert config["max_results"] == 5

    def test_depth_only_when_greater_than_one(self):
        config1 = gui_core.build_graph_config(depth=1)
        assert "depth" not in config1
        config2 = gui_core.build_graph_config(depth=3)
        assert config2["depth"] == 3

    def test_custom_values(self):
        config = gui_core.build_graph_config(
            model="ollama/llama3",
            base_url="http://host:1",
            temperature=0.7,
            output_format="text",
            verbose=True,
        )
        assert config["llm"] == {
            "model": "ollama/llama3",
            "base_url": "http://host:1",
            "temperature": 0.7,
            "format": "text",
        }
        assert config["verbose"] is True


class TestRunScrapeDispatch:
    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown scrape mode"):
            gui_core.run_scrape("bogus", "prompt", {})

    def test_scrape_mode_requires_url(self):
        with pytest.raises(ValueError, match="target URL is required"):
            gui_core.run_scrape(gui_core.MODE_SCRAPE, config={})

    def test_extract_mode_requires_url_and_prompt(self):
        with pytest.raises(ValueError, match="source URL is required"):
            gui_core.run_scrape(gui_core.MODE_EXTRACT, prompt="prompt", config={})
        with pytest.raises(ValueError, match="prompt is required"):
            gui_core.run_scrape(
                gui_core.MODE_EXTRACT, url="https://example.com", config={}
            )

    def test_crawl_mode_requires_urls(self):
        with pytest.raises(ValueError, match="At least one URL"):
            gui_core.run_scrape(
                gui_core.MODE_CRAWL, prompt="prompt", config={}, urls=[]
            )

    def test_search_mode_requires_query(self):
        with pytest.raises(ValueError, match="search query or prompt is required"):
            gui_core.run_scrape(gui_core.MODE_SEARCH, prompt="", config={})

    def test_scrape_mode_delegates(self, monkeypatch):
        sentinel = object()
        monkeypatch.setattr(
            gui_core, "run_scrape_markdown", lambda url, config: sentinel
        )
        result = gui_core.run_scrape(
            gui_core.MODE_SCRAPE, url="https://example.com", config={"x": 1}
        )
        assert result is sentinel

    def test_extract_mode_delegates(self, monkeypatch):
        sentinel = object()
        calls = {}

        def fake_run_extract(prompt, url, config):
            calls.update(prompt=prompt, url=url, config=config)
            return sentinel

        monkeypatch.setattr(gui_core, "run_extract", fake_run_extract)
        result = gui_core.run_scrape(
            gui_core.MODE_EXTRACT,
            prompt="p",
            config={"x": 1},
            url="https://example.com",
        )
        assert result is sentinel
        assert calls == {
            "prompt": "p",
            "url": "https://example.com",
            "config": {"x": 1},
        }

    def test_crawl_mode_delegates(self, monkeypatch):
        sentinel = object()
        monkeypatch.setattr(
            gui_core,
            "run_crawl",
            lambda prompt, urls, config, depth: sentinel,
        )
        result = gui_core.run_scrape(
            gui_core.MODE_CRAWL, prompt="p", config={}, urls=["https://example.com"]
        )
        assert result is sentinel

    def test_search_mode_delegates(self, monkeypatch):
        sentinel = object()
        monkeypatch.setattr(gui_core, "run_search", lambda prompt, config: sentinel)
        result = gui_core.run_scrape(gui_core.MODE_SEARCH, prompt="p", config={})
        assert result is sentinel


class TestExecuteGraphNormalization:
    """_execute_graph should normalize any graph's final_state uniformly."""

    class _FakeGraph:
        def __init__(self, final_state):
            self.final_state = final_state
            self.execution_info = {"node": "ok"}

        def run(self):
            return self.final_state["answer"]

        def get_execution_info(self):
            return self.execution_info

    def test_normalizes_multi_site_state(self):
        graph = self._FakeGraph(
            {
                "answer": {"merged": True},
                "urls": ["https://a.com", "https://b.com"],
                "results": [{"a": 1}, {"b": 2}],
            }
        )
        result = gui_core._execute_graph(graph, gui_core.MODE_CRAWL, 0.0)
        assert result.mode == gui_core.MODE_CRAWL
        assert result.answer == {"merged": True}
        assert result.considered_urls == ["https://a.com", "https://b.com"]
        assert result.site_results == [
            {"url": "https://a.com", "result": {"a": 1}},
            {"url": "https://b.com", "result": {"b": 2}},
        ]
        assert "node" in result.execution_info

    def test_handles_missing_state_keys(self):
        graph = self._FakeGraph({"answer": "text answer"})
        result = gui_core._execute_graph(graph, gui_core.MODE_EXTRACT, 0.0)
        assert result.answer == "text answer"
        assert result.considered_urls == []
        assert result.site_results == []
