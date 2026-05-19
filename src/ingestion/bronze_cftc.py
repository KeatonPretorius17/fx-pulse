"""
FX Pulse — Bronze Layer — Step 5: CFTC
=======================================
Downloads the CFTC Traders in Financial Futures (TFF) annual zip,
extracts the CSV in memory, filters to GBP rows only, and saves
as raw.csv into a dated folder.

Run:
    python src/ingestion/bronze_cftc.py

Expected output:
    data/bronze/cftc/gbp_futures/2026/05/18/raw.csv
"""

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
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
        / "cftc"
        / "gbp_futures"
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "raw.csv"

# ---------------------------------------------------------------------------
# Fetch and save
# ---------------------------------------------------------------------------

def fetch_cftc() -> None:
    out_path = dated_path()
    year     = RUN_DATE.year
    zip_url  = f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"

    print(f"  Downloading CFTC TFF zip for {year}...")
    print(f"  URL: {zip_url}")

    resp = requests.get(zip_url, timeout=60)
    resp.raise_for_status()

    print(f"  Download complete ({len(resp.content) / 1024 / 1024:.1f} MB)")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        names     = z.namelist()
        txt_files = [n for n in names if n.lower().endswith(".txt")]

        if not txt_files:
            print(f"  ERROR: no .txt file found in zip. Contents: {names}")
            return

        print(f"  CSV inside zip: {txt_files[0]}")

        with z.open(txt_files[0]) as f:
            # latin-1 is the correct encoding for CFTC files.
            # UTF-8 silently corrupts field values which was the original
            # bug — the contract name matched nothing after corruption.
            df = pd.read_csv(f, encoding="latin-1", low_memory=False)

    print(f"  Full TFF: {len(df)} rows, {len(df.columns)} columns")

    # Confirm the column we need exists
    name_col = "Market_and_Exchange_Names"
    if name_col not in df.columns:
        print(f"  ERROR: column '{name_col}' not found.")
        print(f"  Available columns: {df.columns.tolist()}")
        return

    # str.contains is robust — handles whitespace and minor field variations
    gbp_mask = df[name_col].str.contains("BRITISH POUND", na=False, case=False)
    gbp_df   = df[gbp_mask].copy()

    if gbp_df.empty:
        print("  ERROR: no GBP rows matched. Sample market names:")
        for name in df[name_col].dropna().unique()[:15]:
            print(f"    '{name}'")
        return

    # Print a summary of what we found
    date_col = "Report_Date_as_YYYY-MM-DD"
    print(f"  GBP rows found: {len(gbp_df)}")
    if date_col in gbp_df.columns:
        print(f"  Date range: {gbp_df[date_col].min()} to {gbp_df[date_col].max()}")

    # Save with metadata header
    meta_header = (
        f"# source: cftc_tff\n"
        f"# zip_url: {zip_url}\n"
        f"# filter: {name_col} contains 'BRITISH POUND'\n"
        f"# rows: {len(gbp_df)}\n"
        f"# run_date: {RUN_DATE.strftime('%Y-%m-%d')}\n"
        f"# fetched_at: {datetime.now(timezone.utc).isoformat()}\n"
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(meta_header + gbp_df.to_csv(index=False))

    print(f"  Saved → {out_path}")
    print()

    # Print the last 3 rows so we can see the most recent COT report
    print("  Latest 3 reports:")
    if date_col in gbp_df.columns:
        latest = gbp_df.sort_values(date_col).tail(3)
        cols_to_show = [
            date_col,
            "Lev_Money_Positions_Long_All",
            "Lev_Money_Positions_Short_All",
        ]
        # Only print columns that exist
        cols_to_show = [c for c in cols_to_show if c in latest.columns]
        for _, row in latest[cols_to_show].iterrows():
            print(f"    {row.to_dict()}")
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Bronze   : {BRONZE_ROOT}")
    print()

    try:
        fetch_cftc()
    except Exception as e:
        print(f"  ERROR: {e}")

    print("Done — check data/bronze/cftc/ to confirm the file is there.")

if __name__ == "__main__":
    main()