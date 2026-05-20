"""
FX Pulse — Silver Layer — Step 2: yfinance
===========================================
Reads the raw Bronze yfinance JSON, cleans and types it,
and writes a clean Parquet file to Silver.

What this does:
    - Extracts the data array from the raw JSON
    - Casts date to date type, OHLCV to correct numerics
    - Keeps only the most recent trading day row

Run:
    python src/ingestion/silver_yfinance.py

Expected output:
    data/silver/yfinance/SPY/2026/05/19/clean.parquet
    data/silver/yfinance/GLD/2026/05/19/clean.parquet
    data/silver/yfinance/TLT/2026/05/19/clean.parquet
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RUN_DATE    = datetime.now(timezone.utc)
BRONZE_ROOT = Path(__file__).parent.parent.parent / "data" / "bronze"
SILVER_ROOT = Path(__file__).parent.parent.parent / "data" / "silver"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def bronze_path(ticker: str) -> Path:
    # Find the most recent raw.json for this ticker
    search = BRONZE_ROOT / "yfinance" / ticker
    files  = sorted(search.rglob("raw.json"))
    if not files:
        return search / "not_found"
    return files[-1]

def silver_path(ticker: str) -> Path:
    folder = (
        SILVER_ROOT
        / "yfinance"
        / ticker
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "clean.parquet"

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

def clean_ticker(ticker: str) -> None:
    src = bronze_path(ticker)
    dst = silver_path(ticker)

    if not src.exists():
        print(f"  ERROR: Bronze file not found: {src}")
        return

    with open(src) as f:
        raw = json.load(f)

    records = raw.get("data", [])
    print(f"  Raw rows received : {len(records)}")

    df = pd.DataFrame(records)

    # Cast types
    df["date"]   = pd.to_datetime(df["date"]).dt.date
    df["Open"]   = pd.to_numeric(df["Open"],   errors="coerce")
    df["High"]   = pd.to_numeric(df["High"],   errors="coerce")
    df["Low"]    = pd.to_numeric(df["Low"],    errors="coerce")
    df["Close"]  = pd.to_numeric(df["Close"],  errors="coerce")
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").astype("Int64")

    # Rename to lowercase to match the rest of the project
    df = df.rename(columns={
        "Open":   "open",
        "High":   "high",
        "Low":    "low",
        "Close":  "close",
        "Volume": "volume",
    })

    # Drop any rows where close is null
    before = len(df)
    df = df.dropna(subset=["close"])
    after  = len(df)
    if before != after:
        print(f"  Dropped {before - after} null rows")

    print(f"  Rows after cleaning : {len(df)}")

    if df.empty:
        print(f"  WARNING: no clean data for {ticker}")
        return

    # Keep only the most recent trading day
    df = df.sort_values("date").tail(1).reset_index(drop=True)
    print(f"  Kept most recent row: {df['date'].iloc[0]}")

    # Add source column
    df["ticker"] = ticker
    df["source"] = "yfinance"

    # Drop columns we don't need downstream
    drop_cols = [c for c in ["Adj Close", "adj_close"] if c in df.columns]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    df.to_parquet(dst, index=False)
    print(f"  Saved → {dst}")
    print()
    print(df.to_string(index=False))
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    tickers = ["SPY", "GLD", "TLT"]

    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Silver   : {SILVER_ROOT}")
    print()

    for ticker in tickers:
        print(f"[{ticker}]")
        try:
            clean_ticker(ticker)
        except Exception as e:
            print(f"  ERROR: {e}")
        print()

    print("Done — check data/silver/yfinance/ to confirm files are there.")

if __name__ == "__main__":
    main()