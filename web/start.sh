#!/bin/bash
# Start Dividend Seeker Web Dashboard

cd "$(dirname "$0")/.."
source venv/bin/activate

echo "🚀 Starting Dividend Seeker Dashboard..."
echo "   Open http://localhost:5000 in your browser"
echo ""

python web/app.py
