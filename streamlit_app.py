from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import sqlite3


DB_FILENAME = "trades.db"
WEEKLY_SUMMARY_FILENAME = "weekly_summary.csv"
EQUITY_CURVE_PNG = "equity_curve.png"
WEEKLY_PNL_PNG = "weekly_pnl.png"
WEEKLY_WINRATE_PNG = "weekly_winrate.png"


@dataclass
class Metrics:
    total_trades: int
    total_profit: float
    total_loss: float
    net_pnl: float
    win_rate_pct: float
    average_win: float
    average_loss: float
    current_equity: float
    weeks_to_target: Optional[int]


def get_project_root() -> Path:
    return Path(__file__).resolve().parent


def get_db_path() -> Path:
    return get_project_root() / DB_FILENAME


def ensure_db() -> None:
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                type TEXT NOT NULL,
                profit REAL NOT NULL DEFAULT 0,
                loss REAL NOT NULL DEFAULT 0,
                fees REAL NOT NULL DEFAULT 0,
                notes TEXT
            )
            """
        )
        conn.commit()


def load_trades() -> pd.DataFrame:
    ensure_db()
    with sqlite3.connect(get_db_path()) as conn:
        df = pd.read_sql_query(
            """
            SELECT date, symbol, type, profit, loss, fees, notes
            FROM trades
            WHERE symbol = ?
            ORDER BY date, symbol
            """,
            conn,
            params=("BTCUSD",),
        )

    if df.empty:
        # Ensure expected columns exist even when empty
        df = pd.DataFrame(
            columns=["date", "symbol", "type", "profit", "loss", "fees", "notes"]
        )

    # Parse dates; coerce malformed to NaT
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Standardize numeric columns
    for col in ["profit", "loss", "fees"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    # Compute PnL related columns
    if not df.empty:
        df["pnl"] = df["profit"] - df["loss"] - df["fees"]
        df["is_win"] = df["pnl"] > 0
        df["is_loss"] = df["pnl"] < 0
        # Sort by date when available
        if "date" in df.columns:
            df = df.sort_values(by=["date", "symbol"], ascending=[True, True])
            df = df.reset_index(drop=True)
    else:
        df = pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "type",
                "profit",
                "loss",
                "fees",
                "notes",
                "pnl",
                "is_win",
                "is_loss",
            ]
        )

    return df


def compute_weekly_summary(df: pd.DataFrame) -> Tuple[pd.DataFrame, float]:
    if df.empty:
        return pd.DataFrame(), 0.0

    # Handle missing or malformed dates by excluding from weekly grouping
    valid_dates = df[df["date"].notna()].copy()
    if valid_dates.empty:
        return pd.DataFrame(), 0.0

    # Compute week start timestamps
    periods = valid_dates["date"].dt.to_period("W")
    week_start = periods.apply(
        lambda p: getattr(p, "start_time", None) if hasattr(p, "start_time") else p.to_timestamp()
    )
    valid_dates = valid_dates.assign(week_start=week_start)

    grouped = valid_dates.groupby("week_start")
    weekly = pd.DataFrame(
        {
            "trades": grouped.size(),
            "wins": grouped["is_win"].sum(),
            "losses": grouped["is_loss"].sum(),
            "total_profit": grouped["profit"].sum(),
            "total_loss": grouped["loss"].sum(),
            "total_pnl": grouped["pnl"].sum(),
        }
    )
    weekly["win_rate_%"] = (weekly["wins"] / weekly["trades"]) * 100.0
    weekly = weekly.reset_index().sort_values("week_start")

    avg_weekly_pnl = weekly["total_pnl"].mean() if not weekly.empty else 0.0
    return weekly, float(avg_weekly_pnl)


def compute_metrics(df: pd.DataFrame, start_balance: float, target_equity: float) -> Metrics:
    total_trades = int(len(df))
    total_profit = float(df["profit"].sum()) if not df.empty else 0.0
    total_loss = float(df["loss"].sum()) if not df.empty else 0.0
    net_pnl = float(df["pnl"].sum()) if "pnl" in df.columns else 0.0

    wins = int(df["is_win"].sum()) if "is_win" in df.columns else 0
    win_rate_pct = (wins / total_trades * 100.0) if total_trades > 0 else 0.0

    average_win = (
        float(df.loc[df["pnl"] > 0, "pnl"].mean()) if not df.empty and (df["pnl"] > 0).any() else 0.0
    )
    average_loss = (
        float(df.loc[df["pnl"] < 0, "pnl"].mean()) if not df.empty and (df["pnl"] < 0).any() else 0.0
    )

    current_equity = float(start_balance + net_pnl)

    weekly, avg_weekly_pnl = compute_weekly_summary(df)
    _save_weekly_summary_to_disk(weekly)

    # Weeks to target per plan: if avg_weekly_pnl <= 0, or result <= 0 => N/A
    weeks_to_target: Optional[int]
    if avg_weekly_pnl <= 0:
        weeks_to_target = None
    else:
        remaining = target_equity - current_equity
        if remaining <= 0:
            weeks_to_target = None  # Clamp negative/zero to N/A per plan
        else:
            weeks_to_target = int(math.ceil(remaining / avg_weekly_pnl))

    return Metrics(
        total_trades=total_trades,
        total_profit=total_profit,
        total_loss=total_loss,
        net_pnl=net_pnl,
        win_rate_pct=win_rate_pct,
        average_win=average_win,
        average_loss=average_loss,
        current_equity=current_equity,
        weeks_to_target=weeks_to_target,
    )


def _save_weekly_summary_to_disk(weekly: pd.DataFrame) -> None:
    output_path = get_project_root() / WEEKLY_SUMMARY_FILENAME
    if weekly is None or weekly.empty:
        # Write an empty file with headers for consistency
        empty_df = pd.DataFrame(
            columns=[
                "week_start",
                "trades",
                "wins",
                "losses",
                "total_profit",
                "total_loss",
                "total_pnl",
                "win_rate_%",
            ]
        )
        empty_df.to_csv(output_path, index=False)
        return
    weekly.to_csv(output_path, index=False)


def _plot_equity_curve(df: pd.DataFrame, start_balance: float) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 4))
    if df.empty:
        ax.set_title("Equity Curve (no data)")
        ax.set_xlabel("Date")
        ax.set_ylabel("Equity (USD)")
        fig.tight_layout()
        return fig

    # Ensure sorted by date
    df_sorted = df.sort_values("date").copy()
    equity = start_balance + df_sorted["pnl"].cumsum()
    ax.plot(df_sorted["date"], equity)
    ax.set_title("Equity Curve")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity (USD)")
    fig.tight_layout()
    # Save image
    fig.savefig(get_project_root() / EQUITY_CURVE_PNG, dpi=150)
    return fig


def _plot_weekly_pnl(weekly: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 4))
    if weekly is None or weekly.empty:
        ax.set_title("Weekly Total P&L (no data)")
        ax.set_xlabel("Week Start")
        ax.set_ylabel("Total P&L (USD)")
        fig.tight_layout()
        return fig

    ax.bar(weekly["week_start"], weekly["total_pnl"])
    ax.set_title("Weekly Total P&L")
    ax.set_xlabel("Week Start")
    ax.set_ylabel("Total P&L (USD)")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(get_project_root() / WEEKLY_PNL_PNG, dpi=150)
    return fig


def _plot_weekly_winrate(weekly: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 4))
    if weekly is None or weekly.empty:
        ax.set_title("Weekly Win Rate (no data)")
        ax.set_xlabel("Week Start")
        ax.set_ylabel("Win Rate (%)")
        fig.tight_layout()
        return fig

    ax.bar(weekly["week_start"], weekly["win_rate_%"])
    ax.set_title("Weekly Win Rate")
    ax.set_xlabel("Week Start")
    ax.set_ylabel("Win Rate (%)")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(get_project_root() / WEEKLY_WINRATE_PNG, dpi=150)
    return fig


def append_trade(
    trade_date: datetime,
    trade_type: str,
    profit: float,
    loss: float,
    fees: float,
    notes: str,
) -> None:
    ensure_db()
    with sqlite3.connect(get_db_path()) as conn:
        conn.execute(
            """
            INSERT INTO trades (date, symbol, type, profit, loss, fees, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_date.isoformat(),
                "BTCUSD",
                trade_type,
                float(profit),
                float(loss),
                float(fees or 0.0),
                (notes or "").replace("\n", " ").strip(),
            ),
        )
        conn.commit()


