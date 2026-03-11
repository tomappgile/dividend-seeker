#!/usr/bin/env python3
"""
Sync scan results (JSON) to SQLite database.
Can be run after scan or as part of nightly_scan.sh

Column naming convention (Hungarian notation):
- i = INTEGER, s = TEXT, r = REAL, b = BOOLEAN, d = DATE, t = TIMESTAMP
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "dividend_seeker.db"
MAIN_LIST = DATA_DIR / "candidates" / "MAIN_LIST.json"


def get_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sync_stock(conn, stock: dict, market: str = None):
    """Upsert a stock record."""
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO stocks (sticker, sname, ssector, sindustry, scurrency, smarket, bocean_accessible, tupdated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(sticker) DO UPDATE SET
            sname = excluded.sname,
            ssector = excluded.ssector,
            sindustry = excluded.sindustry,
            scurrency = excluded.scurrency,
            smarket = COALESCE(excluded.smarket, stocks.smarket),
            bocean_accessible = excluded.bocean_accessible,
            tupdated_at = CURRENT_TIMESTAMP
    """, (
        stock['ticker'],
        stock.get('name'),
        stock.get('sector'),
        stock.get('industry'),
        stock.get('currency'),
        market or stock.get('ocean_market'),
        stock.get('ocean_accessible', False)
    ))


def sync_snapshot(conn, stock: dict, scan_date: str):
    """Insert snapshot for today (or update if exists)."""
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO snapshots (
            sticker, dscan_date, rprice, rdividend_yield, rdividend_rate,
            rpayout_ratio, rpe_ratio, rmarket_cap, rweek_52_high, rweek_52_low,
            rchange_6m, rchange_12m, rdist_from_high, rmax_drawdown_12m,
            rbeta, idividend_score, icapital_score, bsustainable,
            rprice_target_avg, rprice_target_high, rprice_target_low,
            rupside_potential, sanalyst_rating, ianalyst_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sticker, dscan_date) DO UPDATE SET
            rprice = excluded.rprice,
            rdividend_yield = excluded.rdividend_yield,
            rdividend_rate = excluded.rdividend_rate,
            rpayout_ratio = excluded.rpayout_ratio,
            rpe_ratio = excluded.rpe_ratio,
            rmarket_cap = excluded.rmarket_cap,
            rweek_52_high = excluded.rweek_52_high,
            rweek_52_low = excluded.rweek_52_low,
            rchange_6m = excluded.rchange_6m,
            rchange_12m = excluded.rchange_12m,
            rdist_from_high = excluded.rdist_from_high,
            rmax_drawdown_12m = excluded.rmax_drawdown_12m,
            rbeta = excluded.rbeta,
            idividend_score = excluded.idividend_score,
            icapital_score = excluded.icapital_score,
            bsustainable = excluded.bsustainable,
            rprice_target_avg = excluded.rprice_target_avg,
            rprice_target_high = excluded.rprice_target_high,
            rprice_target_low = excluded.rprice_target_low,
            rupside_potential = excluded.rupside_potential,
            sanalyst_rating = excluded.sanalyst_rating,
            ianalyst_count = excluded.ianalyst_count
    """, (
        stock['ticker'],
        scan_date,
        stock.get('price'),
        stock.get('dividend_yield') or stock.get('yield'),
        stock.get('dividend_rate') or stock.get('div_rate'),
        stock.get('payout_ratio') or stock.get('payout'),
        stock.get('pe_ratio'),
        stock.get('market_cap'),
        stock.get('52w_high'),
        stock.get('52w_low'),
        stock.get('change_6m'),
        stock.get('change_12m'),
        stock.get('dist_from_high') or stock.get('discount_from_high'),
        stock.get('max_drawdown_12m'),
        stock.get('beta'),
        stock.get('dividend_score'),
        stock.get('capital_score'),
        stock.get('sustainable', True),
        stock.get('price_target_avg'),
        stock.get('price_target_high'),
        stock.get('price_target_low'),
        stock.get('upside_potential'),
        stock.get('analyst_rating'),
        stock.get('analyst_count')
    ))


def sync_dividend(conn, stock: dict):
    """Upsert dividend record if ex_dividend_date exists."""
    ex_date = stock.get('ex_dividend_date')
    if not ex_date:
        return
    
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dividends (sticker, dex_date, ramount, scurrency)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(sticker, dex_date) DO UPDATE SET
            ramount = COALESCE(excluded.ramount, dividends.ramount),
            scurrency = COALESCE(excluded.scurrency, dividends.scurrency)
    """, (
        stock['ticker'],
        ex_date,
        stock.get('dividend_rate'),
        stock.get('currency')
    ))


