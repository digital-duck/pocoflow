"""PicoFlow Workflow Monitor — Streamlit UI for run observability.

Standalone usage:
    streamlit run picoflow/ui/monitor.py -- /path/to/picoflow.db

Embedded usage (in any Streamlit page):
    from picoflow.ui.monitor import render_workflow_monitor
    render_workflow_monitor("picoflow.db")

Requires the optional [ui] extra:
    pip install picoflow[ui]

Features
--------
- Runs table with live status badges (auto-refresh every 5 / 10 / 30 s)
- Per-run detail panel with three tabs:
    Timeline  — ordered event log (node timings, errors)
    Store     — step slider to inspect Store state at any checkpoint
    Resume    — copy-paste code snippet to resume from a checkpoint
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

STATUS_EMOJI = {
    "queued":    "⏳",
    "running":   "🔄",
    "paused":    "⏸️",
    "completed": "✅",
    "failed":    "❌",
}


def _duration(row: dict) -> str:
    """Human-readable duration from run row."""
    started = row.get("started_at", "")
    ended = row.get("completed_at", "")
    if not started:
        return "—"
    try:
        from datetime import datetime, timezone
        fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
        t0 = datetime.fromisoformat(started)
        t1 = datetime.fromisoformat(ended) if ended else datetime.now(timezone.utc)
        secs = (t1 - t0).total_seconds()
        if secs < 60:
            return f"{secs:.1f}s"
        return f"{secs/60:.1f}m"
    except Exception:
        return "—"


def render_workflow_monitor(
    db_path: str | Path,
    title: str = "PicoFlow Monitor",
) -> None:
    """Render the full workflow monitor UI into the current Streamlit page.

    Parameters
    ----------
    db_path :
        Path to the SQLite database file (``picoflow.db`` or similar).
        Creates the file / schema if it does not exist.
    title :
        Section heading displayed at the top of the monitor.
    """
    import streamlit as st
    from picoflow.db import WorkflowDB

    db_path = Path(db_path)
    db = WorkflowDB(db_path)

    # ── Header ────────────────────────────────────────────────────────────────
    col_title, col_refresh, col_interval = st.columns([5, 2, 2])
    with col_title:
        st.subheader(title)
        st.caption(f"DB: `{db_path}`")
    with col_refresh:
        auto_refresh = st.toggle("Auto-refresh", value=False)
    with col_interval:
        refresh_secs = st.selectbox(
            "Interval", [5, 10, 30], index=0, disabled=not auto_refresh,
            label_visibility="collapsed",
        )

    if st.button("🔄 Refresh now", use_container_width=False):
        st.rerun()

    # ── Runs table ────────────────────────────────────────────────────────────
    runs = db.list_runs(limit=200)

    if not runs:
        st.info("No workflow runs recorded yet. Start a flow with `db_path` set to this file.")
        _maybe_rerun(auto_refresh, refresh_secs)
        return

    # Build display rows
    rows = []
    for r in runs:
        emoji = STATUS_EMOJI.get(r["status"], "❓")
        rows.append({
            "Status":     f"{emoji} {r['status']}",
            "Run ID":     r["run_id"],
            "Flow":       r["flow_name"] or "—",
            "Started":    (r["started_at"] or "")[:19].replace("T", " "),
            "Duration":   _duration(r),
            "Steps":      r["total_steps"] if r["total_steps"] is not None else "—",
            "Node":       r["current_node"] or "—",
        })

    # Display as a table; keep selected row in session state
    if "pf_selected_run" not in st.session_state:
        st.session_state.pf_selected_run = None

    run_ids = [r["run_id"] for r in runs]

    st.markdown("**Select a run to inspect:**")
    selected_run_id = st.selectbox(
        "Run",
        options=run_ids,
        format_func=lambda rid: next(
            f"{STATUS_EMOJI.get(r['status'], '?')} {r['run_id']}  [{r['flow_name'] or '—'}]  {r['status']}"
            for r in runs if r["run_id"] == rid
        ),
        label_visibility="collapsed",
        key="pf_run_selector",
    )
    st.session_state.pf_selected_run = selected_run_id

    import pandas as pd
    df = pd.DataFrame(rows)
    # Highlight selected row
    def _highlight(row):
        return ["background-color: #1a3a5c" if row["Run ID"] == selected_run_id else ""
                for _ in row]
    st.dataframe(
        df.style.apply(_highlight, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    # ── Run detail ────────────────────────────────────────────────────────────
    if selected_run_id:
        run = db.get_run(selected_run_id)
        if not run:
            st.warning("Run not found — may have been deleted.")
            return

        st.divider()
        st.markdown(f"### Run detail — `{selected_run_id}`")

        # Key metrics row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Status", f"{STATUS_EMOJI.get(run['status'], '?')} {run['status']}")
        m2.metric("Flow", run["flow_name"] or "—")
        m3.metric("Steps", run["total_steps"] or "—")
        m4.metric("Duration", _duration(run))

        if run.get("error_msg"):
            st.error(f"Error: {run['error_msg']}")

        # Three tabs
        tab_timeline, tab_store, tab_resume = st.tabs(["📋 Timeline", "🗄 Store", "⏩ Resume"])

        # ── Timeline tab ──────────────────────────────────────────────────────
        with tab_timeline:
            events = db.get_events(selected_run_id)
            if not events:
                st.info("No events recorded for this run.")
            else:
                ev_rows = []
                for e in events:
                    ev_rows.append({
                        "#":       e["id"],
                        "Step":    e["step"] if e["step"] is not None else "—",
                        "Node":    e["node_name"] or "—",
                        "Event":   e["event"],
                        "Action":  e["action"] or "—",
                        "ms":      f"{e['elapsed_ms']:.1f}" if e["elapsed_ms"] else "—",
                        "Time":    (e["ts"] or "")[:19].replace("T", " "),
                        "Error":   (e["error_msg"] or "")[:80],
                    })
                st.dataframe(pd.DataFrame(ev_rows), use_container_width=True, hide_index=True)

        # ── Store Inspector tab ────────────────────────────────────────────────
        with tab_store:
            checkpoints = db.get_checkpoints(selected_run_id)
            if not checkpoints:
                st.info("No checkpoints saved for this run.")
            else:
                step_options = {
                    f"Step {c['step']} — {c['node_name']}  ({c['created_at'][:19].replace('T',' ')})": c["step"]
                    for c in checkpoints
                }
                selected_label = st.selectbox("Checkpoint", list(step_options.keys()))
                selected_step = step_options[selected_label]

                try:
                    restored = db.load_checkpoint(selected_run_id, selected_step)
                    kv_rows = [
                        {"Key": k, "Value": _fmt_value(v), "Type": type(v).__name__}
                        for k, v in restored._data.items()
                    ]
                    st.dataframe(pd.DataFrame(kv_rows), use_container_width=True, hide_index=True)

                    with st.expander("Raw JSON"):
                        st.code(json.dumps(restored._data, indent=2, ensure_ascii=False), language="json")
                except KeyError as e:
                    st.error(str(e))

        # ── Resume tab ────────────────────────────────────────────────────────
        with tab_resume:
            checkpoints = db.get_checkpoints(selected_run_id)
            if not checkpoints:
                st.info("No checkpoints available — flow may not have completed any nodes.")
            else:
                st.markdown("**Restore a checkpoint and resume the flow from any node.**")
                ckpt_options = {
                    f"Step {c['step']} — {c['node_name']}": c["step"]
                    for c in checkpoints
                }
                resume_label = st.selectbox("Resume from checkpoint", list(ckpt_options.keys()),
                                            key="pf_resume_ckpt")
                resume_step = ckpt_options[resume_label]
                resume_node = checkpoints[resume_step]["node_name"]

                db_path_str = str(db_path)
                snippet = f"""\