def render_kpi_tiles(metrics: Metrics) -> None:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Trades", metrics.total_trades)
        st.metric("Win rate", f"{metrics.win_rate_pct:.1f}%")
    with c2:
        st.metric("Avg win", f"${metrics.average_win:,.2f}")
        st.metric("Avg loss", f"${metrics.average_loss:,.2f}")
    with c3:
        st.metric("Total won", f"${metrics.total_profit:,.2f}")
        st.metric("Total lost", f"${metrics.total_loss:,.2f}")
    with c4:
        st.metric("Net P&L", f"${metrics.net_pnl:,.2f}")
        weeks_value = "N/A" if metrics.weeks_to_target is None else str(metrics.weeks_to_target)
        st.metric("Weeks to target", weeks_value)
    st.metric("Current equity", f"${metrics.current_equity:,.2f}")


def main() -> None:
    st.set_page_config(page_title="BTCUSD Trade Tracker", layout="wide")
    st.title("BTCUSD Trade Tracker")

    df = load_trades()

    # Sidebar inputs
    st.sidebar.header("Settings")
    start_balance = st.sidebar.number_input(
        "Start balance (USD)", min_value=0.0, value=1000.0, step=100.0, format="%.2f"
    )
    target_equity = st.sidebar.number_input(
        "Target equity (USD)", min_value=0.0, value=5000.0, step=100.0, format="%.2f"
    )

    # Trade input form
    st.subheader("Add Trade")
    with st.form(key="add_trade_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            trade_date_input: date = st.date_input("Date", value=date.today())
            trade_type = st.selectbox("Type", options=["LONG", "SHORT"], index=0)
        with col2:
            profit = st.number_input("Profit (USD)", min_value=0.0, value=0.0, step=10.0, format="%.2f")
            loss = st.number_input("Loss (USD)", min_value=0.0, value=0.0, step=10.0, format="%.2f")
        with col3:
            fees = st.number_input("Fees (USD)", min_value=0.0, value=0.0, step=1.0, format="%.2f")
            notes = st.text_input("Notes", value="")

        submitted = st.form_submit_button("Add Trade")

    if submitted:
        # Validation: exactly one of profit or loss must be > 0
        num_positive = int(profit > 0) + int(loss > 0)
        if num_positive != 1:
            st.warning("Enter either a Profit OR a Loss (not both), and one must be > 0.")
        else:
            # Convert date to datetime at midnight
            trade_datetime = datetime.combine(trade_date_input, datetime.min.time())
            append_trade(
                trade_date=trade_datetime,
                trade_type=trade_type,
                profit=profit,
                loss=loss,
                fees=fees or 0.0,
                notes=notes,
            )
            st.success("Trade added.")
            # Reload data after append
            df = load_trades()

    # KPIs and charts
    metrics = compute_metrics(df, start_balance=start_balance, target_equity=target_equity)
    render_kpi_tiles(metrics)

    weekly, _ = compute_weekly_summary(df)

    col_a, col_b = st.columns(2)
    with col_a:
        st.pyplot(_plot_equity_curve(df, start_balance=start_balance))
    with col_b:
        st.pyplot(_plot_weekly_pnl(weekly))
    st.pyplot(_plot_weekly_winrate(weekly))

    st.subheader("Ledger")
    # Display a clean table view (without helper columns)
    display_cols = ["date", "symbol", "type", "profit", "loss", "fees", "notes", "pnl"]
    display_df = df.copy()
    if not display_df.empty and "date" in display_df.columns:
        display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")
    st.dataframe(display_df[display_cols] if not display_df.empty else display_df)


if __name__ == "__main__":
    main()


