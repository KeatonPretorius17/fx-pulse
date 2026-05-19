"""
FX Pulse — Silver Layer — Step 1: Oanda
========================================
Reads the raw Bronze Oanda JSON, cleans and types it,
and writes a clean Parquet file to Silver.

What this does:
    - Extracts the candles array from the raw JSON
    - Parses timestamps to dates
    - Casts OHLC values to float
    - Drops incomplete candles (partial trading days)
    - Keeps only the most recent complete candle

Run:
    python src/ingestion/silver_oanda.py

Expected output:
    data/silver/oanda/GBP_USD/2026/05/18/clean.parquet
    data/silver/oanda/EUR_GBP/2026/05/18/clean.parquet
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

def bronze_path(pair: str) -> Path:
    # Find the most recent raw.json for this pair rather than
    # assuming it was created today
    search = BRONZE_ROOT / "oanda" / pair
    files  = sorted(search.rglob("raw.json"))
    if not files:
        return search / "not_found"
    return files[-1]  # most recent


def silver_path(pair: str) -> Path:
    folder = (
        SILVER_ROOT
        / "oanda"
        / pair
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "clean.parquet"

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

def clean_pair(pair: str) -> None:
    src = bronze_path(pair)
    dst = silver_path(pair)

    if not src.exists():
        print(f"  ERROR: Bronze file not found: {src}")
        return

    with open(src) as f:
        raw = json.load(f)

    candles = raw.get("candles", [])
    print(f"  Raw candles received : {len(candles)}")

    # Build a flat list of records from the nested candle structure
    records = []
    for c in candles:
        records.append({
            "date":      c["time"][:10],           # "2026-05-17T..." → "2026-05-17"
            "open":      float(c["mid"]["o"]),
            "high":      float(c["mid"]["h"]),
            "low":       float(c["mid"]["l"]),
            "close":     float(c["mid"]["c"]),
            "volume":    int(c.get("volume", 0)),
            "complete":  bool(c["complete"]),
            "pair":      pair,
            "source":    "oanda",
        })

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    print(f"  Before filtering      : {len(df)} rows")

    # Drop incomplete candles — partial days have unreliable OHLC
    df = df[df["complete"] == True].copy()
    print(f"  After dropping incomplete: {len(df)} rows")

    if df.empty:
        print(f"  WARNING: no complete candles for {pair} — market may still be open")
        return

    # Keep only the most recent complete candle
    df = df.sort_values("date").tail(1).reset_index(drop=True)
    print(f"  Kept most recent row  : {df['date'].iloc[0]}")

    # Drop the complete column — it's always True at this point
    df = df.drop(columns=["complete"])

    df.to_parquet(dst, index=False)
    print(f"  Saved → {dst}")
    print()
    print(df.to_string(index=False))
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    pairs = ["GBP_USD", "EUR_GBP"]

    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Silver   : {SILVER_ROOT}")
    print()

    for pair in pairs:
        print(f"[{pair}]")
        try:
            clean_pair(pair)
        except Exception as e:
            print(f"  ERROR: {e}")
        print()

    print("Done — check data/silver/oanda/ to confirm files are there.")

if __name__ == "__main__":
    main()