"""
RootIQ — PLC Error Intelligence (main Analyse page).
Run with:  streamlit run app.py
"""
import datetime
import json

import streamlit as st

import agent
import batch_view
import llm
from config import load_config, save_config
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

    # Offline / Online mode toggle (persists to mcp.json so the agent sees it)
    online = st.sidebar.toggle(
        "🌐 Online mode",
        value=(llm.current_mode() == "online"),
        help="Off = offline, local Ollama. "
             "On = hosted API using the OPENAI_API_KEY in Streamlit secrets.",
    )
    desired = "online" if online else "offline"
    if desired != llm.current_mode():
        lc = llm.llm_config()
        cfg = load_config()
        cfg["llm"] = {"mode": desired, "ollama": lc["ollama"], "online": lc["online"]}
        save_config(cfg)
        st.rerun()

    label = llm.provider_label()
    if llm.llm_online():
        st.sidebar.markdown("🟢 **LLM ready**")
        st.sidebar.caption(label)
    else:
        st.sidebar.markdown("🔴 **LLM unavailable** — solutions from history only")
        st.sidebar.caption(label)

    stats = phase1_crawl.index_stats()
    if stats["exists"] and stats["count"]:
        st.sidebar.markdown(f"📇 **{stats['count']} topics indexed**")
    else:
        st.sidebar.markdown("⚠️ Index not built — go to **Settings**")

    st.sidebar.markdown("---")
    st.sidebar.caption("Pages: Analyse · Map · History · Reports · Settings")


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
    srcs = sol.get("sources") or []
    if srcs:
        lines += ["", "## Sources"]
        for s in srcs:
            lines.append(f"{s.get('n','')}. [{s.get('title') or s['url']}]({s['url']})")
    elif sol.get("source_url"):
        lines += ["", "## Sources", f"- {sol['source_url']}"]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
st.title("Analyse PLC Error Log")


def run_and_store(chosen: str, raw_text: str) -> None:
    """Run the agent pipeline with a live status panel and store the result."""
    with st.status("Running RootIQ agent...", expanded=True) as status:
        def step(label, detail=""):
            status.write(f"**{label}** {('— ' + detail) if detail else ''}")

        step("Extracting error codes...", chosen)
        solution = agent.run_agent(chosen, raw_text=raw_text, step=step)
        # Record every diagnosis to history automatically (skip security blocks).
        if solution.get("source_type") != "blocked" and solution.get("error_code"):
            try:
                saved = save_solution.run(solution)
                solution["scrape_count"] = saved.get("scrape_count", 1)
                solution["_saved"] = True
                step("Saved to history", f"scrape_count={saved.get('scrape_count', 1)}")
            except Exception as e:  # noqa: BLE001
                solution["_saved"] = False
                step("Could not save to history", str(e))
        st.session_state["solution"] = solution
        status.update(label="Agent complete", state="complete")


tab_upload, tab_type, tab_batch = st.tabs(
    ["📄 Upload a log", "⌨️ Type an error", "📦 Batch (CSV)"]
)

# --- Path 1: upload a PDF/image log -------------------------------------- #
with tab_upload:
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
        chosen = st.text_input("Error code / fault to diagnose",
                               value=default_code, key="chosen_upload")

        if st.button("🚀 Run RootIQ Agent", type="primary",
                     disabled=not chosen, key="run_upload"):
            run_and_store(chosen, extracted["text"])

# --- Path 2: type an error code / message directly ----------------------- #
with tab_type:
    st.caption("No file needed — type an error code or paste a fault message "
               "and RootIQ will diagnose it the same way.")
    typed = st.text_area(
        "Error code or fault message",
        placeholder="e.g. COUT_OVERCURRENT\n…or a description like "
                    "'Chassis module / No contact, critical CAN bus error'",
        key="typed_input",
        height=120,
    )
    if st.button("🚀 Diagnose", type="primary",
                 disabled=not typed.strip(), key="run_type"):
        text = typed.strip()
        run_and_store(text, text)

# --- Path 3: batch-diagnose a CSV of error logs -------------------------- #
with tab_batch:
    batch_view.render()


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

    # Every forum thread the answer was reasoned from (cited as [n] above).
    sources = solution.get("sources") or []
    if sources:
        st.markdown(f"**Sources** — reasoned from {len(sources)} forum thread(s):")
        for s in sources:
            title = s.get("title") or s["url"]
            st.markdown(f"{s.get('n','')}. [{title}]({s['url']})")
    elif solution.get("source_url"):
        st.markdown(f"**Source:** {solution['source_url']}")

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
        if solution.get("_saved"):
            st.success("✅ Auto-saved to history — see the History page.")
        elif st.button("💾 Save to history"):
            saved = save_solution.run(solution)
            st.success(f"Saved (scrape_count={saved['scrape_count']}).")
