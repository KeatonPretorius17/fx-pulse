"""
FX Pulse — Bronze Layer — Step 1: Oanda
========================================
Fetches daily OHLC candles for GBP/USD and EUR/GBP
and saves them as raw.json into dated folders.

Run:
    python bronze_oanda.py

Expected output:
    data/bronze/oanda/GBP_USD/2026/05/18/raw.json
    data/bronze/oanda/EUR_GBP/2026/05/18/raw.json
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import oandapyV20
import oandapyV20.endpoints.instruments as oanda_instruments
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

OANDA_TOKEN = os.getenv("OANDA_API_TOKEN")
RUN_DATE    = datetime.now(timezone.utc)
BRONZE_ROOT = Path(__file__).parent.parent.parent / "data" / "bronze"

# ---------------------------------------------------------------------------
# Helper — create the dated folder and return the output path
# ---------------------------------------------------------------------------

def dated_path(pair: str) -> Path:
    folder = (
        BRONZE_ROOT
        / "oanda"
        / pair
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "raw.json"

# ---------------------------------------------------------------------------
# Fetch and save
# ---------------------------------------------------------------------------

def fetch_pair(client, pair: str) -> None:
    out_path = dated_path(pair)

    params = {
        "count":       5,       # last 5 daily candles — Silver filters to today
        "granularity": "D",     # daily bars match our signal frequency
        "price":       "M",     # mid-point (average of bid and ask)
    }

    print(f"  Fetching {pair}...")

    r = oanda_instruments.InstrumentsCandles(instrument=pair, params=params)
    client.request(r)

    payload = r.response
    payload["_meta"] = {
        "source":      "oanda",
        "instrument":  pair,
        "granularity": "D",
        "count":       5,
        "run_date":    RUN_DATE.strftime("%Y-%m-%d"),
        "fetched_at":  datetime.now(timezone.utc).isoformat() + "Z",
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    # Quick sanity check — print the candles so you can see what arrived
    candles = payload.get("candles", [])
    print(f"  Saved {len(candles)} candles → {out_path}")
    print()
    for c in candles:
        print(f"    {c['time'][:10]}  open={c['mid']['o']}  close={c['mid']['c']}  complete={c['complete']}")
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not OANDA_TOKEN:
        print("ERROR: OANDA_API_TOKEN not found in .env")
        return

    client = oandapyV20.API(access_token=OANDA_TOKEN, environment="practice")
    pairs  = ["GBP_USD", "EUR_GBP"]

    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Bronze   : {BRONZE_ROOT}")
    print()

    for pair in pairs:
        try:
            fetch_pair(client, pair)
        except Exception as e:
            print(f"  ERROR on {pair}: {e}")

    print("Done — check data/bronze/oanda/ to confirm files are there.")

if __name__ == "__main__":
    main()