"""
Map — a knowledge graph of every diagnosed error.

Reads working_dir/solutions.json and renders error -> fix -> source threads as
a Graphviz graph (via st.graphviz_chart, so no system Graphviz / extra deps).
Each unique error is one node; source threads are shared, so two errors that
cite the same forum thread converge on it — revealing related faults.
"""
import streamlit as st

from skills import lookup_history

st.set_page_config(page_title="RootIQ · Map", page_icon="🗺️", layout="wide")
st.title("🗺️ Error Knowledge Map")
st.caption("Every diagnosed error → its fix → the forum threads it came from. "
           "Errors that share a source thread connect through it.")

# confidence -> (fill, font)
_CONF = {
    "high":   ("#166534", "#ffffff"),
    "medium": ("#854d0e", "#ffffff"),
    "low":    ("#7f1d1d", "#ffffff"),
}


def _esc(s, limit: int = 60) -> str:
    """Escape a string for a DOT label and trim it."""
    s = str(s or "").replace("\\", " ").replace('"', "'").replace("\n", " ").strip()
    return (s[:limit] + "…") if len(s) > limit else s


def build_dot(sols: list[dict], max_errors: int, confs: set[str]) -> tuple[str, dict]:
    """Return (dot_string, stats). Errors are sorted by occurrence (scrape_count)."""
    sols = [s for s in sols if (s.get("confidence") or "Low").lower() in confs]
    sols = sorted(sols, key=lambda s: -int(s.get("scrape_count", 1) or 1))[:max_errors]

    lines = [
        "digraph G {",
        '  rankdir=LR;',
        '  graph [bgcolor="transparent" pad=0.3 nodesep=0.35 ranksep=0.9];',
        '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=10];',
        '  edge [color="#94a3b8" arrowsize=0.7];',
    ]

    src_id: dict[str, str] = {}      # url -> node id (shared across errors)
    src_label: dict[str, str] = {}   # url -> best title seen
    src_edges: set[tuple[str, str]] = set()

    for i, s in enumerate(sols):
        code = s.get("error_code", "?")
        conf = (s.get("confidence") or "Low").lower()
        fill, font = _CONF.get(conf, ("#475569", "#ffffff"))
        occ = int(s.get("scrape_count", 1) or 1)

        eid = f"e{i}"
        lines.append(
            f'  {eid} [label="{_esc(code, 40)}\\n×{occ} · {conf.title()}" '
            f'fillcolor="{fill}" fontcolor="{font}"];'
        )

        fid = f"f{i}"
        nsteps = len(s.get("fix_steps") or [])
        rc = _esc(s.get("root_cause", "") or "Fix", 70)
        lines.append(
            f'  {fid} [label="{rc}\\n({nsteps} steps)" shape=note '
            f'fillcolor="#1e293b" fontcolor="#e2e8f0"];'
        )
        lines.append(f"  {eid} -> {fid};")

        srcs = s.get("sources") or []
        if not srcs and s.get("source_url"):
            srcs = [{"url": s["source_url"], "title": ""}]
        for src in srcs:
            url = (src or {}).get("url")
            if not url:
                continue
            if url not in src_id:
                src_id[url] = f"s{len(src_id)}"
            sid = src_id[url]
            title = (src or {}).get("title") or url.rsplit("/", 1)[-1]
            if len(title) > len(src_label.get(url, "")):
                src_label[url] = title
            src_edges.add((fid, sid))

    # Emit shared source nodes (clickable) + their edges.
    for url, sid in src_id.items():
        label = _esc(src_label.get(url, url), 45)
        lines.append(
            f'  {sid} [label="{label}" shape=folder fillcolor="#0e3a5f" '
            f'fontcolor="#bfdbfe" URL="{url}" target="_blank" tooltip="{_esc(url, 120)}"];'
        )
    for fid, sid in sorted(src_edges):
        lines.append(f'  {fid} -> {sid} [style=dashed];')

    lines.append("}")
    # how many sources are shared by >1 error
    fan = {}
    for fid, sid in src_edges:
        fan[sid] = fan.get(sid, 0) + 1
    shared = sum(1 for v in fan.values() if v > 1)
    return "\n".join(lines), {
        "errors": len(sols), "sources": len(src_id), "shared_sources": shared,
    }


sols = lookup_history.all_solutions()
if not sols:
    st.info("No diagnoses yet. Run something on the Analyse or Batch page; this "
            "map fills in automatically and accumulates over time.")
    st.stop()

c1, c2 = st.columns([2, 1])
all_confs = ["High", "Medium", "Low"]
picked = c1.multiselect("Show confidence levels", all_confs, default=all_confs)
max_errors = c2.slider("Max errors", 1, max(1, len(sols)),
                       value=min(40, len(sols)))

confset = {c.lower() for c in picked} or {"high", "medium", "low"}
dot, stats = build_dot(sols, max_errors, confset)

m1, m2, m3 = st.columns(3)
m1.metric("Errors mapped", stats["errors"])
m2.metric("Source threads", stats["sources"])
m3.metric("Shared sources", stats["shared_sources"],
          help="Forum threads cited by more than one error — the links in the map.")

st.graphviz_chart(dot, use_container_width=True)

st.caption("🟢 High · 🟠 Medium · 🔴 Low confidence · 📁 source threads "
           "(click to open the forum). Dashed lines link a fix to its sources.")
