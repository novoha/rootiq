"""
Map — a knowledge graph of every diagnosed error.

Reads working_dir/solutions.json and renders error -> fix -> source threads as
a Graphviz graph (via st.graphviz_chart, so no system Graphviz / extra deps).
Each unique error is one node; source threads are shared, so two errors that
cite the same forum thread converge on it — revealing related faults.
"""
import streamlit as st

from skills import lookup_history
from mapviz import build_dot

st.set_page_config(page_title="RootIQ · Map", page_icon="🗺️", layout="wide")
st.title("🗺️ Error Knowledge Map")
st.caption("Every diagnosed error → its fix → the forum threads it came from. "
           "Errors that share a source thread connect through it.")

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
