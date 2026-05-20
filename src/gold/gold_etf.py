"""
FX Pulse — Gold Layer — ETF Attribution Model
==============================================
Decomposes the daily SPY return into three components:
    - Currency component  (driven by GBP/USD move)
    - Rates component     (driven by TLT move)
    - Equity residual     (pure equity sentiment)

Method:
    Simple OLS regression of SPY daily returns against
    GBP/USD daily returns and TLT daily returns.

    SPY return = β1 * GBP_USD return
               + β2 * TLT return
               + residual

    β1 = currency sensitivity
    β2 = rate sensitivity
    residual = equity component

Run:
    python src/gold/gold_etf.py

Expected output:
    data/gold/etf_attribution/2026/05/20/etf.parquet
"""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RUN_DATE    = datetime.now(timezone.utc)
SILVER_ROOT = Path(__file__).parent.parent.parent / "data" / "silver"
GOLD_ROOT   = Path(__file__).parent.parent.parent / "data" / "gold"

# Minimum days needed for a meaningful regression
MIN_DAYS = 5

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def gold_path() -> Path:
    folder = (
        GOLD_ROOT
        / "etf_attribution"
        / str(RUN_DATE.year)
        / f"{RUN_DATE.month:02d}"
        / f"{RUN_DATE.day:02d}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "etf.parquet"

def load_closes(ticker: str, source: str) -> pd.DataFrame:
    """
    Load all available daily close prices for a given ticker.
    Returns a DataFrame with date and close columns.
    """
    if source == "yfinance":
        path = SILVER_ROOT / "yfinance" / ticker
    elif source == "oanda":
        path = SILVER_ROOT / "oanda" / ticker
    else:
        raise ValueError(f"Unknown source: {source}")

    files = sorted(path.rglob("clean.parquet"))
    if not files:
        raise FileNotFoundError(f"No Silver files found for {ticker}")

    rows = []
    for f in files:
        df = pd.read_parquet(f)
        if not df.empty and "close" in df.columns:
            rows.append({
                "date":  pd.to_datetime(df["date"].iloc[0]),
                "close": float(df["close"].iloc[0]),
            })

    result = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    print(f"  {ticker}: {len(result)} days available")
    return result

def daily_returns(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Calculate daily percentage returns from close prices."""
    df = df.copy()
    df[name] = df["close"].pct_change() * 100   # as percentage
    return df[["date", name]].dropna()

# ---------------------------------------------------------------------------
# Attribution calculation
# ---------------------------------------------------------------------------

def calculate_attribution() -> None:
    dst = gold_path()

    print("Loading Silver price data...")
    spy_df     = load_closes("SPY",     "yfinance")
    tlt_df     = load_closes("TLT",     "yfinance")
    gbpusd_df  = load_closes("GBP_USD", "oanda")

    # Calculate daily returns for each
    print()
    print("Calculating daily returns...")
    spy_ret    = daily_returns(spy_df,    "spy_ret")
    tlt_ret    = daily_returns(tlt_df,    "tlt_ret")
    gbpusd_ret = daily_returns(gbpusd_df, "gbpusd_ret")

    # Merge on date — only keep days where all three have data
    merged = (
        spy_ret
        .merge(tlt_ret,    on="date", how="inner")
        .merge(gbpusd_ret, on="date", how="inner")
    )

    print(f"  Overlapping days (all 3 sources): {len(merged)}")

    # Current day's returns (most recent row)
    if merged.empty:
        print()
        print("  WARNING: no overlapping days across all 3 sources yet.")
        print("  This happens when Bronze was run on different dates per source.")
        print("  Run the full Bronze + Silver pipeline on the same day to fix this.")
        _save_empty(dst)
        return

    latest = merged.iloc[-1]
    print()
    print(f"  Most recent date : {latest['date'].date()}")
    print(f"  SPY return       : {latest['spy_ret']:.4f}%")
    print(f"  TLT return       : {latest['tlt_ret']:.4f}%")
    print(f"  GBP/USD return   : {latest['gbpusd_ret']:.4f}%")

    # Check if we have enough history for a meaningful regression
    if len(merged) < MIN_DAYS:
        print()
        print(f"  NOTE: only {len(merged)} overlapping day(s) — need {MIN_DAYS} for regression.")
        print("  Using today's returns with equal-weight attribution as a placeholder.")
        print("  Coefficients will be calculated once enough history accumulates.")
        _save_placeholder(dst, latest, len(merged))
        return

    # OLS regression — SPY returns as dependent variable
    print()
    print("Running OLS regression...")

    X = merged[["gbpusd_ret", "tlt_ret"]].values
    y = merged["spy_ret"].values

    # Add intercept
    X_with_intercept = np.column_stack([np.ones(len(X)), X])
    coeffs, residuals, _, _ = np.linalg.lstsq(X_with_intercept, y, rcond=None)

    intercept    = coeffs[0]
    beta_gbpusd  = coeffs[1]
    beta_tlt     = coeffs[2]

    print(f"  Intercept        : {intercept:.4f}")
    print(f"  β GBP/USD        : {beta_gbpusd:.4f}")
    print(f"  β TLT            : {beta_tlt:.4f}")

    # Decompose today's SPY return
    currency_component = beta_gbpusd * latest["gbpusd_ret"]
    rates_component    = beta_tlt    * latest["tlt_ret"]
    equity_residual    = latest["spy_ret"] - currency_component - rates_component

    print()
    print("Attribution for most recent day:")
    print(f"  SPY total return : {latest['spy_ret']:.4f}%")
    print(f"  Currency (GBP/USD β={beta_gbpusd:.2f}) : {currency_component:.4f}%")
    print(f"  Rates    (TLT β={beta_tlt:.2f})     : {rates_component:.4f}%")
    print(f"  Equity residual                    : {equity_residual:.4f}%")

    result = pd.DataFrame([{
        "date":               RUN_DATE.date(),
        "spy_return":         round(latest["spy_ret"],       4),
        "gbpusd_return":      round(latest["gbpusd_ret"],    4),
        "tlt_return":         round(latest["tlt_ret"],       4),
        "beta_gbpusd":        round(beta_gbpusd,             4),
        "beta_tlt":           round(beta_tlt,                4),
        "currency_component": round(currency_component,      4),
        "rates_component":    round(rates_component,         4),
        "equity_residual":    round(equity_residual,         4),
        "history_days":       len(merged),
        "confidence":         "high" if len(merged) >= 52 else "medium" if len(merged) >= 20 else "low",
        "source":             "yfinance+oanda",
    }])

    result.to_parquet(dst, index=False)
    print()
    print(f"  Saved → {dst}")
    print()
    print(result.to_string(index=False))


def _save_placeholder(dst: Path, latest: pd.Series, days: int) -> None:
    """Save a placeholder row when there isn't enough history for regression."""
    total = latest["spy_ret"]
    result = pd.DataFrame([{
        "date":               RUN_DATE.date(),
        "spy_return":         round(total, 4),
        "gbpusd_return":      round(latest["gbpusd_ret"], 4),
        "tlt_return":         round(latest["tlt_ret"],    4),
        "beta_gbpusd":        None,
        "beta_tlt":           None,
        "currency_component": None,
        "rates_component":    None,
        "equity_residual":    None,
        "history_days":       days,
        "confidence":         "low",
        "source":             "yfinance+oanda",
    }])
    result.to_parquet(dst, index=False)
    print(f"  Saved placeholder → {dst}")
    print()
    print(result.to_string(index=False))


def _save_empty(dst: Path) -> None:
    """Save an empty row when no overlapping data exists yet."""
    result = pd.DataFrame([{
        "date":               RUN_DATE.date(),
        "spy_return":         None,
        "gbpusd_return":      None,
        "tlt_return":         None,
        "beta_gbpusd":        None,
        "beta_tlt":           None,
        "currency_component": None,
        "rates_component":    None,
        "equity_residual":    None,
        "history_days":       0,
        "confidence":         "low",
        "source":             "yfinance+oanda",
    }])
    result.to_parquet(dst, index=False)
    print(f"  Saved empty placeholder → {dst}")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print(f"Run date : {RUN_DATE.strftime('%Y-%m-%d')}")
    print(f"Gold     : {GOLD_ROOT}")
    print()

    try:
        calculate_attribution()
    except Exception as e:
        print(f"  ERROR: {e}")

    print()
    print("Done — check data/gold/etf_attribution/ to confirm the file is there.")

if __name__ == "__main__":
    main()