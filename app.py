"""
RootIQ — PLC Error Intelligence (main Analyse page).
Run with:  streamlit run app.py
"""
import datetime
import json

import streamlit as st

import agent
from config import ollama_settings
from skills import extract_log, save_solution, phase1_crawl

st.set_page_config(page_title="RootIQ", page_icon="🔧", layout="wide")

CSS = """
<style>
[data-testid="stSidebar"] { background-color: #0D1B2A; }
[data-testid="stSidebar"] * { color: white !important; }
.error-code { font-family: monospace; font-size: 1.4rem; color: #0D9488; font-weight: bold; }
.badge-history { background:#166534; color:#dcfce7; padding:3px 10px; border-radius:6px; font-size:12px; font-weight:500; }
.badge-forum { background:#1e3a5f; color:#bfdbfe; padding:3px 10px; border-radius:6px; font-size:12px; font-weight:500; }
.badge-high { background:#166534; color:#dcfce7; padding:3px 8px; border-radius:6px; font-size:11px; }
.badge-medium { background:#854d0e; color:#fef9c3; padding:3px 8px; border-radius:6px; font-size:11px; }
.badge-low { background:#7f1d1d; color:#fee2e2; padding:3px 8px; border-radius:6px; font-size:11px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def render_sidebar():
    st.sidebar.markdown("# 🔧🧠 RootIQ")
    st.sidebar.caption("PLC Error Intelligence — Diagnose faster, fix smarter.")
    st.sidebar.markdown("---")

    if agent.ollama_online():
        st.sidebar.markdown("🟢 **Ollama online** "
                            f"(`{ollama_settings()['model']}`)")
    else:
        st.sidebar.markdown("🔴 **Ollama offline** — solutions from history only")

    stats = phase1_crawl.index_stats()
    if stats["exists"] and stats["count"]:
        st.sidebar.markdown(f"📇 **{stats['count']} topics indexed**")
    else:
        st.sidebar.markdown("⚠️ Index not built — go to **Settings**")

    st.sidebar.markdown("---")
    st.sidebar.caption("Pages: Analyse · History · Reports · Settings")


render_sidebar()


def render_markdown(sol: dict) -> str:
    lines = [
        f"# {sol.get('error_code','?')}",
        "",
        f"- **Device:** {sol.get('device') or 'n/a'}",
        f"- **Confidence:** {sol.get('confidence','Low')}",
        f"- **Source:** {sol.get('source_type','')} {sol.get('source_url','')}",
        f"- **Generated:** {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        "",
        "## Root cause",
        sol.get("root_cause", "") or "_n/a_",
        "",
        "## Fix steps",
    ]
    for i, s in enumerate(sol.get("fix_steps") or [], 1):
        lines.append(f"{i}. {s}")
    if sol.get("notes"):
        lines += ["", "## Notes", sol["notes"]]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
st.title("Analyse PLC Error Log")

uploaded = st.file_uploader(
    "Upload error log",
    type=["pdf", "png", "jpg", "jpeg", "tiff", "bmp"],
)

if uploaded is not None:
    data = uploaded.read()
    with st.spinner("Extracting text and error codes..."):
        extracted = extract_log.run(uploaded.name, data)
    st.session_state["extracted"] = extracted

extracted = st.session_state.get("extracted")

if extracted:
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.expander("Extracted text", expanded=False):
            st.text(extracted["text"][:5000] or "(no text found)")
    with col2:
        st.markdown("**Detected error codes**")
        codes = extracted["error_codes"]
        if codes:
            st.markdown(" ".join(
                f"<span class='badge-forum'>{c}</span>" for c in codes
            ), unsafe_allow_html=True)
        else:
            st.info("No error codes auto-detected. Enter one manually below.")

    default_code = codes[0] if (codes := extracted["error_codes"]) else ""
    chosen = st.text_input("Error code / fault to diagnose", value=default_code)

    if st.button("🚀 Run RootIQ Agent", type="primary", disabled=not chosen):
        with st.status("Running RootIQ agent...", expanded=True) as status:
            log_lines = []

            def step(label, detail=""):
                line = f"**{label}** {('— ' + detail) if detail else ''}"
                log_lines.append(line)
                status.write(line)

            step("Extracting error codes...", chosen)
            solution = agent.run_agent(chosen, raw_text=extracted["text"], step=step)
            st.session_state["solution"] = solution
            status.update(label="Agent complete", state="complete")


# --------------------------------------------------------------------------- #
# Result card
# --------------------------------------------------------------------------- #
solution = st.session_state.get("solution")
if solution:
    st.markdown("---")
    st.markdown(f"<div class='error-code'>{solution.get('error_code','?')}</div>",
                unsafe_allow_html=True)

    src = solution.get("source_type", "")
    if src == "history":
        st.markdown("<span class='badge-history'>From history</span>",
                    unsafe_allow_html=True)
    elif src == "forum":
        url = solution.get("source_url", "")
        st.markdown(f"<span class='badge-forum'>From IQAN forum</span> {url}",
                    unsafe_allow_html=True)

    conf = (solution.get("confidence") or "Low").lower()
    st.markdown(f"<span class='badge-{conf}'>Confidence: {conf.title()}</span>",
                unsafe_allow_html=True)

    if solution.get("device"):
        st.markdown(f"**Device:** {solution['device']}")
    if solution.get("root_cause"):
        st.markdown(f"**Root cause:** {solution['root_cause']}")

    steps = solution.get("fix_steps") or []
    if steps:
        st.markdown("**Fix steps:**")
        for i, s in enumerate(steps, 1):
            st.markdown(f"{i}. {s}")

    if solution.get("notes"):
        st.info(solution["notes"])

    # Build a markdown export
    md_text = render_markdown(solution)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "⬇️ Download as Markdown",
            data=md_text,
            file_name=f"{solution.get('error_code','solution')}.md",
            mime="text/markdown",
        )
    with c2:
        if st.button("💾 Save to history"):
            saved = save_solution.run(solution)
            st.success(f"Saved (scrape_count={saved['scrape_count']}).")
