import sys
import os
from datetime import datetime, timedelta, timezone

import gradio as gr
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from db import get_db, DB_CONTENT, DB_APPEALS
from log import read_logs


def _week_ago() -> str:
    return (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat()


# ── Data loaders ──────────────────────────────────────────────────────────────


def label_distribution_data() -> pd.DataFrame:
    with get_db(DB_CONTENT) as conn:
        rows = conn.execute(
            "SELECT label, COUNT(*) AS count FROM content "
            "WHERE label IS NOT NULL GROUP BY label"
        ).fetchall()
    if not rows:
        return pd.DataFrame({"label": [], "count": []})
    return pd.DataFrame([{"label": r["label"], "count": r["count"]} for r in rows])


def appeals_over_time_data() -> pd.DataFrame:
    with get_db(DB_APPEALS) as conn:
        rows = conn.execute(
            "SELECT appealed_at FROM appeals WHERE appealed_at >= ?",
            (_week_ago(),),
        ).fetchall()
    if not rows:
        return pd.DataFrame({"hour": [], "appeals": []})
    df = pd.DataFrame([r["appealed_at"] for r in rows], columns=["appealed_at"])
    df["hour"] = (
        pd.to_datetime(df["appealed_at"]).dt.floor("h").dt.strftime("%Y-%m-%d %H:00")
    )
    return df.groupby("hour").size().reset_index(name="appeals").sort_values("hour")


def content_size_over_time_data() -> pd.DataFrame:
    with get_db(DB_CONTENT) as conn:
        rows = conn.execute(
            "SELECT submitted_at, LENGTH(content) AS chars FROM content "
            "WHERE submitted_at >= ?",
            (_week_ago(),),
        ).fetchall()
    if not rows:
        return pd.DataFrame({"hour": [], "chars": []})
    df = pd.DataFrame(
        [{"submitted_at": r["submitted_at"], "chars": r["chars"]} for r in rows]
    )
    df["hour"] = (
        pd.to_datetime(df["submitted_at"]).dt.floor("h").dt.strftime("%Y-%m-%d %H:00")
    )
    return df.groupby("hour")["chars"].sum().reset_index().sort_values("hour")


def all_log_entries() -> list[dict]:
    return list(reversed(read_logs()))


# ── Combined refresh ──────────────────────────────────────────────────────────


def refresh_all():
    return (
        label_distribution_data(),
        appeals_over_time_data(),
        content_size_over_time_data(),
        all_log_entries(),
    )


# ── Gradio UI ─────────────────────────────────────────────────────────────────

with gr.Blocks(title="Provenance Guard Analytics") as demo:
    gr.Markdown("# Provenance Guard Analytics")

    with gr.Tabs():
        with gr.Tab("Visualizations"):
            refresh_btn = gr.Button("Refresh", variant="primary")

            label_plot = gr.BarPlot(
                x="label",
                y="count",
                title="Content Label Distribution",
                x_title="Label",
                y_title="Count",
            )
            with gr.Row():
                appeals_plot = gr.BarPlot(
                    x="hour",
                    y="appeals",
                    title="Appeals Filed per Hour (last 7 days)",
                    x_title="Hour",
                    y_title="Appeals",
                )
                content_size_plot = gr.LinePlot(
                    x="hour",
                    y="chars",
                    title="Total Characters Uploaded per Hour (last 7 days)",
                    x_title="Hour",
                    y_title="Characters",
                )

        with gr.Tab("Logs"):
            refresh_logs_btn = gr.Button("Refresh Logs", variant="primary")
            logs_display = gr.JSON(label="Log Entries (newest first)")

    all_outputs = [label_plot, appeals_plot, content_size_plot, logs_display]

    demo.load(fn=refresh_all, outputs=all_outputs)
    refresh_btn.click(fn=refresh_all, outputs=all_outputs)
    refresh_logs_btn.click(fn=all_log_entries, outputs=[logs_display])


if __name__ == "__main__":
    demo.launch()
