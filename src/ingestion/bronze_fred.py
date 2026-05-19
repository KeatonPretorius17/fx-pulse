"""
FX Pulse — Bronze Layer — Step 3: FRED
=======================================
Fetches US interest rate series from the Federal Reserve
and saves them as raw.json into dated folders.

Series:
    DFF     — Effective Federal Funds Rate (daily)
    T10Y2Y  — 10-Year minus 2-Year Treasury yield spread (daily)

Run:
    python src/ingestion/bronze_fred.py

Expected output:
    data/bronze/fred/DFF/2026/05/18/raw.json
    data/bronze/fred/T10Y2Y/2026/05/18/raw.json
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

FRED_KEY    = os.getenv("FRED_API_KEY")
RUN_DATE    = datetime.now(timezone.utc)
BRONZE_ROOT = Path(__file__).parent.parent.parent / "data" / "bronze"

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def dated_path(series_id: str) -> Path:
    folder = (
        BRONZE_ROOT
        / "fred"
        / series_id
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "raw.json"

# ---------------------------------------------------------------------------
# Fetch and save
# ---------------------------------------------------------------------------

def fetch_series(fred: Fred, series_id: str) -> None:
    out_path = dated_path(series_id)

    # 10-day window — FRED sometimes lags 1-3 business days
    # so this guarantees the latest actual observation is captured
    end_str   = RUN_DATE.strftime("%Y-%m-%d")
    start_str = (RUN_DATE - timedelta(days=10)).strftime("%Y-%m-%d")

    print(f"  Fetching {series_id}...")

    series = fred.get_series(
        series_id,
        observation_start=start_str,
        observation_end=end_str,
    )

    observations = [
        {
            "date":  str(date.date()),
            "value": None if pd.isna(val) else float(val),
        }
        for date, val in series.items()
    ]

    payload = {
        "_meta": {
            "source":            "fred",
            "series_id":         series_id,
            "observation_start": start_str,
            "observation_end":   end_str,
            "run_date":          RUN_DATE.strftime("%Y-%m-%d"),
            "fetched_at":        datetime.now(timezone.utc).isoformat(),
        },
        "observations": observations,
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"  Saved {len(observations)} observations → {out_path}")
    print()
    for obs in observations:
        print(f"    {obs['date']}  value={obs['value']}")
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not FRED_KEY:
        print("ERROR: FRED_API_KEY not found in .env")
        return

    fred        = Fred(api_key=FRED_KEY)
    series_list = ["DFF", "T10Y2Y"]

    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Bronze   : {BRONZE_ROOT}")
    print()

    for series_id in series_list:
        try:
            fetch_series(fred, series_id)
        except Exception as e:
            print(f"  ERROR on {series_id}: {e}")

    print("Done — check data/bronze/fred/ to confirm files are there.")

if __name__ == "__main__":
    main()