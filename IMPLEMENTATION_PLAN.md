# BTCUSD Trade Tracker — Implementation Plan

This plan guides an AI agent to build an interactive trade tracker for BTCUSD that records trades and reports weekly stats, win/loss averages, time-to-target, total money won/lost, and win rate. The solution uses Python, pandas, matplotlib, and Streamlit.

## Objectives
- Append daily trade results with **type** (LONG/SHORT), **profit**, **loss**, **fees**, and **date**.
- Persist data to `trades.csv`.
- Compute and display: total money won, total money lost, net P&L, win rate, average win, average loss, equity curve, weekly totals, weeks to target given initial balance and target.
- Provide clean visualizations and a table view of the ledger.

## Tech stack
- Python 3.10+
- pandas for data handling
- matplotlib for charts (no seaborn, one chart per figure, no custom colors)
- Streamlit for UI (`streamlit run streamlit_app.py`)

## File structure
/project-root
├─ trades.csv # ledger (append-only)
├─ streamlit_app.py # interactive app
├─ IMPLEMENTATION_PLAN.md # this file
└─ (generated)
├─ weekly_summary.csv
├─ equity_curve.png
├─ weekly_pnl.png
└─ weekly_winrate.png


## Data model

`trades.csv` columns:
- `date` (ISO datetime string)
- `symbol` (e.g., "BTCUSD")
- `type` ("LONG" | "SHORT")
- `profit` (float, USD >= 0)
- `loss` (float, USD >= 0)
- `fees` (float, USD >= 0)
- `notes` (string)

Computed:
- `pnl = profit - loss - fees`
- `is_win = pnl > 0`
- `is_loss = pnl < 0`

## Core calculations
- **Total money won** = sum(`profit`)
- **Total money lost** = sum(`loss`)
- **Net P&L** = sum(`pnl`)
- **Win rate** = wins / total trades * 100 where win = `pnl > 0`
- **Avg win** = mean(`pnl` | `pnl > 0`)
- **Avg loss** = mean(`pnl` | `pnl < 0`)
- **Equity curve** = `start_balance` + cumulative sum of `pnl` by date
- **Weekly grouping** by `date.dt.to_period("W").start_time`:
  - trades, wins, losses, `total_pnl`, `total_profit`, `total_loss`, `win_rate_%`
- **Weeks to target** = (`target_equity` - `current_equity`) / `avg_weekly_pnl`
  - If `avg_weekly_pnl <= 0`, weeks-to-target = N/A
  - Negative result clamped to N/A

## UI requirements (Streamlit)
- Sidebar inputs: `start_balance` (USD), `target_equity` (USD)
- Form to add a trade:
  - Inputs: `date`, `type`, `profit`, `loss`, `fees`, `notes`
  - Validation: only one of `profit` or `loss` can be > 0, not both, and at least one must be > 0
  - On submit: append to `trades.csv`, sort by `date`, refresh
- KPI tiles:
  - Trades, Win rate, Avg win, Avg loss, Total won, Total lost, Net P&L, Current equity, Weeks to target
- Charts:
  - Equity curve (matplotlib)
  - Weekly total P&L (matplotlib)
  - Weekly win rate (matplotlib)
- Table: sorted ledger view

## Edge cases & rules
- Missing or malformed dates => coerce to NaT, exclude from weekly grouping
- If both `profit` and `loss` are entered, show warning and reject
- Fees default to 0 if blank
- When `avg_weekly_pnl` is zero or negative, do not estimate time-to-target
- Persist immediately after each trade is added

## Steps
1. **Bootstrap files**: create `trades.csv` if missing with correct headers.
2. **Data loader**: read CSV, standardize types, filter `symbol == "BTCUSD"`.
3. **Calculations**: compute `pnl`, KPIs, weekly stats, equity curve.
4. **UI**: build sidebar, form, KPI grid, charts, and ledger table.
5. **Validation**: enforce input rules for profit/loss exclusivity.
6. **Persistence**: append to CSV, re-load and re-calc on submit.
7. **Export**: write weekly summary CSV and save charts on each run.
8. **Testing**: add a few sample trades and verify stats and projections.
9. **Docs**: keep this plan up to date; comment code sections clearly.

## How to run
```bash
pip install streamlit pandas matplotlib
streamlit run streamlit_app.py
