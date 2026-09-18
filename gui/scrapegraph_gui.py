"""ScrapeGraphAI — Web Scraper for the AI Era.

Inspired by the official scrapegraphai.com platform, providing:
- ⚡ Scrape: Convert any URL into clean Markdown or HTML
- 🎯 Extract: Extract structured data with natural language prompts
- 🔎 Search: Search the web and extract data from top results in one call
- 🕸️ Crawl: Crawl websites and extract across pages or depth

Run with: uv run streamlit run gui/scrapegraph_gui.py
Or via the management script: ./gui/manage_gui.ps1 start
"""

import json
import traceback
from datetime import datetime

import streamlit as st
from gui_core import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    MODE_CRAWL,
    MODE_EXTRACT,
    MODE_SCRAPE,
    MODE_SEARCH,
    ScrapeResult,
    build_graph_config,
    invalid_urls,
    parse_urls,
    run_scrape,
)

# ---------------------------------------------------------------------------
# Streamlit Page Config & Theme Injection
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="ScrapeGraphAI — The scraper for the AI Era",
    page_icon="🕷️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MODE_CONFIG = {
    MODE_SCRAPE: {
        "title": "Scrape",
        "badge": "Markdown & Content",
        "description": "Convert any webpage into clean, LLM-ready markdown or text.",
        "submit_label": "START SCRAPING",
    },
    MODE_EXTRACT: {
        "title": "Extract",
        "badge": "Structured Data",
        "description": "Extract structured data from any webpage using natural language prompts.",
        "submit_label": "START EXTRACTING",
    },
    MODE_SEARCH: {
        "title": "Search",
        "badge": "Web Search & AI",
        "description": "Search the web and extract data from the top results in one call.",
        "submit_label": "START SEARCHING",
    },
    MODE_CRAWL: {
        "title": "Crawl",
        "badge": "Deep / Multi-Page",
        "description": "Crawl websites across linked pages or multiple URLs and extract unified insights.",
        "submit_label": "START CRAWLING",
    },
}

HISTORY_LIMIT = 20

# ---------------------------------------------------------------------------
# Custom CSS matching scrapegraphai.com design system
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

:root {
    --sgai-bg: #111113;
    --sgai-card: #18181b;
    --sgai-card-border: rgba(255, 255, 255, 0.08);
    --sgai-purple: #8c5aeb;
    --sgai-purple-hover: #7b46e3;
    --sgai-purple-subtle: rgba(140, 90, 235, 0.12);
    --sgai-text: #f4f4f5;
    --sgai-muted: #a1a1aa;
    --sgai-lime: #e6f900;
}

/* Global resets & typography */
html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

code, pre, .font-mono {
    font-family: 'IBM Plex Mono', monospace !important;
}

/* Hide default streamlit headers/footers for a standalone app feel */
#MainMenu, header[data-testid="stHeader"], footer {
    visibility: hidden;
    height: 0px;
}

.stApp {
    background-color: var(--sgai-bg);
    color: var(--sgai-text);
}

.block-container {
    max-width: 1040px !important;
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
}

/* Official Header Bar */
.sgai-navbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1.25rem;
    background: rgba(24, 24, 27, 0.7);
    border: 1px solid var(--sgai-card-border);
    border-radius: 8px;
    backdrop-filter: blur(12px);
    margin-bottom: 2.2rem;
}

.sgai-brand {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    font-size: 1.15rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: #ffffff;
    text-decoration: none;
}

.sgai-brand-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: linear-gradient(135deg, #8c5aeb, #6366f1);
    border-radius: 6px;
    color: white;
    font-size: 16px;
}

.sgai-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #d4d4d8;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 0.25rem 0.65rem;
    border-radius: 9999px;
}

/* Hero section */
.sgai-hero {
    text-align: center;
    margin: 1.5rem 0 2.2rem 0;
}

.sgai-hero-title {
    font-size: clamp(2.2rem, 5vw, 3.6rem);
    font-weight: 600;
    letter-spacing: -0.03em;
    line-height: 1.1;
    color: #ffffff;
    margin-bottom: 0.75rem;
}

.sgai-hero-subtitle {
    font-size: 1.05rem;
    color: var(--sgai-muted);
    max-width: 680px;
    margin: 0 auto;
    line-height: 1.5;
}

/* Clean Tabs/Radio design */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    justify-content: center !important;
    gap: 0.5rem !important;
    background: rgba(24, 24, 27, 0.95) !important;
    border: 1px solid var(--sgai-card-border) !important;
    padding: 0.4rem !important;
    border-radius: 8px !important;
    max-width: 540px !important;
    margin: 0 auto 1.75rem auto !important;
}

