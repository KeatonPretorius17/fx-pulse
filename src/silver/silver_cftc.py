"""
FX Pulse — Silver Layer — Step 5: CFTC
=======================================
Reads the raw Bronze CFTC CSV, cleans and types it,
and writes a clean Parquet file to Silver.

What this does:
    - Skips the 6 metadata comment lines at the top
    - Filters to the main futures contract only (drops the options row)
    - Keeps only the columns needed for the COT crossover signal
    - Casts date and positioning columns to correct types
    - Keeps only the most recent report

Columns kept:
    date            — report date
    long            — leveraged fund long positions
    short           — leveraged fund short positions
    net             — long minus short (calculated)
    open_interest   — total open interest

Run:
    python src/ingestion/silver_cftc.py

Expected output:
    data/silver/cftc/gbp_futures/2026/05/19/clean.parquet
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
    search = BRONZE_ROOT / "cftc" / "gbp_futures"
    files  = sorted(search.rglob("raw.csv"))
    if not files:
        return search / "not_found"
    return files[-1]

def silver_path() -> Path:
    folder = (
        SILVER_ROOT
        / "cftc"
        / "gbp_futures"
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "clean.parquet"

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

def clean_cftc() -> None:
    src = bronze_path()
    dst = silver_path()

    if not src.exists():
        print(f"  ERROR: Bronze file not found: {src}")
        return

    # Skip the 6 comment lines at the top (lines starting with #)
    df = pd.read_csv(src, comment="#", low_memory=False)
    print(f"  Raw rows received : {len(df)}")
    print(f"  Contracts found   :")
    for name in df["Market_and_Exchange_Names"].unique():
        print(f"    '{name}'")

    # Two rows per report date — main futures contract and a smaller options
    # contract. The main contract has far larger open interest.
    # Filter to the main futures contract by keeping the row with the
    # largest open interest per report date.
    date_col = "Report_Date_as_YYYY-MM-DD"
    oi_col   = "Open_Interest_All"

    df[oi_col] = pd.to_numeric(df[oi_col], errors="coerce")
    df = (
        df.sort_values(oi_col, ascending=False)
          .groupby(date_col, as_index=False)
          .first()
    )
    print(f"  After keeping main contract per date: {len(df)} rows")

    # Keep only the columns we need downstream
    cols_needed = {
        date_col:                        "date",
        "Lev_Money_Positions_Long_All":  "long",
        "Lev_Money_Positions_Short_All": "short",
        oi_col:                          "open_interest",
    }

    missing = [c for c in cols_needed if c not in df.columns]
    if missing:
        print(f"  ERROR: missing columns: {missing}")
        print(f"  Available: {df.columns.tolist()}")
        return

    df = df[list(cols_needed.keys())].rename(columns=cols_needed)

    # Cast types
    df["date"]          = pd.to_datetime(df["date"]).dt.date
    df["long"]          = pd.to_numeric(df["long"],          errors="coerce")
    df["short"]         = pd.to_numeric(df["short"],         errors="coerce")
    df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce")

    # Calculate net positioning — positive means leveraged funds are net long GBP
    df["net"] = df["long"] - df["short"]

    # Drop nulls
    before = len(df)
    df = df.dropna()
    after  = len(df)
    if before != after:
        print(f"  Dropped {before - after} null rows")

    print(f"  Rows after cleaning : {len(df)}")

    if df.empty:
        print("  WARNING: no clean data for CFTC GBP futures")
        return

    # Keep only the most recent report
    df = df.sort_values("date").tail(1).reset_index(drop=True)
    print(f"  Kept most recent row: {df['date'].iloc[0]}")

    # Add source columns
    df["contract"] = "GBP_FUTURES"
    df["source"]   = "cftc"

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

    print("[CFTC GBP Futures]")
    try:
        clean_cftc()
    except Exception as e:
        print(f"  ERROR: {e}")

    print("Done — check data/silver/cftc/ to confirm the file is there.")

if __name__ == "__main__":
    main()