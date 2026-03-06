#!/usr/bin/env python3
"""
Export latest snapshot data to MAIN_LIST.json for web dashboard
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DB_PATH = PROJECT_DIR / "data" / "dividend_seeker.db"
OUTPUT_PATH = PROJECT_DIR / "data" / "candidates" / "MAIN_LIST.json"


def export_main_list():
    """Export latest data from DB to MAIN_LIST.json"""
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Get latest scan date
    cursor = conn.execute("SELECT MAX(scan_date) FROM snapshots")
    latest_date = cursor.fetchone()[0]
    
    if not latest_date:
        print("❌ No snapshots found in database")
        return
    
    # Get all stocks with latest snapshot data (yield > 5%)
    query = """
    SELECT 
        s.ticker,
        st.name,
        st.sector,
        st.industry,
        st.currency,
        s.price,
        s.dividend_yield,
        s.dividend_rate,
        s.payout_ratio,
        s.pe_ratio,
        s.market_cap,
        s.week_52_high as "52w_high",
        s.week_52_low as "52w_low",
        s.dividend_score,
        s.capital_score,
        s.sustainable,
        st.ocean_accessible,
        st.market as ocean_market
    FROM snapshots s
    JOIN stocks st ON s.ticker = st.ticker
    WHERE s.scan_date = ?
    AND s.dividend_yield >= 5.0
    ORDER BY s.dividend_yield DESC
    """
    
    cursor = conn.execute(query, (latest_date,))
    rows = cursor.fetchall()
    
    stocks = []
    for row in rows:
        stock = {
            "ticker": row["ticker"],
            "name": row["name"],
            "sector": row["sector"],
            "industry": row["industry"],
            "currency": row["currency"],
            "price": row["price"],
            "dividend_yield": round(row["dividend_yield"], 2) if row["dividend_yield"] else None,
            "dividend_rate": row["dividend_rate"],
            "payout_ratio": round(row["payout_ratio"], 2) if row["payout_ratio"] else None,
            "pe_ratio": round(row["pe_ratio"], 2) if row["pe_ratio"] else None,
            "market_cap": row["market_cap"],
            "52w_high": row["52w_high"],
            "52w_low": row["52w_low"],
            "dividend_score": row["dividend_score"],
            "capital_score": row["capital_score"],
            "sustainable": bool(row["sustainable"]),
            "ocean_accessible": bool(row["ocean_accessible"]),
            "ocean_market": row["ocean_market"]
        }
        stocks.append(stock)
    
    conn.close()
    
    # Create output
    output = {
        "scan_date": latest_date,
        "exported_at": datetime.now().isoformat(),
        "total": len(stocks),
        "stocks": stocks
    }
    
    # Write to file
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ Exported {len(stocks)} stocks to MAIN_LIST.json")
    print(f"   📅 Scan date: {latest_date}")
    print(f"   📦 Exported at: {output['exported_at']}")


if __name__ == "__main__":
    export_main_list()
