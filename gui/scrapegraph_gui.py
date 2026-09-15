"""Interactive Streamlit GUI for ScrapeGraphAI.

Three ways to scrape, all driven by natural language:

- **Web search**: ask a question in plain language; SearchGraph finds the top
  websites for you and scrapes them all.
- **Single URL**: scrape one page with a prompt.
- **Multiple URLs**: scrape several pages at once with one shared prompt.

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
    MODE_MULTI,
    MODE_SEARCH,
    MODE_SINGLE,
    ScrapeResult,
    build_graph_config,
    invalid_urls,
    parse_urls,
    run_scrape,
)

st.set_page_config(page_title="ScrapeGraphAI", page_icon="🕷️", layout="wide")

MODE_LABELS = {
    MODE_SEARCH: "🔍 Web search (natural language)",
    MODE_SINGLE: "🔗 Single URL",
    MODE_MULTI: "📚 Multiple URLs",
}

HISTORY_LIMIT = 20

# ---------------------------------------------------------------------------
# Sidebar: model + search settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Model settings")
    model = st.text_input("Ollama model", value=DEFAULT_MODEL, key="model")
    base_url = st.text_input("Ollama base URL", value=DEFAULT_BASE_URL, key="base_url")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.0, 0.1, key="temperature")
    output_format = st.selectbox(
        "Output format", ["json", "text"], index=0, key="output_format"
    )

    st.header("🔎 Search settings")
    max_results = st.slider(
        "Websites to scrape per search",
        min_value=1,
        max_value=10,
        value=3,
        key="max_results",
        help="How many of the top search results are scraped and merged into "
        "the final answer.",
    )
    verbose = st.checkbox("Verbose logging", value=False, key="verbose")

    st.divider()
    if st.button("🗑️ Clear history", key="clear_history", use_container_width=True):
        st.session_state.history = []
        st.session_state.last_result = None
        st.rerun()

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "history" not in st.session_state:
    st.session_state.history = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ---------------------------------------------------------------------------
# Header + mode picker
# ---------------------------------------------------------------------------
st.title("🕷️ ScrapeGraphAI")
st.caption(
    "Ask in plain language. Search the web or scrape one page — or many at "
    "once — powered by an LLM graph pipeline."
)

mode_label = st.radio(
    "What do you want to do?",
    options=list(MODE_LABELS.values()),
    horizontal=True,
    key="mode",
)
mode = {v: k for k, v in MODE_LABELS.items()}[mode_label]

# ---------------------------------------------------------------------------
# Inputs (per mode)
# ---------------------------------------------------------------------------
prompt = ""
source_url = ""
source_urls: list[str] = []

if mode == MODE_SEARCH:
    prompt = st.text_area(
        "Ask anything",
        value="",
        placeholder="e.g. What are the best hiking trails near Trento, Italy?",
        height=100,
        key="prompt_search",
    )
    st.caption(
        f"The top {max_results} websites for your question will be scraped "
        "and merged into one answer."
    )
elif mode == MODE_SINGLE:
    source_url = st.text_input(
        "Source URL", value="", placeholder="https://example.com", key="single_url"
    )
    prompt = st.text_area(
        "What should I extract?",
        value="",
        placeholder="e.g. Summarize the main content of this page.",
        height=100,
        key="prompt_single",
    )
else:
    urls_text = st.text_area(
        "Source URLs (one per line)",
        value="",
        placeholder="https://example.com\nhttps://www.iana.org/domains/example",
        height=140,
        key="multi_urls",
    )
    source_urls = parse_urls(urls_text)
    bad_urls = invalid_urls(source_urls)
    if source_urls:
        st.caption(f"✅ {len(source_urls)} URL(s) ready to scrape.")
    for bad_url in bad_urls:
        st.warning(f"Not a valid http(s) URL: `{bad_url}`")
    prompt = st.text_area(
        "What should I extract from every page?",
        value="",
        placeholder="e.g. List the page title and its main topic.",
        height=100,
        key="prompt_multi",
    )

run_clicked = st.button("🚀 Run", type="primary", use_container_width=True, key="run")

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if run_clicked:
    error_message = None
    if not prompt.strip():
        error_message = "Please describe what you want to know or extract."
    elif mode == MODE_SINGLE and not source_url.strip():
        error_message = "Please provide a source URL."
    elif mode == MODE_SINGLE and invalid_urls([source_url.strip()]):
        error_message = f"`{source_url.strip()}` is not a valid http(s) URL."
    elif mode == MODE_MULTI and not source_urls:
        error_message = "Please provide at least one URL."
    elif mode == MODE_MULTI and invalid_urls(source_urls):
        error_message = "Please fix the invalid URLs highlighted above."

    if error_message:
        st.error(error_message)
    else:
        config = build_graph_config(
            model=model,
            base_url=base_url,
            temperature=temperature,
            output_format=output_format,
            max_results=max_results if mode == MODE_SEARCH else None,
            verbose=verbose,
        )
        spinner_text = {
            MODE_SEARCH: (
                f"Searching the web and scraping the top {max_results} sites..."
            ),
            MODE_SINGLE: f"Scraping {source_url} ...",
            MODE_MULTI: f"Scraping {len(source_urls)} sites in parallel...",
        }[mode]

        with st.spinner(spinner_text):
            try:
                result = run_scrape(
                    mode=mode,
                    prompt=prompt.strip(),
                    config=config,
                    url=source_url.strip() or None,
                    urls=source_urls or None,
                )
            except Exception as exc:  # noqa: BLE001 - surface any failure
                st.error(f"Scrape failed: {exc}")
                with st.expander("Traceback"):
                    st.code(traceback.format_exc())
            else:
                st.session_state.last_result = result
                st.session_state.history.insert(
                    0,
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "mode": MODE_LABELS[mode],
                        "prompt": prompt.strip(),
                        "sites": len(result.site_results)
                        or (1 if mode == MODE_SINGLE else 0),
                        "elapsed": result.elapsed_seconds,
                    },
                )
                st.session_state.history = st.session_state.history[:HISTORY_LIMIT]

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
result: ScrapeResult | None = st.session_state.last_result

if result is not None:
    st.divider()
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Mode", MODE_LABELS[result.mode].split(" ", 1)[1])
    col_b.metric(
        "Sites scraped",
        len(result.site_results) or (1 if result.mode == MODE_SINGLE else 0),
    )
    col_c.metric("Elapsed", f"{result.elapsed_seconds}s")

    st.subheader("Answer")
    if isinstance(result.answer, (dict, list)):
        st.json(result.answer)
    else:
        st.markdown(str(result.answer))

    if result.considered_urls:
        with st.expander(f"🌐 Websites used ({len(result.considered_urls)})"):
            for url in result.considered_urls:
                st.markdown(f"- {url}")

    if result.site_results:
        st.subheader("Per-site results")
        for site in result.site_results:
            with st.expander(f"📄 {site['url']}"):
                site_result = site["result"]
                if isinstance(site_result, (dict, list)):
                    st.json(site_result)
                else:
                    st.markdown(str(site_result))

    export_payload = {
        "mode": result.mode,
        "answer": result.answer,
        "considered_urls": result.considered_urls,
        "site_results": result.site_results,
    }
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "⬇️ Download JSON",
            data=json.dumps(export_payload, indent=2, default=str),
            file_name="scrapegraph_result.json",
            mime="application/json",
            use_container_width=True,
            key="download_json",
        )
    with dl_col2:
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
            file_name="scrapegraph_result.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_csv",
        )

    with st.expander("Execution info"):
        st.code(result.execution_info, language="json")
else:
    st.info("Choose a mode above, describe what you need, then click **Run**.")

# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
if st.session_state.history:
    st.divider()
    with st.expander(f"🕘 Run history ({len(st.session_state.history)})"):
        st.dataframe(
            st.session_state.history,
            use_container_width=True,
            hide_index=True,
        )
