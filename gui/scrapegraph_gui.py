"""Interactive Streamlit GUI for scrapegraphai's SmartScraperGraph.

Run with: uv run streamlit run gui/scrapegraph_gui.py
Or via the management script: ./gui/manage_gui.ps1 start
"""

import asyncio
import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from scrapegraphai.graphs import SmartScraperGraph


def _run_graph_isolated(graph: SmartScraperGraph):
    """Run the graph in a worker thread with a Proactor event loop policy.

    Streamlit's Tornado server pins the main thread's asyncio event loop to
    SelectorEventLoop on Windows, which has no subprocess support. Playwright's
    async API needs to spawn a browser subprocess, which requires
    ProactorEventLoop. Running the scrape in its own thread with the policy
    forced to Proactor avoids clashing with Tornado's loop in the main thread.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return graph.run()


st.set_page_config(page_title="ScrapeGraphAI", page_icon="🕷️", layout="wide")

st.title("🕷️ ScrapeGraphAI")
st.caption(
    "Scrape any page with a natural-language prompt, powered by an LLM graph pipeline."
)

with st.sidebar:
    st.header("Model settings")
    model = st.text_input("Ollama model", value="ollama/glm-5.3-flash:cloud")
    base_url = st.text_input("Ollama base URL", value="http://localhost:11434")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.0, 0.1)
    output_format = st.selectbox("Output format", ["json", "text"], index=0)

col1, col2 = st.columns([2, 3])

with col1:
    source = st.text_input("Source URL", value="https://example.com")
    prompt = st.text_area(
        "Prompt",
        value="Summarize the main content of this page.",
        height=120,
    )
    run_clicked = st.button("Run scrape", type="primary", use_container_width=True)

with col2:
    result_area = st.container()

if run_clicked:
    if not source.strip() or not prompt.strip():
        st.error("Please provide both a source URL and a prompt.")
    else:
        graph_config = {
            "llm": {
                "model": model,
                "temperature": temperature,
                "format": output_format,
                "base_url": base_url,
            },
        }
        with result_area:
            with st.spinner(f"Scraping {source} ..."):
                try:
                    graph = SmartScraperGraph(
                        prompt=prompt,
                        source=source,
                        config=graph_config,
                    )
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        result = pool.submit(_run_graph_isolated, graph).result()
                    exec_info = graph.get_execution_info()
                except (
                    Exception
                ) as exc:  # noqa: BLE001 - surface any scrape failure to the UI
                    st.error(f"Scrape failed: {exc}")
                    st.code(traceback.format_exc())
                else:
                    st.success("Done")
                    st.subheader("Result")
                    st.json(result)
                    with st.expander("Execution info"):
                        st.text(str(exec_info))
                    with st.expander("Raw JSON"):
                        st.code(json.dumps(result, indent=2, default=str))
else:
    with result_area:
        st.info("Enter a URL and prompt, then click **Run scrape**.")
