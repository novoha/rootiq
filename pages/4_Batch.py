"""
Batch / CSV — diagnose many error logs at once.

Upload a CSV, pick the column that holds the error code or message, and either
browse + diagnose selected rows or run a capped "diagnose all". Each target is
code-detected (falling back to the raw text), de-duplicated, and routed through
the normal agent pipeline. Repeated codes are instant (served from history), so
only unique, not-yet-seen codes actually call the LLM.
"""
import csv as pycsv
import io
from collections import Counter

import pandas as pd
import streamlit as st

import agent
import llm
from skills import extract_log, save_solution, lookup_history

st.set_page_config(page_title="RootIQ · Batch", page_icon="📦", layout="wide")
st.title("📦 Batch / CSV Diagnosis")
st.caption("Upload a CSV of error logs, pick the column to diagnose, and run them "
           "in bulk. Repeated codes are instant (served from history) — you only "
           "pay the LLM for unique, not-yet-seen ones.")

up = st.file_uploader("Upload CSV", type=["csv"])
if not up:
    st.info("Upload a .csv to begin.")
    st.stop()


def read_csv_robust(raw: bytes) -> pd.DataFrame:
    """Read a CSV regardless of delimiter (; , tab |) and strip a UTF-8 BOM.
    IQAN system logs are semicolon-delimited with a BOM, which trips pandas'
    comma default — so sniff the separator from the header line."""
    text = raw.decode("utf-8-sig", errors="replace")  # utf-8-sig drops the BOM
    header = next((ln for ln in text.splitlines() if ln.strip()), "")
    try:
        delim = pycsv.Sniffer().sniff(header, delimiters=";,\t|").delimiter
    except Exception:  # noqa: BLE001 — fall back to the most frequent candidate
        delim = max([";", ",", "\t", "|"], key=header.count) or ","
    return pd.read_csv(io.StringIO(text), sep=delim, engine="python",
                       dtype=str, keep_default_na=False)


try:
    df = read_csv_robust(up.read())
except Exception as e:  # noqa: BLE001
    st.error(f"Could not read CSV: {e}")
    st.stop()

if df.empty:
    st.warning("That CSV has no rows.")
    st.stop()

st.markdown(f"**{len(df)} rows · {len(df.columns)} columns**")
with st.expander("Preview (first 20 rows)"):
    st.dataframe(df.head(20), use_container_width=True, hide_index=True)

# Pick one OR MORE columns; combined per row (e.g. Description + Value), so a
# fault like "XC44" + "No contact" becomes one meaningful target.
_pref = [c for c in df.columns
         if c.strip().lower() in ("description", "value", "message", "fault",
                                  "error", "code", "alarm")]
cols = st.multiselect(
    "Which column(s) describe the error? (combined per row)",
    list(df.columns), default=_pref or [df.columns[-1]],
)
if not cols:
    st.info("Pick at least one column.")
    st.stop()

# Skip non-fault bookkeeping rows. Editable so it works for any log format.
_DEFAULT_IGNORE = ("System started, Application changed, User logged, "
                   "Clock changed, Machine ID changed, Date and time not set")
ignore_raw = st.text_input(
    "Ignore rows containing any of (comma-separated, case-insensitive)",
    value=_DEFAULT_IGNORE,
    help="Filters out routine log entries that aren't faults.",
)
ignores = [x.strip().lower() for x in ignore_raw.split(",") if x.strip()]


def row_text(row) -> str:
    """Join the chosen columns of one row into a single fault description."""
    parts = [str(row[c]).strip() for c in cols]
    parts = [p for p in parts if p and p.lower() != "nan"]
    return " — ".join(parts)


def target_for(text: str) -> tuple[str | None, str]:
    """Return (diagnosis target, raw text). Use the first detected code if any,
    else the text itself."""
    text = (text or "").strip()
    if not text:
        return None, ""
    codes = extract_log.detect_error_codes(text)
    return (codes[0] if codes else text[:120]), text


# Aggregate rows into unique targets + frequency + a representative text.
counts: Counter = Counter()
rep_text: dict[str, str] = {}
skipped = 0
for _, row in df.iterrows():
    text = row_text(row)
    if not text:
        continue
    if any(x in text.lower() for x in ignores):
        skipped += 1
        continue
    tgt, txt = target_for(text)
    if not tgt:
        continue
    counts[tgt] += 1
    if tgt not in rep_text or len(txt) > len(rep_text[tgt]):
        rep_text[tgt] = txt

if not counts:
    st.warning("No usable fault rows after filtering. Check the column choice "
               "or the ignore list.")
    st.stop()

if skipped:
    st.caption(f"Filtered out {skipped} routine/non-fault row(s).")

targets = sorted(counts, key=lambda t: -counts[t])

