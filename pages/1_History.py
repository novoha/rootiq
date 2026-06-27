"""History dashboard — browse, search, export, and prune saved solutions."""
import json

import pandas as pd
import streamlit as st

from skills import lookup_history
from config import WORKING_DIR

st.set_page_config(page_title="RootIQ · History", page_icon="📚", layout="wide")

solutions = lookup_history.all_solutions()

# Title + always-visible reset control (shown even when history is empty).
head, reset_col = st.columns([4, 1])
head.title("📚 Solution History")
with reset_col:
    st.write("")  # vertical nudge to align with the title
    if st.button("🗑️ Reset history", type="primary",
                 disabled=not solutions, use_container_width=True):
        from tools import write_file
        write_file("solutions.json", "[]")
        st.success("History cleared — starting fresh.")
        st.rerun()

if not solutions:
    st.info("No solutions saved yet. Diagnose a log on the Analyse page; "
            "each run is recorded here automatically.")
    st.stop()

df = pd.DataFrame(solutions)

# Metrics
total = len(df)
forum_hits = int((df.get("source_type") == "forum").sum()) if "source_type" in df else 0
hist_reuse = int(df.get("scrape_count", pd.Series([1] * total)).astype(int).sub(1).clip(lower=0).sum())
top_code = df["error_code"].value_counts().idxmax() if "error_code" in df else "—"

c1, c2, c3 = st.columns(3)
c1.metric("Total saved", total)
c2.metric("History re-uses", hist_reuse)
c3.metric("Most common code", top_code)

# Search
query = st.text_input("Search (error code, device, root cause)").strip().lower()
view = df.copy()
if query:
    mask = view.apply(
        lambda r: query in json.dumps(r.to_dict(), default=str).lower(), axis=1
    )
    view = view[mask]

cols = [c for c in ["error_code", "device", "root_cause", "source_type",
                    "confidence", "date_saved", "scrape_count"] if c in view.columns]
st.dataframe(view[cols], use_container_width=True, hide_index=True)

# Detail
st.markdown("### Inspect a solution")
pick = st.selectbox("Error code", options=view["error_code"].tolist() if not view.empty else [])
if pick:
    rec = next(s for s in solutions if s["error_code"] == pick)
    with st.expander(f"Full record — {pick}", expanded=True):
        st.json(rec)

# Export
st.download_button(
    "⬇️ Export all as CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="rootiq_history.csv",
    mime="text/csv",
)
st.caption(f"Stored at: {WORKING_DIR / 'solutions.json'}")