def log_scan(conn, scan_date: str, total: int, source: str):
    """Log the scan run."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO scans (dscan_date, itotal_scanned, icandidates_found, smarkets_scanned)
        VALUES (?, ?, ?, ?)
    """, (scan_date, total, total, source))


def sync_from_json(json_path: Path = MAIN_LIST):
    """Sync database from JSON scan results."""
    top_picks = DATA_DIR / "candidates" / "top_picks.json"
    if top_picks.exists():
        json_path = top_picks
    elif not json_path.exists():
        print(f"❌ JSON file not found: {json_path}")
        return False
    
    with open(json_path) as f:
        data = json.load(f)
    
    scan_date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_connection()
    
    total = 0
    tiers = ['tier1_high_sustainable', 'tier2_moderate_sustainable', 'tier3_high_risk']
    
    if 'top_20' in data:
        stocks = data['top_20']
    elif 'candidates' in data:
        stocks = data['candidates']
    else:
        stocks = []
        for tier in tiers:
            stocks.extend(data.get(tier, []))
    
    print(f"📊 Syncing {len(stocks)} stocks to database...")
    
    for stock in stocks:
        try:
            sync_stock(conn, stock)
            sync_snapshot(conn, stock, scan_date)
            sync_dividend(conn, stock)
            total += 1
        except Exception as e:
            print(f"  ⚠️  {stock.get('ticker')}: {e}")
    
    try:
        log_scan(conn, scan_date, total, str(json_path.name))
    except:
        pass
    
    conn.commit()
    conn.close()
    
    print(f"✅ Synced {total} stocks to {DB_PATH.name}")
    print(f"   📅 Scan date: {scan_date}")
    
    return True


def show_stats():
    """Show database statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM stocks")
    stocks = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM snapshots")
    snapshots = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT dscan_date) FROM snapshots")
    scan_days = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM dividends WHERE dex_date >= date('now')")
    upcoming_divs = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT sticker, rdividend_yield, idividend_score, icapital_score 
        FROM snapshots 
        WHERE dscan_date = (SELECT MAX(dscan_date) FROM snapshots)
        ORDER BY rdividend_yield DESC
        LIMIT 5
    """)
    top5 = cursor.fetchall()
    
    conn.close()
    
    print(f"\n📈 DATABASE STATS")
    print(f"   Stocks: {stocks}")
    print(f"   Snapshots: {snapshots} ({scan_days} scan days)")
    print(f"   Upcoming dividends: {upcoming_divs}")
    print(f"\n🏆 Top 5 by yield:")
    for row in top5:
        div_s = f"D:{'⭐'*row['idividend_score']}" if row['idividend_score'] else ""
        cap_s = f"C:{'⭐'*row['icapital_score']}" if row['icapital_score'] else ""
        print(f"   {row['sticker']:<10} {row['rdividend_yield']:.1f}% {div_s} {cap_s}")


def sync_from_daily_files(date_str: str = None):
    """Sync from all daily market scan files."""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    dividends_dir = DATA_DIR / "dividends"
    pattern = f"{date_str}_*.json"
    
    files = list(dividends_dir.glob(pattern))
    if not files:
        print(f"❌ No scan files found for {date_str}")
        return False
    
    print(f"📊 Found {len(files)} scan files for {date_str}")
    
    conn = get_connection()
    total = 0
    seen_tickers = set()
    
    for file_path in files:
        market = file_path.stem.replace(f"{date_str}_", "")
        with open(file_path) as f:
            data = json.load(f)
        
        stocks = data.get('candidates', [])
        for stock in stocks:
            ticker = stock['ticker']
            if ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)
            
            try:
                sync_stock(conn, stock, market)
                sync_snapshot(conn, stock, date_str)
                sync_dividend(conn, stock)
                total += 1
            except Exception as e:
                print(f"  ⚠️  {ticker}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Synced {total} stocks from daily files to {DB_PATH.name}")
    print(f"   📅 Scan date: {date_str}")
    
    return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        show_stats()
    elif len(sys.argv) > 1 and sys.argv[1] == "--daily":
        date_arg = sys.argv[2] if len(sys.argv) > 2 else None
        sync_from_daily_files(date_arg)
        show_stats()
    else:
        sync_from_daily_files()
        show_stats()