MAX_SHOW = 200
if len(targets) > MAX_SHOW:
    st.caption(f"Showing the {MAX_SHOW} most frequent of {len(targets)} unique "
               f"targets (raise the cap below to diagnose beyond the table).")
    shown = targets[:MAX_SHOW]
else:
    shown = targets


def _norm(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


# Load history once and test membership locally (avoids a file read per target).
known_codes = {_norm(h.get("error_code", "")) for h in lookup_history.all_solutions()}
known = {t: _norm(t) in known_codes for t in shown}
n_new = sum(1 for t in shown if not known[t])

st.markdown(f"**{len(targets)} unique targets** · **{n_new}** not yet in history "
            f"(only these call the LLM).")

if not llm.llm_online():
    st.warning(f"LLM not ready ({llm.provider_label()}). New codes will return "
               "'cannot synthesise'; codes already in history still resolve.")

# --- Browse + select ----------------------------------------------------- #
table = pd.DataFrame({
    "diagnose": [False] * len(shown),
    "target": shown,
    "occurrences": [counts[t] for t in shown],
    "in_history": [known[t] for t in shown],
})
edited = st.data_editor(
    table, hide_index=True, use_container_width=True,
    column_config={
        "diagnose": st.column_config.CheckboxColumn("diagnose", default=False),
    },
    disabled=["target", "occurrences", "in_history"],
    key="batch_table",
)

# --- Controls ------------------------------------------------------------ #
cc1, cc2 = st.columns(2)
cap = cc1.number_input("Top-N cap for 'Diagnose all'", min_value=1,
                       max_value=len(targets), value=min(20, len(targets)),
                       help="Caps cost: only the N most frequent targets run.")
skip_known = cc2.checkbox("Skip targets already in history", value=True)

b1, b2 = st.columns(2)
run_all = b1.button("🚀 Diagnose all (top-N)", type="primary", use_container_width=True)
run_sel = b2.button("Diagnose selected", use_container_width=True)


def run_targets(tlist: list[str]) -> tuple[list[dict], list[dict]]:
    """Returns (table_rows, full_solutions). The full solutions feed the map."""
    rows, full = [], []
    prog = st.progress(0.0, text="Starting...")
    for i, t in enumerate(tlist, 1):
        prog.progress(i / len(tlist), text=f"{i}/{len(tlist)} — {t[:50]}")
        sol = agent.run_agent(t, raw_text=rep_text.get(t, t))
        # Auto-record (run_agent doesn't save; the Analyse page does that itself).
        if sol.get("source_type") != "blocked" and sol.get("error_code"):
            try:
                save_solution.run(sol)
            except Exception:  # noqa: BLE001
                pass
        # Use the CSV occurrence count for the map's ×N labelling.
        sol["scrape_count"] = counts[t]
        full.append(sol)
        rows.append({
            "target": t,
            "occurrences": counts[t],
            "error_code": sol.get("error_code", ""),
            "source": sol.get("source_type", ""),
            "confidence": sol.get("confidence", ""),
            "root_cause": (sol.get("root_cause", "") or "")[:200],
            "n_sources": len(sol.get("sources") or []),
            "source_url": sol.get("source_url", ""),
        })
    prog.progress(1.0, text="Done")
    return rows, full


selected = None
if run_all:
    selected = [t for t in targets if not (skip_known and _norm(t) in known_codes)][:cap]
elif run_sel:
    selected = edited.loc[edited["diagnose"], "target"].tolist()

if selected is not None:
    if not selected:
        st.warning("Nothing to diagnose with the current selection/filters.")
    else:
        with st.spinner(f"Diagnosing {len(selected)} target(s)..."):
            res, full = run_targets(selected)
        st.success(f"Done — {len(res)} diagnosed and saved to History.")
        rdf = pd.DataFrame(res)
        st.dataframe(rdf, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Download results CSV",
            data=rdf.to_csv(index=False).encode("utf-8"),
            file_name="rootiq_batch_results.csv", mime="text/csv",
        )

        # Per-batch knowledge map — just this CSV's faults, shared sources linked.
        from mapviz import build_dot
        dot, stats = build_dot(full, len(full), {"high", "medium", "low"})
        st.markdown("### 🗺️ Map of this batch")
        mm1, mm2, mm3 = st.columns(3)
        mm1.metric("Errors", stats["errors"])
        mm2.metric("Source threads", stats["sources"])
        mm3.metric("Shared sources", stats["shared_sources"],
                   help="Threads cited by more than one error in this batch.")
        st.graphviz_chart(dot, use_container_width=True)
        st.caption("🟢 High · 🟠 Medium · 🔴 Low · 📁 source threads (click to open). "
                   "See the **Map** page for the graph across all history.")
