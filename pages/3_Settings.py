"""Settings — Ollama, forum index, forum config, security log, maintenance."""
import json
import datetime
from pathlib import Path

import requests
import streamlit as st

import security
from config import load_config, save_config, WORKING_DIR
from skills import phase1_crawl

st.set_page_config(page_title="RootIQ · Settings", page_icon="⚙️", layout="wide")
st.title("⚙️ Settings")

cfg = load_config()

# --------------------------------------------------------------------------- #
# 1. Ollama
# --------------------------------------------------------------------------- #
st.header("1 · Ollama")
o = cfg["ollama"]
url = st.text_input("Ollama URL", value=o["url"])
model = st.selectbox("Model", ["phi3", "llama3", "mistral", "gemma2"],
                     index=max(0, ["phi3", "llama3", "mistral", "gemma2"].index(o["model"])
                               if o["model"] in ["phi3", "llama3", "mistral", "gemma2"] else 0))
if st.button("Test connection"):
    try:
        r = requests.get(url, timeout=3)
        st.success("Ollama reachable ✅" if r.status_code == 200 else f"HTTP {r.status_code}")
    except requests.RequestException as e:
        st.error(f"Unreachable: {e}")
if st.button("Save Ollama settings"):
    cfg["ollama"]["url"] = url
    cfg["ollama"]["model"] = model
    save_config(cfg)
    st.success("Saved to mcp.json")

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
