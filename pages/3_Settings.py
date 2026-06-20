"""Settings — Ollama, forum index, forum config, security log, maintenance."""
import json
import datetime
from pathlib import Path

import requests
import streamlit as st

import security
import llm
from config import load_config, save_config, WORKING_DIR
from skills import phase1_crawl

st.set_page_config(page_title="RootIQ · Settings", page_icon="⚙️", layout="wide")
st.title("⚙️ Settings")

cfg = load_config()

# --------------------------------------------------------------------------- #
# 1. LLM provider — offline (Ollama) vs online (OpenAI-compatible)
# --------------------------------------------------------------------------- #
st.header("1 · LLM Provider")
lc = llm.llm_config()
mode = lc["mode"]
st.caption(f"Current mode: **{mode.upper()}** — switch it with the 🌐 toggle in "
           f"the sidebar. Below you can edit the endpoint/model for this mode.")

if mode == "offline":
    st.caption("Runs against a local Ollama. Works on a machine where Ollama is "
               "reachable — **not** on Streamlit Cloud (no localhost LLM there).")
    ourl = st.text_input("Ollama URL", value=lc["ollama"]["url"])
    omodels = ["phi3", "llama3", "mistral", "gemma2"]
    cur = lc["ollama"]["model"]
    omodel = st.selectbox("Ollama model", omodels,
                          index=omodels.index(cur) if cur in omodels else 0)
    new_llm = {"mode": "offline",
               "ollama": {"url": ourl, "model": omodel,
                          "timeout": lc["ollama"].get("timeout", 120)},
               "online": lc["online"]}
else:
    st.caption("Runs against any OpenAI-compatible API — use this for the hosted "
               "Streamlit app.")
    base = st.text_input(
        "API base URL", value=lc["online"]["base_url"],
        help="OpenAI: https://api.openai.com/v1 · "
             "Groq: https://api.groq.com/openai/v1 · "
             "OpenRouter: https://openrouter.ai/api/v1",
    )
    omodel = st.text_input("Model", value=lc["online"]["model"],
                           help="e.g. gpt-4o-mini, llama-3.1-8b-instant")
    # The key is provided via Streamlit secrets — NOT typed here.
    if llm.api_key_present():
        st.success("API key loaded from Streamlit secrets ✅")
    else:
        st.info("No API key found. Add `OPENAI_API_KEY` in **Manage app → "
                "Settings → Secrets** (or as a local env var). The key is never "
                "entered in this app.")
    new_llm = {"mode": "online",
               "ollama": lc["ollama"],
               "online": {"base_url": base, "model": omodel,
                          "timeout": lc["online"].get("timeout", 120)}}

col_a, col_b = st.columns(2)
with col_a:
    if st.button("Test connection"):
        cfg["llm"] = new_llm
        cfg["ollama"] = new_llm["ollama"]
        save_config(cfg)
        ok, msg = llm.test_connection()
        (st.success if ok else st.error)(msg)
with col_b:
    if st.button("Save LLM settings"):
        cfg["llm"] = new_llm
        cfg["ollama"] = new_llm["ollama"]  # keep back-compat block in sync
        save_config(cfg)
        st.success("Saved to mcp.json (API key NOT stored here).")

# Live round-trip test: actually ask the model to reply.
if st.button("🧪 Send test message (say hello)"):
    cfg["llm"] = new_llm
    cfg["ollama"] = new_llm["ollama"]
    save_config(cfg)
    with st.spinner("Asking the model to reply..."):
        try:
            reply = llm.call_llm(
                "You are a connectivity test. Reply in one short sentence.",
                "Say hello and confirm you are working.",
            )
            if reply and reply.strip():
                st.success("✅ Model replied — your key/endpoint works:")
                st.info(reply.strip())
            else:
                st.error("Model returned an empty reply. Check the model name.")
        except Exception as e:  # noqa: BLE001
            st.error(f"❌ Test failed: {e}")
            st.caption("Common causes: wrong/missing OPENAI_API_KEY in secrets, "
                       "wrong base URL, or a model name your provider doesn't offer.")