from picoflow.db import WorkflowDB
from picoflow import Flow

# Restore store from checkpoint
db = WorkflowDB("{db_path_str}")
store = db.load_checkpoint("{selected_run_id}", step={resume_step})

# Rebuild your flow (same node objects as original run)
# flow = build_my_flow()

# Resume from the node that produced this checkpoint
# flow.run(store, resume_from={resume_node}_node)
"""
                st.code(snippet, language="python")
                st.caption(
                    "Copy the snippet above into your notebook or script.  "
                    "Replace `build_my_flow()` with your actual flow builder and "
                    f"`{resume_node}_node` with the corresponding node instance."
                )

    # ── Auto-refresh ──────────────────────────────────────────────────────────
    _maybe_rerun(auto_refresh, refresh_secs)


def _fmt_value(v: object) -> str:
    """Format a store value for table display (truncate long strings)."""
    s = str(v)
    return s[:120] + "…" if len(s) > 120 else s


def _maybe_rerun(auto_refresh: bool, secs: int) -> None:
    """Sleep then rerun if auto-refresh is enabled."""
    if auto_refresh:
        import streamlit as st
        placeholder = st.empty()
        for i in range(secs, 0, -1):
            placeholder.caption(f"Refreshing in {i}s…")
            time.sleep(1)
        placeholder.empty()
        st.rerun()


# ── Standalone entry point ────────────────────────────────────────────────────

def _main() -> None:
    """Standalone Streamlit app.

    Usage:
        streamlit run picoflow/ui/monitor.py
        streamlit run picoflow/ui/monitor.py -- picoflow.db
    """
    import streamlit as st

    # db_path from CLI arg (passed after `--` to streamlit)
    db_arg = sys.argv[1] if len(sys.argv) > 1 else "picoflow.db"

    st.set_page_config(
        page_title="PicoFlow Monitor",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.title("⚡ PicoFlow Workflow Monitor")
    st.caption("Built with love by Claude & digital-duck 🦆")
    st.divider()

    # Optional db path override from sidebar
    with st.sidebar:
        st.header("Settings")
        db_path_input = st.text_input("Database path", value=db_arg)

    render_workflow_monitor(db_path_input or db_arg)


if __name__ == "__main__":
    _main()
