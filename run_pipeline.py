"""
FX Pulse — Pipeline Runner
===========================
Runs all Bronze, Silver and Gold scripts in the correct order.
A failure in one script is logged but does not stop the rest.

Run:
    python run_pipeline.py
"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Pipeline definition — order matters
# ---------------------------------------------------------------------------

SCRIPTS = [
    # --- Bronze ---
    ("Bronze", "src/ingestion/bronze_oanda.py"),
    ("Bronze", "src/ingestion/bronze_yfinance.py"),
    ("Bronze", "src/ingestion/bronze_fred.py"),
    ("Bronze", "src/ingestion/bronze_boe.py"),
    ("Bronze", "src/ingestion/bronze_cftc.py"),

    # --- Silver ---
    ("Silver", "src/silver/silver_oanda.py"),
    ("Silver", "src/silver/silver_yfinance.py"),
    ("Silver", "src/silver/silver_fred.py"),
    ("Silver", "src/silver/silver_boe.py"),
    ("Silver", "src/silver/silver_cftc.py"),

    # --- Gold ---
    ("Gold",   "src/gold/gold_carry.py"),
    ("Gold",   "src/gold/gold_cot.py"),
    ("Gold",   "src/gold/gold_etf.py"),
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_script(layer: str, script: str) -> bool:
    """Run a single script and return True if it succeeded."""
    name = Path(script).stem
    print(f"  [{layer}] {name}...", end=" ", flush=True)

    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("✓")
        return True
    else:
        print("✗")
        # Print the last few lines of output to show what went wrong
        output = (result.stdout + result.stderr).strip().split("\n")
        for line in output[-5:]:
            print(f"    {line}")
        return False


def main():
    start = datetime.now(timezone.utc)

    print("=" * 50)
    print(f"FX Pulse Pipeline  |  {start.strftime('%Y-%m-%d %H:%M')} UTC")
    print("=" * 50)
    print()

    results = {}
    current_layer = None

    for layer, script in SCRIPTS:
        if layer != current_layer:
            print(f"--- {layer} ---")
            current_layer = layer
        success = run_script(layer, script)
        results[script] = "ok" if success else "failed"

    # Summary
    elapsed = round((datetime.now(timezone.utc) - start).total_seconds(), 1)
    passed  = sum(1 for v in results.values() if v == "ok")
    failed  = sum(1 for v in results.values() if v == "failed")

    print()
    print("=" * 50)
    print(f"Done in {elapsed}s  |  {passed} passed  |  {failed} failed")

    if failed > 0:
        print()
        print("Failed scripts:")
        for script, status in results.items():
            if status == "failed":
                print(f"  ✗  {script}")

    print("=" * 50)


if __name__ == "__main__":
    main()