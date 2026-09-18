"""Core scraping logic for the ScrapeGraphAI Streamlit GUI.

This module is intentionally free of any Streamlit imports so it can be
unit-tested without a running server. It exposes the 4 official ScrapeGraphAI
modalities matching the official scrapegraphai.com platform:

- ``MODE_SCRAPE``  -> Convert URL to clean markdown / structured HTML (MarkdownifyGraph)
- ``MODE_EXTRACT`` -> Extract structured data using natural language prompts (SmartScraperGraph)
- ``MODE_SEARCH``  -> Search the web and extract data from top results (SearchGraph)
- ``MODE_CRAWL``   -> Crawl websites and extract data across pages / depth (DepthSearchGraph / SmartScraperMultiGraph)

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
from scrapegraphai.graphs.depth_search_graph import DepthSearchGraph
from scrapegraphai.graphs.markdownify_graph import MarkdownifyGraph

#: Modes supported by the GUI (aligning with scrapegraphai.com hero actions)
MODE_SCRAPE = "scrape"
MODE_EXTRACT = "extract"
MODE_SEARCH = "search"
MODE_CRAWL = "crawl"

# Backwards compatibility aliases for previous internal names
MODE_SINGLE = MODE_EXTRACT
MODE_MULTI = MODE_CRAWL

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
    """
    urls: List[str] = []
    for chunk in text.replace(",", "\n").splitlines():
        url = chunk.strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def is_valid_http_url(url: str) -> bool:
    """Check that a string is a well-formed http(s) URL."""
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
    depth: int = 1,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Assemble the graph configuration dict used across pipelines."""
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
    if depth > 1:
        config["depth"] = depth
    return config


def _run_graph_isolated(
    graph: Any, initial_state: Optional[Dict[str, Any]] = None
) -> Any:
    """Run a graph in a worker thread with a Proactor event loop policy on Windows."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    if hasattr(graph, "run"):
        return graph.run()
    if hasattr(graph, "execute") and initial_state is not None:
        state, execution_info = graph.execute(initial_state)
        return state.get("markdown") or state
    raise ValueError(f"Unsupported graph object: {graph!r}")


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
    except Exception:  # noqa: BLE001
        execution_info = str(getattr(graph, "execution_info", ""))

    return ScrapeResult(
        mode=mode,
        answer=answer,
        considered_urls=urls,
        site_results=site_results,
        execution_info=execution_info,
        elapsed_seconds=round(time.time() - started, 1),
    )


def run_scrape_markdown(url: str, config: Dict[str, Any]) -> ScrapeResult:
    """Convert any URL to clean Markdown using MarkdownifyGraph."""
    started = time.time()
    llm_conf = config.get("llm", {})
    graph = MarkdownifyGraph(
        llm_model=llm_conf,
        node_config=config,
    )

    with ThreadPoolExecutor(max_workers=1) as pool:
        result_state = pool.submit(
            _run_graph_isolated,
            graph,
            {"user_prompt": "", "url": url},
        ).result()

    md_output = (
        result_state.get("markdown") if isinstance(result_state, dict) else result_state
    )

    return ScrapeResult(
        mode=MODE_SCRAPE,
        answer=md_output,
        considered_urls=[url],
        site_results=[{"url": url, "result": md_output}],
        execution_info=str(getattr(graph, "execution_info", "")),
        elapsed_seconds=round(time.time() - started, 1),
    )


def run_extract(prompt: str, url: str, config: Dict[str, Any]) -> ScrapeResult:
    """Extract structured data from a single URL with a prompt (SmartScraperGraph)."""
    started = time.time()
    graph = SmartScraperGraph(prompt=prompt, source=url, config=config)
    return _execute_graph(graph, MODE_EXTRACT, started)


def run_single(prompt: str, url: str, config: Dict[str, Any]) -> ScrapeResult:
    """Alias for run_extract for backward compatibility."""
    return run_extract(prompt, url, config)


def run_search(prompt: str, config: Dict[str, Any]) -> ScrapeResult:
    """Search the web and extract data from top results (SearchGraph)."""
    started = time.time()
    graph = SearchGraph(prompt=prompt, config=config)
    return _execute_graph(graph, MODE_SEARCH, started)


def run_crawl(
    prompt: str,
    urls: List[str],
    config: Dict[str, Any],
    depth: int = 1,
) -> ScrapeResult:
    """Crawl a website across depth or scrape across multiple URLs."""
    started = time.time()
    graph: Any
    if len(urls) == 1 and depth > 1:
        # Depth search graph for recursive crawling
        crawl_config = dict(config)
        crawl_config["depth"] = depth
        graph = DepthSearchGraph(
            prompt=prompt
            or "Extract and summarize all content found across linked pages.",
            source=urls[0],
            config=crawl_config,
        )
        return _execute_graph(graph, MODE_CRAWL, started)

    # Multi-URL parallel scraper
    graph = SmartScraperMultiGraph(
        prompt=prompt or "Extract key information and summarize content.",
        source=urls,
        config=config,
    )
    return _execute_graph(graph, MODE_CRAWL, started)


def run_multi(prompt: str, urls: List[str], config: Dict[str, Any]) -> ScrapeResult:
    """Alias for run_crawl across multiple URLs."""
    return run_crawl(prompt=prompt, urls=urls, config=config, depth=1)


def run_scrape(
    mode: str,
    prompt: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    url: Optional[str] = None,
    urls: Optional[List[str]] = None,
    depth: int = 1,
) -> ScrapeResult:
    """Dispatch to the right pipeline for the requested mode."""
    cfg = config or {}
    p = (prompt or "").strip()

    if mode == MODE_SCRAPE:
        if not url:
            raise ValueError("A target URL is required for Scrape mode.")
        return run_scrape_markdown(url, cfg)

    if mode in (MODE_EXTRACT, "single"):
        if not url:
            raise ValueError("A source URL is required for Extract mode.")
        if not p:
            raise ValueError("A prompt is required for Extract mode.")
        return run_extract(p, url, cfg)

    if mode == MODE_SEARCH:
        if not p:
            raise ValueError("A search query or prompt is required.")
        return run_search(p, cfg)

    if mode in (MODE_CRAWL, "multi"):
        target_urls = urls or ([url] if url else [])
        if not target_urls:
            raise ValueError("At least one URL is required for Crawl mode.")
        return run_crawl(prompt=p, urls=target_urls, config=cfg, depth=depth)

    raise ValueError(f"Unknown scrape mode: {mode!r}")
