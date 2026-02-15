#!/bin/bash
# Nightly Dividend Scanner
# Runs at 3:00 AM Europe/Madrid

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
source venv/bin/activate

echo "🌙 Starting nightly dividend scan at $(date)"
echo "================================================"

# Scan all markets
MARKETS="sp500 eurostoxx50 dax40 cac40 ftse_mib ibex35"

for market in $MARKETS; do
    echo ""
    echo "📊 Scanning $market..."
    python scripts/scan_dividends.py "$market" || echo "⚠️ Error scanning $market"
done

# Sync results to SQLite database
echo ""
echo "💾 Syncing to database..."
python scripts/sync_db.py

echo ""
echo "✅ Nightly scan complete at $(date)"