div[data-testid="stRadio"] > div[role="radiogroup"] > label {
    flex: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0.6rem 1rem !important;
    border-radius: 6px !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    cursor: pointer !important;
    background: transparent !important;
    color: #e4e4e7 !important;
    transition: all 0.15s ease !important;
}

div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
    color: #ffffff !important;
    background: rgba(255, 255, 255, 0.08) !important;
}

/* Hide default circle radio button completely */
div[data-testid="stRadio"] div[role="radiogroup"] label > div:first-child {
    display: none !important;
}

/* Selected tab pill */
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
    background: var(--sgai-purple) !important;
    color: #ffffff !important;
    box-shadow: 0 4px 14px rgba(140, 90, 235, 0.4) !important;
}

div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) * {
    color: #ffffff !important;
    font-weight: 600 !important;
}

div[data-testid="stRadio"] div[data-testid="stMarkdownContainer"] p {
    color: inherit !important;
    font-size: 0.92rem !important;
    margin: 0 !important;
}

/* Modern Input Card Container */
.sgai-action-card {
    background: rgba(24, 24, 27, 0.85);
    border: 1px solid var(--sgai-card-border);
    border-radius: 10px;
    padding: 1.5rem;
    box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(16px);
    margin-bottom: 1.5rem;
}

.sgai-mode-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.5rem;
}

.sgai-mode-header h3 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: #ffffff;
}

.sgai-mode-pill {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    background: var(--sgai-purple-subtle);
    color: #c4b5fd;
    border: 1px solid rgba(140, 90, 235, 0.3);
    padding: 0.25rem 0.75rem;
    border-radius: 6px;
}

/* Primary Action Buttons */
.stButton > button[kind="primary"] {
    background-color: var(--sgai-purple) !important;
    color: #ffffff !important;
    border: none !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    padding: 0.75rem 1.75rem !important;
    border-radius: 6px !important;
    box-shadow: 0 4px 16px rgba(140, 90, 235, 0.35) !important;
    transition: all 0.15s ease !important;
}

.stButton > button[kind="primary"]:hover {
    background-color: var(--sgai-purple-hover) !important;
    box-shadow: 0 6px 20px rgba(140, 90, 235, 0.5) !important;
    transform: translateY(-1px);
}

/* Input boxes dark styling */
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {
    background: #18181b !important;
    color: #ffffff !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.9rem !important;
}

div[data-testid="stTextInput"] input:focus, div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--sgai-purple) !important;
    box-shadow: 0 0 0 2px var(--sgai-purple-subtle) !important;
}

div[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace !important;
    color: #ffffff !important;
}

