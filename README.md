### BTCUSD Trade Tracker

An interactive Streamlit app to record BTCUSD trades and visualize performance: weekly stats, win/loss averages, equity curve, and estimated weeks to reach a target equity.

### Features

- **Append trades** with type (LONG/SHORT), profit, loss, fees, date, notes
- **KPIs**: trades, win rate, avg win/loss, total won/lost, net P&L, current equity, weeks to target
- **Charts**: equity curve, weekly total P&L, weekly win rate (saved to PNGs)
- **Exports**: `weekly_summary.csv`

### Requirements

- Python 3.10+
- Linux/macOS/Windows

### Setup (recommended)

1) Clone the repo and enter the project directory

```bash
git clone <your-repo-url>
cd trading-tool
```

2) Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3) Install dependencies

```bash
pip install -r requirements.txt
```

### Run the app

```bash
streamlit run streamlit_app.py
```

This will open the app in your browser (by default at `http://localhost:8501`).

### Usage

- Set your **Start balance** and **Target equity** in the sidebar.
- Use the **Add Trade** form to record each trade. Validation enforces that exactly one of Profit or Loss is > 0 and Fees default to 0.
- The ledger is now stored in a local SQLite database `trades.db` (no CSV required).
- Charts and `weekly_summary.csv` are written to the project root on each run.

### Data model

Database table `trades` columns: `id`, `date`, `symbol`, `type`, `profit`, `loss`, `fees`, `notes`.
Derived columns used in the app: `pnl`, `is_win`, `is_loss`.

### Notes

- Only the `BTCUSD` symbol is included per plan.
- If average weekly P&L is non-positive, weeks-to-target is shown as N/A.
- Malformed dates are excluded from weekly aggregation.

### Troubleshooting

- If Streamlit says a port is in use, run: `streamlit run streamlit_app.py --server.port 8502`
- If you see missing module errors, re-run dependency install: `pip install -r requirements.txt`


