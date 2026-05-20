"""
FX Pulse — Silver Layer — Step 4: Bank of England
==================================================
Reads the raw Bronze BoE CSV, cleans and types it,
and writes a clean Parquet file to Silver.

What this does:
    - Skips the 4 metadata comment lines at the top
    - Parses the BoE date format ("11 May 2026" -> date)
    - Casts the rate value to float
    - Drops nulls
    - Keeps only the most recent row

Run:
    python src/ingestion/silver_boe.py

Expected output:
    data/silver/boe/bank_rate/2026/05/19/clean.parquet
"""

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

def bronze_path() -> Path:
    search = BRONZE_ROOT / "boe" / "bank_rate"
    files  = sorted(search.rglob("raw.csv"))
    if not files:
        return search / "not_found"
    return files[-1]

def silver_path() -> Path:
    folder = (
        SILVER_ROOT
        / "boe"
        / "bank_rate"
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "clean.parquet"

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

def clean_boe() -> None:
    src = bronze_path()
    dst = silver_path()

    if not src.exists():
        print(f"  ERROR: Bronze file not found: {src}")
        return

    # Skip the 4 comment lines at the top (lines starting with #)
    df = pd.read_csv(src, comment="#", header=0)
    print(f"  Raw rows received : {len(df)}")
    print(f"  Columns           : {df.columns.tolist()}")

    # BoE CSV columns are typically: date_column, IUDBEDR
    # Rename to standard names regardless of what BoE calls them
    df.columns = ["date", "value"]

    # Parse BoE date format: "11 May 2026"
    df["date"]  = pd.to_datetime(df["date"], format="%d %b %Y").dt.date
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    # Drop nulls
    before = len(df)
    df = df.dropna(subset=["value"])
    after  = len(df)
    if before != after:
        print(f"  Dropped {before - after} null rows")

    print(f"  Rows after cleaning : {len(df)}")

    if df.empty:
        print("  WARNING: no clean data for BoE bank rate")
        return

    # Keep only the most recent row
    df = df.sort_values("date").tail(1).reset_index(drop=True)
    print(f"  Kept most recent row: {df['date'].iloc[0]}  value={df['value'].iloc[0]}")

    # Add source columns
    df["series_id"] = "IUDBEDR"
    df["source"]    = "boe"

    df.to_parquet(dst, index=False)
    print(f"  Saved → {dst}")
    print()
    print(df.to_string(index=False))
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Silver   : {SILVER_ROOT}")
    print()

    print("[BoE Bank Rate]")
    try:
        clean_boe()
    except Exception as e:
        print(f"  ERROR: {e}")

    print("Done — check data/silver/boe/ to confirm the file is there.")

if __name__ == "__main__":
    main()