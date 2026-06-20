"""Reports — analytics over saved solutions and agent run log."""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from skills import lookup_history
from config import WORKING_DIR

st.set_page_config(page_title="RootIQ · Reports", page_icon="📊", layout="wide")
st.title("📊 Reports & Analytics")

solutions = lookup_history.all_solutions()
if not solutions:
    st.info("No data yet. Save some diagnoses first.")
    st.stop()

df = pd.DataFrame(solutions)
if "date_saved" in df:
    df["date_saved"] = pd.to_datetime(df["date_saved"], errors="coerce", utc=True)

# Agent run log
log_path = WORKING_DIR / "agent_log.jsonl"
runs = []
if log_path.exists():
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
runs_df = pd.DataFrame(runs)

# Metric cards
c1, c2, c3, c4 = st.columns(4)
c1.metric("Solutions stored", len(df))
c2.metric("Unique codes", df["error_code"].nunique())
forum_fetches = int((runs_df.get("source") == "forum").sum()) if not runs_df.empty else 0
history_hits = int((runs_df.get("source") == "history").sum()) if not runs_df.empty else 0
c3.metric("Forum fetches", forum_fetches)
c4.metric("History hits", history_hits)

# Top error codes
st.subheader("Top error codes")
top = df["error_code"].value_counts().head(10).reset_index()
top.columns = ["error_code", "count"]
st.plotly_chart(px.bar(top, x="error_code", y="count"), use_container_width=True)

# Source breakdown
if "source_type" in df:
    st.subheader("Solution source breakdown")
    sb = df["source_type"].value_counts().reset_index()
    sb.columns = ["source", "count"]
    st.plotly_chart(px.pie(sb, names="source", values="count"), use_container_width=True)

# Over time
if "date_saved" in df and df["date_saved"].notna().any():
    st.subheader("Solutions saved over time")
    by_week = (df.dropna(subset=["date_saved"])
                 .set_index("date_saved").resample("W").size().reset_index())
    by_week.columns = ["week", "count"]
    st.plotly_chart(px.line(by_week, x="week", y="count", markers=True),
                    use_container_width=True)
