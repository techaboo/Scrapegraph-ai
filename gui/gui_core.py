"""Core scraping logic for the ScrapeGraphAI Streamlit GUI.

This module is intentionally free of any Streamlit imports so it can be
unit-tested without a running server. It wraps three library pipelines:

- ``SmartScraperGraph``      -> scrape a single URL with a prompt
- ``SmartScraperMultiGraph`` -> scrape several URLs at once with one prompt
- ``SearchGraph``            -> answer a natural-language question by searching
                                the web and scraping the top results

Every entry point returns a :class:`ScrapeResult` with a uniform shape so the
UI layer never touches graph internals.
"""

import asyncio
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from scrapegraphai.graphs import SearchGraph, SmartScraperGraph, SmartScraperMultiGraph

#: Modes supported by the GUI.
MODE_SINGLE = "single"
MODE_MULTI = "multi"
MODE_SEARCH = "search"

DEFAULT_MODEL = "ollama/glm-5.3-flash:cloud"
DEFAULT_BASE_URL = "http://localhost:11434"


@dataclass
class ScrapeResult:
    """Uniform result wrapper for all GUI scraping modes."""

    mode: str
    answer: Any
    considered_urls: List[str] = field(default_factory=list)
    site_results: List[Dict[str, Any]] = field(default_factory=list)
    execution_info: str = ""
    elapsed_seconds: float = 0.0


def parse_urls(text: str) -> List[str]:
    """Split free-form user input into a deduplicated list of URLs.

    Accepts one URL per line; commas and whitespace are also treated as
    separators so pasting a comma-separated list works too. Order is
    preserved and duplicates are removed.

    Args:
        text: Raw text from the multi-URL input box.

    Returns:
        A list of cleaned URL strings (possibly empty).
    """
    urls: List[str] = []
    for chunk in text.replace(",", "\n").splitlines():
        url = chunk.strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def is_valid_http_url(url: str) -> bool:
    """Check that a string is a well-formed http(s) URL.

    Args:
        url: The candidate URL.

    Returns:
        True when the URL parses with an http/https scheme and a host.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def invalid_urls(urls: List[str]) -> List[str]:
    """Return the subset of URLs that fail :func:`is_valid_http_url`."""
    return [url for url in urls if not is_valid_http_url(url)]


def build_graph_config(
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    temperature: float = 0.0,
    output_format: str = "json",
    max_results: Optional[int] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Assemble the graph configuration dict used by all three pipelines.

    Args:
        model: LangChain-style model identifier, e.g. ``ollama/...``.
        base_url: Base URL of the Ollama server.
        temperature: Sampling temperature for the LLM.
        output_format: ``json`` or ``text`` (Ollama needs this explicitly).
        max_results: Number of search hits to scrape (search mode only).
        verbose: Forward verbose logging to the graphs.

    Returns:
        A configuration dictionary ready for the graph constructors.
    """
    config: Dict[str, Any] = {
        "llm": {
            "model": model,
            "temperature": temperature,
            "format": output_format,
            "base_url": base_url,
        },
        "verbose": verbose,
    }
    if max_results is not None:
        config["max_results"] = max_results
    return config


def _run_graph_isolated(graph: Any) -> Any:
    """Run a graph in a worker thread with a Proactor event loop policy.

    Streamlit's Tornado server pins the main thread's asyncio event loop to
    SelectorEventLoop on Windows, which has no subprocess support. Playwright's
    async API needs to spawn a browser subprocess, which requires
    ProactorEventLoop. Running the scrape in its own thread with the policy
    forced to Proactor avoids clashing with Tornado's loop in the main thread.
    The policy is process-global, so the worker threads spawned internally by
    ``GraphIteratorNode`` (multi-URL and search modes) inherit it too.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return graph.run()


def _execute_graph(graph: Any, mode: str, started: float) -> ScrapeResult:
    """Execute a graph in the isolated thread and normalize its output."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        answer = pool.submit(_run_graph_isolated, graph).result()

    final_state = getattr(graph, "final_state", {}) or {}
    urls = list(final_state.get("urls", []) or [])
    raw_results = list(final_state.get("results", []) or [])

    site_results = [
        {"url": url, "result": result} for url, result in zip(urls, raw_results)
    ]

    try:
        execution_info = json.dumps(graph.get_execution_info(), indent=2, default=str)
    except Exception:  # noqa: BLE001 - execution info is best-effort only
        execution_info = str(getattr(graph, "execution_info", ""))

    return ScrapeResult(
        mode=mode,
        answer=answer,
        considered_urls=urls,
        site_results=site_results,
        execution_info=execution_info,
        elapsed_seconds=round(time.time() - started, 1),
    )


def run_single(prompt: str, url: str, config: Dict[str, Any]) -> ScrapeResult:
    """Scrape one URL with a natural-language prompt (SmartScraperGraph)."""
    started = time.time()
    graph = SmartScraperGraph(prompt=prompt, source=url, config=config)
    return _execute_graph(graph, MODE_SINGLE, started)


def run_multi(prompt: str, urls: List[str], config: Dict[str, Any]) -> ScrapeResult:
    """Scrape several URLs at once with one prompt (SmartScraperMultiGraph)."""
    started = time.time()
    graph = SmartScraperMultiGraph(prompt=prompt, source=urls, config=config)
    return _execute_graph(graph, MODE_MULTI, started)


def run_search(prompt: str, config: Dict[str, Any]) -> ScrapeResult:
    """Answer a natural-language question by searching and scraping the web
    (SearchGraph)."""
    started = time.time()
    graph = SearchGraph(prompt=prompt, config=config)
    return _execute_graph(graph, MODE_SEARCH, started)


def run_scrape(
    mode: str,
    prompt: str,
    config: Dict[str, Any],
    url: Optional[str] = None,
    urls: Optional[List[str]] = None,
) -> ScrapeResult:
    """Dispatch to the right pipeline for the requested mode.

    Args:
        mode: One of ``MODE_SINGLE``, ``MODE_MULTI`` or ``MODE_SEARCH``.
        prompt: The natural-language prompt / question.
        config: Graph configuration from :func:`build_graph_config`.
        url: Source URL (single mode).
        urls: Source URLs (multi mode).

    Returns:
        A normalized :class:`ScrapeResult`.

    Raises:
        ValueError: If the mode is unknown or required inputs are missing.
    """
    if mode == MODE_SINGLE:
        if not url:
            raise ValueError("A source URL is required for single-URL mode.")
        return run_single(prompt, url, config)
    if mode == MODE_MULTI:
        if not urls:
            raise ValueError("At least one URL is required for multi-URL mode.")
        return run_multi(prompt, urls, config)
    if mode == MODE_SEARCH:
        return run_search(prompt, config)
    raise ValueError(f"Unknown scrape mode: {mode!r}")
