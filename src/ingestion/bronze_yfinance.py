"""
FX Pulse — Bronze Layer — Step 2: yfinance
===========================================
Fetches daily OHLCV for SPY, GLD and TLT
and saves them as raw.json into dated folders.

Run:
    python src/ingestion/bronze_yfinance.py

Expected output:
    data/bronze/yfinance/SPY/2026/05/18/raw.json
    data/bronze/yfinance/GLD/2026/05/18/raw.json
    data/bronze/yfinance/TLT/2026/05/18/raw.json
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RUN_DATE    = datetime.now(timezone.utc)
BRONZE_ROOT = Path(__file__).parent.parent.parent / "data" / "bronze"

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def dated_path(ticker: str) -> Path:
    folder = (
        BRONZE_ROOT
        / "yfinance"
        / ticker
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "raw.json"

# ---------------------------------------------------------------------------
# Fetch and save
# ---------------------------------------------------------------------------

def fetch_ticker(ticker: str) -> None:
    out_path = dated_path(ticker)

    # 5-day window so we always capture the latest trading day
    # even if run on a weekend or bank holiday
    end_date   = RUN_DATE + timedelta(days=1)
    start_date = RUN_DATE - timedelta(days=5)

    print(f"  Fetching {ticker}...")

    df = yf.download(
        ticker,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        auto_adjust=False,
        progress=False,
    )

    if df.empty:
        print(f"  WARNING: no data returned for {ticker}")
        return

    # yfinance >=0.2 returns MultiIndex columns for single tickers — flatten it
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    records = df.reset_index().rename(columns={"Date": "date"})
    records["date"] = records["date"].astype(str)

    payload = {
        "_meta": {
            "source":     "yfinance",
            "ticker":     ticker,
            "start":      start_date.strftime("%Y-%m-%d"),
            "end":        end_date.strftime("%Y-%m-%d"),
            "run_date":   RUN_DATE.strftime("%Y-%m-%d"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
        "data": records.to_dict(orient="records"),
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"  Saved {len(records)} rows → {out_path}")
    print()
    for _, row in records.iterrows():
        print(f"    {row['date']}  open={row['Open']:.2f}  close={row['Close']:.2f}  volume={int(row['Volume'])}")
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    tickers = ["SPY", "GLD", "TLT"]

    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Bronze   : {BRONZE_ROOT}")
    print()

    for ticker in tickers:
        try:
            fetch_ticker(ticker)
        except Exception as e:
            print(f"  ERROR on {ticker}: {e}")

    print("Done — check data/bronze/yfinance/ to confirm files are there.")

if __name__ == "__main__":
    main()