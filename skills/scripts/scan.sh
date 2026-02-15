#!/bin/bash
# Dividend Scanner Wrapper
# Usage: ./scan.sh [market1] [market2] ...
# Example: ./scan.sh sp500 ibex35

PROJECT_DIR="/Users/tomix/.openclaw/workspace-dividend-seeker/dividend-seeker"

cd "$PROJECT_DIR" || exit 1
source venv/bin/activate

if [ $# -eq 0 ]; then
    # No arguments - scan all markets
    ./scripts/nightly_scan.sh
else
    # Scan specific markets
    for market in "$@"; do
        echo "📊 Scanning $market..."
        python scripts/scan_dividends.py "$market"
    done
fi
