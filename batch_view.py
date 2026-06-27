"""
batch_view.py — Batch / CSV diagnosis UI.

Exposes render(), used as the third tab on the Analyse page. Upload a CSV,
pick the column(s) that describe the fault, and diagnose every unique fault in
one click: known faults resolve instantly from history, unknown ones are
scraped from the forum (all handled inside agent.run_agent).

It uses `return` (not st.stop) so it can live inside a tab without halting the
rest of the page.
"""
import csv as pycsv
import io
from collections import Counter

import pandas as pd
import streamlit as st

import agent
import llm
from skills import extract_log, save_solution
from mapviz import build_dot


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


def _target_for(text: str) -> tuple[str | None, str]:
    """Return (diagnosis target, raw text): first detected code, else the text."""
    text = (text or "").strip()
    if not text:
        return None, ""
    codes = extract_log.detect_error_codes(text)
    return (codes[0] if codes else text[:120]), text


def render() -> None:
    st.caption("Upload a CSV of error logs, pick the column(s) that describe the "
               "fault, and diagnose every unique fault in one click. Known faults "
               "resolve instantly from history; new ones are scraped from the forum.")

    up = st.file_uploader("Upload CSV", type=["csv"], key="batch_csv")
    if not up:
        st.info("Upload a .csv to begin.")
        return

    try:
        df = read_csv_robust(up.read())
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not read CSV: {e}")
        return

    if df.empty:
        st.warning("That CSV has no rows.")
        return

    st.markdown(f"**{len(df)} rows · {len(df.columns)} columns**")
    with st.expander("Preview (first 20 rows)"):
        st.dataframe(df.head(20), use_container_width=True, hide_index=True)

    # Pick one OR MORE columns; combined per row (e.g. Description + Value), so a
    # fault like "XC44" + "No contact" becomes one meaningful fault.
    _pref = [c for c in df.columns
             if c.strip().lower() in ("description", "value", "message", "fault",
                                      "error", "code", "alarm")]
    cols = st.multiselect(
        "Which column(s) describe the error? (combined per row)",
        list(df.columns), default=_pref or [df.columns[-1]], key="batch_cols",
    )
    if not cols:
        st.info("Pick at least one column.")
        return

    # Skip non-fault bookkeeping rows. Editable so it works for any log format.
    _default_ignore = ("System started, Application changed, User logged, "
                       "Clock changed, Machine ID changed, Date and time not set")
    ignore_raw = st.text_input(
        "Ignore rows containing any of (comma-separated, case-insensitive)",
        value=_default_ignore, key="batch_ignore",
        help="Filters out routine log entries that aren't faults.",
    )
    ignores = [x.strip().lower() for x in ignore_raw.split(",") if x.strip()]

    def row_text(row) -> str:
        parts = [str(row[c]).strip() for c in cols]
        parts = [p for p in parts if p and p.lower() != "nan"]
        return " — ".join(parts)

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
        tgt, txt = _target_for(text)
        if not tgt:
            continue
        counts[tgt] += 1
        if tgt not in rep_text or len(txt) > len(rep_text[tgt]):
            rep_text[tgt] = txt

    if not counts:
        st.warning("No usable fault rows after filtering. Check the column choice "
                   "or the ignore list.")
        return

    if skipped:
        st.caption(f"Filtered out {skipped} routine/non-fault row(s).")

    faults = sorted(counts, key=lambda t: -counts[t])
    preview = pd.DataFrame({"fault": faults,
                            "occurrences": [counts[t] for t in faults]})
    st.markdown(f"**{len(faults)} unique faults** found across the log.")
    with st.expander("See the unique faults", expanded=False):
        st.dataframe(preview, use_container_width=True, hide_index=True)

    if not llm.llm_online():
        st.warning(f"LLM not ready ({llm.provider_label()}). New faults will return "
                   "'cannot synthesise'; known faults still resolve from history.")

    run_all = st.button("🚀 Diagnose all faults", type="primary",
                        use_container_width=True, key="batch_run")

    def run_targets(tlist: list[str]) -> tuple[list[dict], list[dict]]:
        rows, full = [], []
        prog = st.progress(0.0, text="Starting...")
        for i, t in enumerate(tlist, 1):
            prog.progress(i / len(tlist), text=f"{i}/{len(tlist)} — {t[:50]}")
            sol = agent.run_agent(t, raw_text=rep_text.get(t, t))
            if sol.get("source_type") != "blocked" and sol.get("error_code"):
                try:
                    save_solution.run(sol)
                except Exception:  # noqa: BLE001
                    pass
            sol["scrape_count"] = counts[t]   # CSV occurrence count for the map
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

    if run_all:
        with st.spinner(f"Diagnosing {len(faults)} fault(s)..."):
            res, full = run_targets(faults)
        st.success(f"Done — {len(res)} diagnosed and saved to History.")
        rdf = pd.DataFrame(res)
        st.dataframe(rdf, use_container_width=True, hide_index=True)
        st.download_button(
            "⬇️ Download results CSV",
            data=rdf.to_csv(index=False).encode("utf-8"),
            file_name="rootiq_batch_results.csv", mime="text/csv",
        )

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
