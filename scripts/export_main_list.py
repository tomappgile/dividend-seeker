#!/usr/bin/env python3
"""
Export latest snapshot data to MAIN_LIST.json for web dashboard

Column naming convention (Hungarian notation):
- i = INTEGER, s = TEXT, r = REAL, b = BOOLEAN, d = DATE, t = TIMESTAMP
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DB_PATH = PROJECT_DIR / "data" / "dividend_seeker.db"
OUTPUT_PATH = PROJECT_DIR / "data" / "candidates" / "MAIN_LIST.json"


def export_main_list():
    """Export latest data from DB to MAIN_LIST.json"""
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT MAX(dscan_date) FROM snapshots")
    latest_date = cursor.fetchone()[0]
    
    if not latest_date:
        print("❌ No snapshots found in database")
        return
    
    query = """
    SELECT 
        s.sticker,
        st.sname,
        st.ssector,
        st.sindustry,
        st.scurrency,
        s.rprice,
        s.rdividend_yield,
        s.rdividend_rate,
        s.rpayout_ratio,
        s.rpe_ratio,
        s.rmarket_cap,
        s.rweek_52_high,
        s.rweek_52_low,
        s.idividend_score,
        s.icapital_score,
        s.bsustainable,
        st.bocean_accessible,
        st.smarket,
        st.bbroker_caixabank,
        st.bbroker_n26
    FROM snapshots s
    JOIN stocks st ON s.sticker = st.sticker
    WHERE s.dscan_date = ?
    AND s.rdividend_yield >= 5.0
    ORDER BY s.rdividend_yield DESC
    """
    
    cursor = conn.execute(query, (latest_date,))
    rows = cursor.fetchall()
    
    stocks = []
    for row in rows:
        stock = {
            "ticker": row["sticker"],
            "name": row["sname"],
            "sector": row["ssector"],
            "industry": row["sindustry"],
            "currency": row["scurrency"],
            "price": row["rprice"],
            "dividend_yield": round(row["rdividend_yield"], 2) if row["rdividend_yield"] else None,
            "dividend_rate": row["rdividend_rate"],
            "payout_ratio": round(row["rpayout_ratio"], 2) if row["rpayout_ratio"] else None,
            "pe_ratio": round(row["rpe_ratio"], 2) if row["rpe_ratio"] else None,
            "market_cap": row["rmarket_cap"],
            "52w_high": row["rweek_52_high"],
            "52w_low": row["rweek_52_low"],
            "dividend_score": row["idividend_score"],
            "capital_score": row["icapital_score"],
            "sustainable": bool(row["bsustainable"]),
            "ocean_accessible": bool(row["bocean_accessible"]),
            "ocean_market": row["smarket"],
            "broker_caixabank": bool(row["bbroker_caixabank"]),
            "broker_n26": bool(row["bbroker_n26"])
        }
        stocks.append(stock)
    
    conn.close()
    
    output = {
        "scan_date": latest_date,
        "exported_at": datetime.now().isoformat(),
        "total": len(stocks),
        "stocks": stocks
    }
    
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"✅ Exported {len(stocks)} stocks to MAIN_LIST.json")
    print(f"   📅 Scan date: {latest_date}")
    print(f"   📦 Exported at: {output['exported_at']}")


if __name__ == "__main__":
    export_main_list()
