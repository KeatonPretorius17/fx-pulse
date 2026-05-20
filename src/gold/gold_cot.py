"""
FX Pulse — Gold Layer — COT Crossover Signal
=============================================
Combines CFTC institutional positioning with GBP/USD
price momentum to generate the COT crossover signal.

Signal logic:
    1. Calculate net positioning (long - short) from CFTC data
    2. Check if net is at a historical extreme (above 80th or below 20th percentile)
    3. Check price momentum direction (fast MA vs slow MA on GBP/USD closes)
    4. Signal fires when positioning extreme and momentum agree

Output columns:
    date                — run date
    net_position        — current leveraged fund net (long - short)
    net_percentile      — where current net sits in historical range (0-100)
    positioning_signal  — "extreme_long", "extreme_short", or "neutral"
    ma_fast             — average of last 3 available closes
    ma_slow             — average of all available closes
    momentum_signal     — "bullish", "bearish", or "neutral"
    crossover_signal    — final combined signal
    history_days        — how many days of data were used
    confidence          — "low" if <20 days history, "medium" if <52wk, "high" if 52wk+

Run:
    python src/gold/gold_cot.py

Expected output:
    data/gold/cot_signal/2026/05/20/cot.parquet
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RUN_DATE    = datetime.now(timezone.utc)
SILVER_ROOT = Path(__file__).parent.parent.parent / "data" / "silver"
GOLD_ROOT   = Path(__file__).parent.parent.parent / "data" / "gold"

# Percentile thresholds for positioning extremes
EXTREME_HIGH = 80   # above this = extreme long
EXTREME_LOW  = 20   # below this = extreme short

# Moving average windows (in trading days)
MA_FAST = 3
MA_SLOW = 10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def gold_path() -> Path:
    folder = (
        GOLD_ROOT
        / "cot_signal"
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "cot.parquet"

def load_all_parquets(path: Path, value_col: str) -> pd.DataFrame:
    """Load all parquet files under a path and return a time series."""
    files = sorted(path.rglob("clean.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found under {path}")

    rows = []
    for f in files:
        df = pd.read_parquet(f)
        if not df.empty and value_col in df.columns:
            rows.append(df[["date", value_col]].iloc[0])

    if not rows:
        raise ValueError(f"No rows found with column '{value_col}'")

    result = pd.DataFrame(rows)
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values("date").reset_index(drop=True)
    return result

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_cot_history() -> pd.DataFrame:
    """Load all available CFTC net positioning data."""
    path = SILVER_ROOT / "cftc" / "gbp_futures"
    files = sorted(path.rglob("clean.parquet"))

    rows = []
    for f in files:
        df = pd.read_parquet(f)
        if not df.empty and "net" in df.columns:
            rows.append({"date": df["date"].iloc[0], "net": float(df["net"].iloc[0])})

    if not rows:
        raise FileNotFoundError("No CFTC Silver files found")

    result = pd.DataFrame(rows)
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values("date").reset_index(drop=True)
    return result

def load_fx_history() -> pd.DataFrame:
    """Load all available GBP/USD close prices."""
    path = SILVER_ROOT / "oanda" / "GBP_USD"
    files = sorted(path.rglob("clean.parquet"))

    rows = []
    for f in files:
        df = pd.read_parquet(f)
        if not df.empty and "close" in df.columns:
            rows.append({"date": df["date"].iloc[0], "close": float(df["close"].iloc[0])})

    if not rows:
        raise FileNotFoundError("No GBP_USD Silver files found")

    result = pd.DataFrame(rows)
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values("date").reset_index(drop=True)
    return result

# ---------------------------------------------------------------------------
# Signal calculation
# ---------------------------------------------------------------------------

def positioning_signal(cot_df: pd.DataFrame) -> dict:
    """
    Calculate where current net positioning sits in historical range.
    Returns the percentile and a signal label.
    """
    current_net = float(cot_df["net"].iloc[-1])
    current_date = cot_df["date"].iloc[-1]
    history_days = len(cot_df)

    print(f"  COT history available : {history_days} weekly reports")
    print(f"  Most recent report    : {current_date.date()}")
    print(f"  Current net position  : {current_net:,.0f}")

    if history_days < 2:
        print("  WARNING: not enough COT history — positioning signal is neutral")
        return {
            "net_position":       current_net,
            "net_percentile":     50.0,
            "positioning_signal": "neutral",
            "cot_history_weeks":  history_days,
        }

    # Calculate percentile rank of current net vs all history
    percentile = float(pd.Series(cot_df["net"]).rank(pct=True).iloc[-1] * 100)
    print(f"  Net percentile        : {percentile:.1f}th")

    if percentile >= EXTREME_HIGH:
        signal = "extreme_long"
    elif percentile <= EXTREME_LOW:
        signal = "extreme_short"
    else:
        signal = "neutral"

    print(f"  Positioning signal    : {signal}")

    return {
        "net_position":       current_net,
        "net_percentile":     round(percentile, 1),
        "positioning_signal": signal,
        "cot_history_weeks":  history_days,
    }

def momentum_signal(fx_df: pd.DataFrame) -> dict:
    """
    Calculate fast vs slow moving average on GBP/USD closes.
    Returns the MA values and a momentum direction label.
    """
    history_days = len(fx_df)
    print(f"  FX price history      : {history_days} trading days")

    closes = fx_df["close"]
    current_close = float(closes.iloc[-1])

    # Use whatever history we have — be transparent about window size
    fast_window = min(MA_FAST, history_days)
    slow_window = min(MA_SLOW, history_days)

    ma_fast = float(closes.tail(fast_window).mean())
    ma_slow = float(closes.tail(slow_window).mean())

    print(f"  MA fast ({fast_window}d)           : {ma_fast:.5f}")
    print(f"  MA slow ({slow_window}d)          : {ma_slow:.5f}")

    if fast_window == slow_window:
        print("  WARNING: not enough history to separate fast/slow MA — momentum neutral")
        signal = "neutral"
    elif ma_fast > ma_slow:
        signal = "bullish"
    else:
        signal = "bearish"

    print(f"  Momentum signal       : {signal}")

    return {
        "current_close":  current_close,
        "ma_fast":        round(ma_fast, 5),
        "ma_slow":        round(ma_slow, 5),
        "momentum_signal": signal,
        "fx_history_days": history_days,
    }

def combine_signals(pos: dict, mom: dict) -> str:
    """
    Combine positioning and momentum into a final crossover signal.

    Strong signals — both agree:
        extreme_long  + bullish  → COT_LONG
        extreme_short + bearish  → COT_SHORT

    Conflicting or neutral — no signal:
        anything else            → NO_SIGNAL
    """
    p = pos["positioning_signal"]
    m = mom["momentum_signal"]

    if p == "extreme_long" and m == "bullish":
        return "COT_LONG"
    elif p == "extreme_short" and m == "bearish":
        return "COT_SHORT"
    else:
        return "NO_SIGNAL"

def confidence_level(cot_weeks: int, fx_days: int) -> str:
    if cot_weeks >= 52 and fx_days >= 52:
        return "high"
    elif cot_weeks >= 10 and fx_days >= 10:
        return "medium"
    else:
        return "low"

# ---------------------------------------------------------------------------
# Main calculation
# ---------------------------------------------------------------------------

def calculate_cot() -> None:
    dst = gold_path()

    print("Loading CFTC positioning history...")
    cot_df = load_cot_history()

    print()
    print("Loading GBP/USD price history...")
    fx_df = load_fx_history()

    print()
    print("Calculating positioning signal...")
    pos = positioning_signal(cot_df)

    print()
    print("Calculating momentum signal...")
    mom = momentum_signal(fx_df)

    print()
    print("Combining signals...")
    crossover = combine_signals(pos, mom)
    confidence = confidence_level(pos["cot_history_weeks"], mom["fx_history_days"])

    print(f"  Crossover signal      : {crossover}")
    print(f"  Confidence            : {confidence}")

    if confidence == "low":
        print()
        print("  NOTE: signal confidence is low — not enough historical data yet.")
        print("  Run the pipeline daily and confidence will improve automatically.")

    # Build output row
    result = pd.DataFrame([{
        "date":               RUN_DATE.date(),
        "pair":               "GBP_USD",
        "net_position":       pos["net_position"],
        "net_percentile":     pos["net_percentile"],
        "positioning_signal": pos["positioning_signal"],
        "ma_fast":            mom["ma_fast"],
        "ma_slow":            mom["ma_slow"],
        "momentum_signal":    mom["momentum_signal"],
        "crossover_signal":   crossover,
        "cot_history_weeks":  pos["cot_history_weeks"],
        "fx_history_days":    mom["fx_history_days"],
        "confidence":         confidence,
        "source":             "cftc+oanda",
    }])

    result.to_parquet(dst, index=False)

    print()
    print(f"  Saved → {dst}")
    print()
    print(result.to_string(index=False))

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Gold     : {GOLD_ROOT}")
    print()

    try:
        calculate_cot()
    except Exception as e:
        print(f"  ERROR: {e}")

    print()
    print("Done — check data/gold/cot_signal/ to confirm the file is there.")

if __name__ == "__main__":
    main()