div[data-testid="stExpander"] {
    background: rgba(24, 24, 27, 0.6);
    border: 1px solid var(--sgai-card-border);
    border-radius: 8px;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Top Navbar (Brand + GitHub Star Badge, No Auth / Sign-up)
# ---------------------------------------------------------------------------
st.markdown(
    """
<div class="sgai-navbar">
    <a href="https://scrapegraphai.com" target="_blank" class="sgai-brand">
        <span class="sgai-brand-logo">🕷️</span>
        <span>ScrapeGraphAI</span>
    </a>
    <div style="display: flex; align-items: center; gap: 0.75rem;">
        <span class="sgai-badge">★ 31.1k Stars</span>
        <span class="sgai-badge" style="background: rgba(140, 90, 235, 0.15); color: #c4b5fd; border-color: rgba(140,90,235,0.3);">v2 Local UI</span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar: LLM Model & Graph Parameters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Engine Settings")
    model = st.text_input("Model ID", value=DEFAULT_MODEL, key="model")
    base_url = st.text_input("Base URL", value=DEFAULT_BASE_URL, key="base_url")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.0, 0.1, key="temperature")
    output_format = st.selectbox(
        "Format", ["json", "text"], index=0, key="output_format"
    )

    st.markdown("---")
    st.markdown("### 🔎 Search & Crawl")
    max_results = st.slider(
        "Search depth / Websites",
        min_value=1,
        max_value=10,
        value=3,
        key="max_results",
        help="Number of search hits scraped in Search mode.",
    )
    crawl_depth = st.slider(
        "Crawl recursion depth",
        min_value=1,
        max_value=3,
        value=1,
        key="crawl_depth",
        help="Depth limit when crawling recursive links.",
    )
    verbose = st.checkbox("Verbose graph logs", value=False, key="verbose")

    st.divider()
    if st.button("🗑️ Clear History", key="clear_history", use_container_width=True):
        st.session_state.history = []
        st.session_state.last_result = None
        st.rerun()

# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ---------------------------------------------------------------------------
# Hero Header
# ---------------------------------------------------------------------------
st.markdown(
    """
<div class="sgai-hero">
    <h1 class="sgai-hero-title">The scraper for the AI Era</h1>
    <p class="sgai-hero-subtitle">
        Turn any webpage into clean markdown, extract structured schemas,
        search the live web, or crawl multi-page sites with direct AI graph logic.
    </p>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Mode Picker (Scrape, Extract, Search, Crawl)
# ---------------------------------------------------------------------------
MODE_OPTIONS = [MODE_SCRAPE, MODE_EXTRACT, MODE_SEARCH, MODE_CRAWL]
MODE_TITLES = {
    MODE_SCRAPE: "⚡ Scrape",
    MODE_EXTRACT: "🎯 Extract",
    MODE_SEARCH: "🔎 Search",
    MODE_CRAWL: "🕸️ Crawl",
}

selected_title = st.radio(
    "Select operation",
    options=[MODE_TITLES[m] for m in MODE_OPTIONS],
    horizontal=True,
    label_visibility="collapsed",
    key="mode_radio",
)
current_mode = {v: k for k, v in MODE_TITLES.items()}[selected_title]
mode_meta = MODE_CONFIG[current_mode]

# ---------------------------------------------------------------------------
# Dynamic Action Card Input
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class="sgai-action-card">
    <div class="sgai-mode-header">
        <div>
            <h3>{mode_meta['title']}</h3>
            <span style="font-size: 0.88rem; color: #a1a1aa;">{mode_meta['description']}</span>
        </div>
        <span class="sgai-mode-pill">{mode_meta['badge']}</span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

prompt_input = ""
url_input = ""
urls_list = []

if current_mode == MODE_SCRAPE:
    url_input = st.text_input(
        "Target URL",
        value="",
        placeholder="https://example.com/blog/getting-started",
        key="scrape_url",
        help="Convert this webpage directly into clean, LLM-ready markdown.",
    )
elif current_mode == MODE_EXTRACT:
    url_input = st.text_input(
        "Target URL",
        value="",
        placeholder="https://news.ycombinator.com",
        key="extract_url",
    )
    prompt_input = st.text_area(
        "Extraction Prompt",
        value="",
        placeholder="e.g. Extract the top 3 stories with title, points, and author",
        height=90,
        key="extract_prompt",
    )
elif current_mode == MODE_SEARCH:
    prompt_input = st.text_area(
        "Search Query & Prompt",
        value="",
        placeholder="e.g. Find the best open-source AI frameworks released in 2026 and summarize their features.",
        height=100,
        key="search_prompt",
    )
    st.caption(f"Will search and scrape the top {max_results} pages.")
elif current_mode == MODE_CRAWL:
    crawl_text = st.text_area(
        "Target URLs (one per line)",
        value="",
        placeholder="https://docs.example.com\nhttps://example.com/about",
        height=120,
        key="crawl_urls",
    )
    urls_list = parse_urls(crawl_text)
    bad_urls = invalid_urls(urls_list)
    valid_urls = [u for u in urls_list if u not in bad_urls]
    if valid_urls:
        st.caption(f"✅ {len(valid_urls)} valid URL(s) ready to crawl.")
    for bad in bad_urls:
        st.warning(f"Not a valid http(s) URL: `{bad}`")

    prompt_input = st.text_area(
        "Extraction Prompt (optional)",
        value="",
        placeholder="e.g. Summarize key product details across all pages",
        height=80,
        key="crawl_prompt",
    )

run_clicked = st.button(
    f"🚀 {mode_meta['submit_label']}",
    type="primary",
    use_container_width=True,
    key="run",
)

# ---------------------------------------------------------------------------
# Pipeline Execution
# ---------------------------------------------------------------------------
if run_clicked:
    validation_error = None

    if current_mode == MODE_SCRAPE:
        if not url_input.strip():
            validation_error = "Please provide a target URL to scrape."
        elif invalid_urls([url_input.strip()]):
            validation_error = f"`{url_input.strip()}` is not a valid http(s) URL."
    elif current_mode == MODE_EXTRACT:
        if not url_input.strip():
            validation_error = "Please provide a target URL."
        elif invalid_urls([url_input.strip()]):
            validation_error = f"`{url_input.strip()}` is not a valid http(s) URL."
        elif not prompt_input.strip():
            validation_error = "Please provide an extraction prompt."
    elif current_mode == MODE_SEARCH:
        if not prompt_input.strip():
            validation_error = "Please provide a search query or question."
    elif current_mode == MODE_CRAWL:
        if not urls_list:
            validation_error = "Please provide at least one URL to crawl."
        elif invalid_urls(urls_list):
            validation_error = "Please fix the invalid URLs before running."

    if validation_error:
        st.error(validation_error)
    else:
        config = build_graph_config(
            model=model,
            base_url=base_url,
            temperature=temperature,
            output_format=output_format,
            max_results=max_results if current_mode == MODE_SEARCH else None,
            depth=crawl_depth if current_mode == MODE_CRAWL else 1,
            verbose=verbose,
        )

        spinner_msg = {
            MODE_SCRAPE: f"Converting {url_input} to clean markdown...",
            MODE_EXTRACT: f"Extracting structured data from {url_input}...",
            MODE_SEARCH: f"Searching web and scraping top {max_results} results...",
            MODE_CRAWL: f"Crawling {len(urls_list)} website(s)...",
        }[current_mode]

        with st.spinner(spinner_msg):
            try:
                result = run_scrape(
                    mode=current_mode,
                    prompt=prompt_input.strip() or None,
                    config=config,
                    url=url_input.strip() or None,
                    urls=urls_list or None,
                    depth=crawl_depth,
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Execution failed: {exc}")
                with st.expander("Traceback"):
                    st.code(traceback.format_exc())
            else:
                st.session_state.last_result = result
                st.session_state.history.insert(
                    0,
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "mode": mode_meta["title"],
                        "target": url_input
                        or f"{len(urls_list)} URLs"
                        or prompt_input[:30],
                        "elapsed": f"{result.elapsed_seconds}s",
                    },
                )
                st.session_state.history = st.session_state.history[:HISTORY_LIMIT]

# ---------------------------------------------------------------------------
# Results Display
# ---------------------------------------------------------------------------
result: ScrapeResult | None = st.session_state.last_result

if result is not None:
    st.divider()
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Mode", MODE_CONFIG.get(result.mode, {}).get("title", result.mode))
    col_b.metric(
        "Pages Scraped",
        len(result.site_results)
        or (1 if result.mode in (MODE_SCRAPE, MODE_EXTRACT) else 0),
    )
    col_c.metric("Duration", f"{result.elapsed_seconds}s")

    st.subheader("Result Output")
    if isinstance(result.answer, (dict, list)):
        st.json(result.answer)
    elif result.mode == MODE_SCRAPE:
        # Markdown preview + raw code view tab
        t1, t2 = st.tabs(["Rendered Markdown", "Raw Markdown"])
        with t1:
            st.markdown(str(result.answer))
        with t2:
            st.code(str(result.answer), language="markdown")
    else:
        st.markdown(str(result.answer))

    if result.considered_urls:
        with st.expander(f"🌐 Sources ({len(result.considered_urls)})"):
            for u in result.considered_urls:
                st.markdown(f"- `{u}`")

    if result.site_results and len(result.site_results) > 1:
        st.subheader("Per-Page Results")
        for s in result.site_results:
            with st.expander(f"📄 {s['url']}"):
                content = s["result"]
                if isinstance(content, (dict, list)):
                    st.json(content)
                else:
                    st.markdown(str(content))

    export_payload = {
        "mode": result.mode,
        "answer": result.answer,
        "considered_urls": result.considered_urls,
        "site_results": result.site_results,
    }
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "⬇️ Download JSON",
            data=json.dumps(export_payload, indent=2, default=str),
            file_name=f"scrapegraph_{result.mode}.json",
            mime="application/json",
            use_container_width=True,
            key="download_json",
        )
    with d2:
        rows = [
            {
                "url": site["url"],
                "result": (
                    json.dumps(site["result"], default=str)
                    if isinstance(site["result"], (dict, list))
                    else str(site["result"])
                ),
            }
            for site in result.site_results
        ] or [{"url": "", "result": json.dumps(result.answer, default=str)}]
        csv_text = "url,result\n" + "\n".join(
            '"{}","{}"'.format(
                row["url"].replace('"', '""'), row["result"].replace('"', '""')
            )
            for row in rows
        )
        st.download_button(
            "⬇️ Download CSV",
            data=csv_text,
            file_name=f"scrapegraph_{result.mode}.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_csv",
        )

    with st.expander("Pipeline Execution Info"):
        st.code(result.execution_info or "{}", language="json")

# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
if st.session_state.history:
    st.divider()
    with st.expander(f"🕘 Recent Executions ({len(st.session_state.history)})"):
        st.dataframe(
            st.session_state.history,
            use_container_width=True,
            hide_index=True,
        )
