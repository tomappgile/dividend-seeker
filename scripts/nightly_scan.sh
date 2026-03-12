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
MARKETS="sp500 eurostoxx50 dax40 cac40 ftse_mib ibex35 nikkei225"

for market in $MARKETS; do
    echo ""
    echo "📊 Scanning $market..."
    python scripts/scan_dividends.py "$market" || echo "⚠️ Error scanning $market"
done

# Sync results to SQLite database
echo ""
echo "💾 Syncing to database..."
python scripts/sync_db.py

# Update dividend frequencies and per-payment amounts
echo ""
echo "📅 Updating dividend frequencies..."
python scripts/dividend_frequency.py

# Import dividend history and calculate TTM yields
echo ""
echo "📜 Importing dividend history..."
python scripts/dividend_history.py --all

# Update analyst consensus and sentiment
echo ""
echo "📈 Updating analyst consensus..."
python scripts/consensus_tracker.py --all

# Verify dividends coming up in next 30 days
echo ""
echo "🔍 Verifying upcoming dividends..."
python scripts/dividend_verifier.py --verify 30

# Export to MAIN_LIST.json for web dashboard
echo ""
echo "📤 Exporting to MAIN_LIST.json..."
python scripts/export_main_list.py

# Smart analysis - only new/changes/urgent
echo ""
echo "🧠 Running smart analysis..."
python scripts/smart_scan.py

# Check if there's a message to send
MSG_FILE="$PROJECT_DIR/data/candidates/telegram_message.txt"
if [ -f "$MSG_FILE" ] && [ -s "$MSG_FILE" ]; then
    echo ""
    echo "📨 Sending message to Telegram group Dividend Hunters..."
    
    # Read message and escape for JSON
    MSG_CONTENT=$(cat "$MSG_FILE" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')
    
    # Send to Telegram using direct API (openclaw message send has issues)
    BOT_TOKEN="8702609816:AAHNH48jCefCcxrRAvFqIwkMoLJjwG-re8I"
    CHAT_ID="-5000716003"
    
    RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
      -H "Content-Type: application/json" \
      -d "{\"chat_id\": ${CHAT_ID}, \"text\": ${MSG_CONTENT}, \"parse_mode\": \"HTML\"}")
    
    if echo "$RESPONSE" | grep -q '"ok":true'; then
        echo "✅ Message sent successfully to Dividend Hunters!"
        echo "SMART_ALERT_SENT"
    else
        echo "❌ Failed to send message:"
        echo "$RESPONSE"
        echo "SMART_ALERT_FAILED"
    fi
else
    echo ""
    echo "📭 No new alerts to send"
    echo "NO_NEW_ALERTS"
fi

echo ""
echo "✅ Nightly scan complete at $(date)"
