"""
FX Pulse — Silver Layer — Step 3: FRED
=======================================
Reads the raw Bronze FRED JSON, cleans and types it,
and writes a clean Parquet file to Silver.

What this does:
    - Extracts the observations array from the raw JSON
    - Drops rows where value is null (FRED uses null for missing data)
    - Casts date and value to correct types
    - Keeps only the most recent non-null observation

Run:
    python src/ingestion/silver_fred.py

Expected output:
    data/silver/fred/DFF/2026/05/19/clean.parquet
    data/silver/fred/T10Y2Y/2026/05/19/clean.parquet
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

def bronze_path(series_id: str) -> Path:
    search = BRONZE_ROOT / "fred" / series_id
    files  = sorted(search.rglob("raw.json"))
    if not files:
        return search / "not_found"
    return files[-1]

def silver_path(series_id: str) -> Path:
    folder = (
        SILVER_ROOT
        / "fred"
        / series_id
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "clean.parquet"

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

def clean_series(series_id: str) -> None:
    src = bronze_path(series_id)
    dst = silver_path(series_id)

    if not src.exists():
        print(f"  ERROR: Bronze file not found: {src}")
        return

    with open(src) as f:
        raw = json.load(f)

    observations = raw.get("observations", [])
    print(f"  Raw observations received : {len(observations)}")

    df = pd.DataFrame(observations)

    # Cast types
    df["date"]  = pd.to_datetime(df["date"]).dt.date
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    # Drop nulls — FRED returns null for weekends and bank holidays
    before = len(df)
    df = df.dropna(subset=["value"])
    after  = len(df)
    if before != after:
        print(f"  Dropped {before - after} null rows")

    print(f"  Rows after cleaning : {len(df)}")

    if df.empty:
        print(f"  WARNING: no clean data for {series_id}")
        return

    # Keep only the most recent observation
    df = df.sort_values("date").tail(1).reset_index(drop=True)
    print(f"  Kept most recent row: {df['date'].iloc[0]}  value={df['value'].iloc[0]}")

    # Add source columns
    df["series_id"] = series_id
    df["source"]    = "fred"

    df.to_parquet(dst, index=False)
    print(f"  Saved → {dst}")
    print()
    print(df.to_string(index=False))
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    series_list = ["DFF", "T10Y2Y"]

    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Silver   : {SILVER_ROOT}")
    print()

    for series_id in series_list:
        print(f"[{series_id}]")
        try:
            clean_series(series_id)
        except Exception as e:
            print(f"  ERROR: {e}")
        print()

    print("Done — check data/silver/fred/ to confirm files are there.")

if __name__ == "__main__":
    main()