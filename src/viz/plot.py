"""분석 쿼리 결과 시각화 → docs/charts/*.png 저장."""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 헤드리스 환경 (Docker) 대응
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import psycopg

from src.generator.writer import get_dsn

CHARTS_DIR = Path(__file__).parents[2] / "docs" / "charts"
PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2"]


def _get_conn() -> psycopg.Connection:
    return psycopg.connect(get_dsn())


def _query(conn: psycopg.Connection, sql: str) -> pd.DataFrame:
    """psycopg3 cursor → DataFrame (pd.read_sql 경고 우회)."""
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [desc.name for desc in cur.description]
    return pd.DataFrame(rows, columns=cols)


# ── Chart 1: 이벤트 타입별 발생 횟수 ──────────────────────────

def plot_events_by_type(conn: psycopg.Connection) -> Path:
    df = _query(conn, """
        SELECT event_type,
               COUNT(*) AS total,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM events
        GROUP BY event_type
        ORDER BY total DESC
    """)

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(df["event_type"], df["total"], color=PALETTE[:len(df)], edgecolor="white")

    for bar, pct in zip(bars, df["pct"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 20,
                f"{pct}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_title("Event Count by Type", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Event Type")
    ax.set_ylabel("Count")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()

    out = CHARTS_DIR / "events_by_type.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"[viz] saved: {out}")
    return out


# ── Chart 2: 시간대별 이벤트 추이 ─────────────────────────────

def plot_events_hourly(conn: psycopg.Connection) -> Path:
    df = _query(conn, """
        SELECT date_trunc('hour', occurred_at) AS hour,
               event_type,
               COUNT(*) AS total
        FROM events
        GROUP BY hour, event_type
        ORDER BY hour
    """)

    if df.empty:
        print("[viz] events_hourly: 데이터 없음, skip")
        return CHARTS_DIR / "events_hourly.png"

    pivot = df.pivot_table(index="hour", columns="event_type", values="total", fill_value=0)

    fig, ax = plt.subplots(figsize=(10, 5))
    pivot.plot(kind="bar", ax=ax, color=PALETTE[:len(pivot.columns)], edgecolor="white")

    ax.set_title("Hourly Event Trend by Type", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Hour")
    ax.set_ylabel("Count")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: pivot.index[int(x)].strftime("%m/%d %H:%M") if int(x) < len(pivot) else ""
    ))
    plt.xticks(rotation=45, ha="right", fontsize=8)
    ax.legend(title="Event Type", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()

    out = CHARTS_DIR / "events_hourly.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"[viz] saved: {out}")
    return out


# ── Chart 3: 에러율 TOP 10 유저 ───────────────────────────────

def plot_error_rate_top_users(conn: psycopg.Connection) -> Path:
    df = _query(conn, """
        SELECT u.user_id,
               u.platform,
               COUNT(e.event_id) AS total_events,
               COUNT(e.event_id) FILTER (WHERE e.event_type = 'error') AS error_count,
               ROUND(
                   COUNT(e.event_id) FILTER (WHERE e.event_type = 'error')
                   * 100.0 / NULLIF(COUNT(e.event_id), 0), 1
               ) AS error_rate_pct
        FROM users u
        JOIN sessions s ON s.user_id = u.user_id
        JOIN events   e ON e.session_id = s.session_id
        GROUP BY u.user_id, u.platform
        HAVING COUNT(e.event_id) > 0
        ORDER BY error_rate_pct DESC, total_events DESC
        LIMIT 10
    """)

    df["user_short"] = df["user_id"].astype(str).str[:8] + f"…\n(" + df["platform"] + ")"

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = [PALETTE[2] if r < 10 else PALETTE[3] for r in df["error_rate_pct"]]
    bars = ax.barh(df["user_short"], df["error_rate_pct"], color=colors, edgecolor="white")

    for bar, val in zip(bars, df["error_rate_pct"]):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                f"{val}%", va="center", fontsize=9)

    ax.set_title("Error Rate by User — Top 10", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Error Rate (%)")
    ax.invert_yaxis()
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()

    out = CHARTS_DIR / "error_rate_top_users.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"[viz] saved: {out}")
    return out


def main() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        plot_events_by_type(conn)
        plot_events_hourly(conn)
        plot_error_rate_top_users(conn)
    print("[viz] 완료 — docs/charts/ 확인")


if __name__ == "__main__":
    main()
