"""
FX Pulse — Bronze Layer — Step 4: Bank of England
==================================================
Fetches the UK Official Bank Rate from the BoE CSV endpoint
and saves it as raw.csv into a dated folder.

Series: IUDBEDR — Official Bank Rate (daily)

Run:
    python src/ingestion/bronze_boe.py

Expected output:
    data/bronze/boe/bank_rate/2026/05/18/raw.csv
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RUN_DATE    = datetime.now(timezone.utc)
BRONZE_ROOT = Path(__file__).parent.parent.parent / "data" / "bronze"

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def dated_path() -> Path:
    folder = (
        BRONZE_ROOT
        / "boe"
        / "bank_rate"
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "raw.csv"

# ---------------------------------------------------------------------------
# Fetch and save
# ---------------------------------------------------------------------------

def fetch_boe() -> None:
    out_path = dated_path()

    url = (
        "https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp"
        "?csv.x=yes"
        "&Datefrom=01/Jan/2020"
        f"&Dateto={RUN_DATE.strftime('%d/%b/%Y')}"
        "&SeriesCodes=IUDBEDR"
        "&CSVF=TN"
        "&UsingCodes=Y"
    )

    headers = {
        # BoE returns 403 without a browser-like User-Agent
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    print(f"  Fetching BoE Bank Rate...")

    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    # Prepend metadata as comment lines so the file is self-describing
    meta_header = (
        f"# source: bank_of_england\n"
        f"# series: IUDBEDR (Official Bank Rate, daily)\n"
        f"# run_date: {RUN_DATE.strftime('%Y-%m-%d')}\n"
        f"# fetched_at: {datetime.now(timezone.utc).isoformat()}\n"
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(meta_header + resp.text)

    # Print the last 5 data lines so we can sanity check the values
    lines = [l for l in resp.text.strip().split("\n") if l.strip()]
    print(f"  Saved {len(lines) - 1} rows → {out_path}")
    print()
    print("  Last 5 rows:")
    for line in lines[-5:]:
        print(f"    {line[:60]}")
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Bronze   : {BRONZE_ROOT}")
    print()

    try:
        fetch_boe()
    except Exception as e:
        print(f"  ERROR: {e}")

    print("Done — check data/bronze/boe/ to confirm the file is there.")

if __name__ == "__main__":
    main()