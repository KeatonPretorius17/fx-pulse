"""
FX Pulse — Gold Layer — Carry Trade Score
==========================================
Reads Silver data for interest rates and FX prices,
calculates the carry trade score for GBP/USD, and
writes the result to Gold.

Formula:
    carry score = (rate_gbp - rate_usd) / volatility

Where:
    rate_gbp    = BoE Official Bank Rate
    rate_usd    = Fed Funds Rate (DFF)
    volatility  = standard deviation of GBP/USD daily close
                  over the last 5 available trading days

A positive score means GBP carries over USD.
A higher absolute score means better risk-adjusted carry.

Run:
    python src/ingestion/gold_carry.py

Expected output:
    data/gold/carry_score/2026/05/19/carry.parquet
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RUN_DATE    = datetime.now(timezone.utc)
SILVER_ROOT = Path(__file__).parent.parent.parent / "data" / "silver"
GOLD_ROOT   = Path(__file__).parent.parent.parent / "data" / "gold"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def latest_parquet(path: Path) -> Path:
    """Find the most recent clean.parquet under a given silver path."""
    files = sorted(path.rglob("clean.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found under {path}")
    return files[-1]

def gold_path() -> Path:
    folder = (
        GOLD_ROOT
        / "carry_score"
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "carry.parquet"

# ---------------------------------------------------------------------------
# Load silver data
# ---------------------------------------------------------------------------

def load_rate(source_path: Path, label: str) -> float:
    """Read a single rate value from a Silver parquet file."""
    f    = latest_parquet(source_path)
    df   = pd.read_parquet(f)
    val  = float(df["value"].iloc[0])
    date = str(df["date"].iloc[0])
    print(f"  {label}: {val}%  (as of {date})")
    return val

def load_fx_volatility() -> float:
    """
    Calculate GBP/USD volatility from all available Silver Oanda files.
    Uses standard deviation of daily close prices across available days.
    We use all available parquet files rather than just today's — this
    gives us a rolling window of recent closes to calculate vol from.
    """
    search = SILVER_ROOT / "oanda" / "GBP_USD"
    files  = sorted(search.rglob("clean.parquet"))

    if not files:
        raise FileNotFoundError("No GBP_USD Silver files found")

    closes = []
    for f in files:
        df = pd.read_parquet(f)
        if "close" in df.columns and not df.empty:
            closes.append(float(df["close"].iloc[0]))

    print(f"  GBP/USD closes available : {closes}")

    if len(closes) < 2:
        # Not enough history yet — use a default volatility estimate
        # This will improve as more daily data accumulates
        print("  WARNING: fewer than 2 data points — using default volatility of 0.005")
        return 0.005

    vol = pd.Series(closes).std()
    print(f"  GBP/USD volatility (std) : {vol:.6f}")
    return vol

# ---------------------------------------------------------------------------
# Calculate carry score
# ---------------------------------------------------------------------------

def calculate_carry() -> None:
    dst = gold_path()

    print("Loading Silver data...")
    print()

    rate_gbp = load_rate(SILVER_ROOT / "boe" / "bank_rate", "BoE rate (GBP)")
    rate_usd = load_rate(SILVER_ROOT / "fred" / "DFF",      "Fed rate (USD)")

    print()
    differential = rate_gbp - rate_usd
    print(f"  Rate differential (GBP - USD) : {differential:.4f}%")

    print()
    print("Loading GBP/USD price data for volatility...")
    volatility = load_fx_volatility()

    print()
    print("Calculating carry score...")

    if volatility == 0:
        print("  ERROR: volatility is zero — cannot divide")
        return

    carry_score = differential / volatility

    print(f"  Carry score = {differential:.4f} / {volatility:.6f} = {carry_score:.4f}")
    print()

    # Build the output row
    result = pd.DataFrame([{
        "date":           RUN_DATE.date(),
        "pair":           "GBP_USD",
        "rate_gbp":       rate_gbp,
        "rate_usd":       rate_usd,
        "differential":   round(differential, 4),
        "volatility":     round(volatility, 6),
        "carry_score":    round(carry_score, 4),
        "signal":         "long GBP" if carry_score > 0 else "long USD",
        "source":         "fred+boe+oanda",
    }])

    result.to_parquet(dst, index=False)
    print(f"  Saved → {dst}")
    print()
    print(result.to_string(index=False))

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Gold     : {GOLD_ROOT}")
    print()

    try:
        calculate_carry()
    except Exception as e:
        print(f"  ERROR: {e}")

    print()
    print("Done — check data/gold/carry_score/ to confirm the file is there.")

if __name__ == "__main__":
    main()