# --------------------------------------------------------------------------- #
# 2. Forum index (Phase 1)
# --------------------------------------------------------------------------- #
st.header("2 · IQAN Forum Index (Phase 1)")
stats = phase1_crawl.index_stats()
if stats["exists"] and stats["count"]:
    ts = datetime.datetime.fromtimestamp(stats["last_modified"]).isoformat(timespec="seconds")
    st.markdown(f"**{stats['count']} topics** · last crawled {ts}")
else:
    st.warning("Index not built yet.")

st.caption("⚠️ Opens a headless browser; ~5–10 min for ~2500 topics.")
if st.button("Build / Refresh Index (Phase 1)"):
    prog = st.progress(0.0, text="Starting crawler...")
    counter = {"n": 0}

    def on_progress(community, scroll, count):
        counter["n"] = count
        prog.progress(min(scroll / phase1_crawl.MAX_SCROLLS, 1.0),
                      text=f"[{community}] scroll {scroll} · {count} topics")

    try:
        total = phase1_crawl.run_phase1(progress=on_progress)
        prog.progress(1.0, text="Done")
        st.success(f"Indexed {total} topics.")
        new = phase1_crawl.index_stats().get("recent", [])
        if new:
            st.write("Most recent topics:")
            for t in new:
                st.markdown(f"- [{t.get('title','(no title)')}]({t['url']})")
    except Exception as e:  # noqa: BLE001
        st.error(f"Crawl failed: {e}. Did you run `playwright install chromium`?")

# --------------------------------------------------------------------------- #
# 3. Forum config (mcp.json)
# --------------------------------------------------------------------------- #
st.header("3 · Forum Config (mcp.json)")
forums = cfg.get("forums", [])
edited = []
for i, f in enumerate(forums):
    cols = st.columns([2, 4, 1])
    name = cols[0].text_input(f"Name {i}", value=f.get("name", ""), key=f"fn{i}")
    cu = cols[1].text_input(f"Community URL {i}", value=f.get("community_url", ""), key=f"fu{i}")
    en = cols[2].toggle("On", value=f.get("enabled", True), key=f"fe{i}")
    edited.append({**f, "name": name, "community_url": cu, "enabled": en})
if st.button("Save forum config"):
    cfg["forums"] = edited
    save_config(cfg)
    st.success("Saved to mcp.json")

# --------------------------------------------------------------------------- #
# 4. Security
# --------------------------------------------------------------------------- #
st.header("4 · Security")
st.markdown("**Blocked patterns** (first-screen on tool args)")
st.code("\n".join(security.BLOCKED_PATTERNS))
st.markdown("**Blocked commands**")
st.code(", ".join(sorted(security.BLOCKED_COMMANDS)))
st.markdown("**Allowed scrape domains**")
st.code(", ".join(sorted(security.ALLOWED_SCRAPE_DOMAINS)))

with st.expander("Recent rejections (last 20)"):
    rej = WORKING_DIR / "rejection_log.jsonl"
    if rej.exists():
        lines = rej.read_text(encoding="utf-8").splitlines()[-20:]
        for ln in reversed(lines):
            try:
                e = json.loads(ln)
                st.markdown(f"- `{e['timestamp']}` **{e['tool']}** — {e['reason']}")
            except json.JSONDecodeError:
                continue
    else:
        st.caption("No rejections logged yet.")

# --------------------------------------------------------------------------- #
# 5. Maintenance
# --------------------------------------------------------------------------- #
st.header("5 · Maintenance")
sol_path = WORKING_DIR / "solutions.json"
st.caption(f"Working dir: {WORKING_DIR}")
if sol_path.exists():
    size_kb = sol_path.stat().st_size / 1024
    st.markdown(f"`solutions.json` — {size_kb:.1f} KB")
    st.download_button("⬇️ Export backup (solutions.json)",
                       data=sol_path.read_bytes(),
                       file_name="solutions_backup.json", mime="application/json")

st.markdown("**Danger zone**")
st.warning("Clearing history overwrites solutions.json with an empty list.")
confirm = st.checkbox("I understand this cannot be undone")
if st.button("Clear history", disabled=not confirm):
    from tools import write_file
    write_file("solutions.json", "[]")
    st.success("History cleared.")
