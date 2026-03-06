#!/usr/bin/env python3
"""
Sync scan results (JSON) to SQLite database.
Can be run after scan or as part of nightly_scan.sh
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
        INSERT INTO stocks (ticker, name, sector, industry, currency, market, ocean_accessible, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(ticker) DO UPDATE SET
            name = excluded.name,
            sector = excluded.sector,
            industry = excluded.industry,
            currency = excluded.currency,
            market = COALESCE(excluded.market, stocks.market),
            ocean_accessible = excluded.ocean_accessible,
            updated_at = CURRENT_TIMESTAMP
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
            ticker, scan_date, price, dividend_yield, dividend_rate,
            payout_ratio, pe_ratio, market_cap, week_52_high, week_52_low,
            change_6m, change_12m, dist_from_high, max_drawdown_12m,
            beta, dividend_score, capital_score, sustainable,
            price_target_avg, price_target_high, price_target_low,
            upside_potential, analyst_rating, analyst_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, scan_date) DO UPDATE SET
            price = excluded.price,
            dividend_yield = excluded.dividend_yield,
            dividend_rate = excluded.dividend_rate,
            payout_ratio = excluded.payout_ratio,
            pe_ratio = excluded.pe_ratio,
            market_cap = excluded.market_cap,
            week_52_high = excluded.week_52_high,
            week_52_low = excluded.week_52_low,
            change_6m = excluded.change_6m,
            change_12m = excluded.change_12m,
            dist_from_high = excluded.dist_from_high,
            max_drawdown_12m = excluded.max_drawdown_12m,
            beta = excluded.beta,
            dividend_score = excluded.dividend_score,
            capital_score = excluded.capital_score,
            sustainable = excluded.sustainable,
            price_target_avg = excluded.price_target_avg,
            price_target_high = excluded.price_target_high,
            price_target_low = excluded.price_target_low,
            upside_potential = excluded.upside_potential,
            analyst_rating = excluded.analyst_rating,
            analyst_count = excluded.analyst_count
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
        INSERT INTO dividends (ticker, ex_date, amount, currency)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ticker, ex_date) DO UPDATE SET
            amount = COALESCE(excluded.amount, dividends.amount),
            currency = COALESCE(excluded.currency, dividends.currency)
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
        INSERT INTO scans (scan_date, total_scanned, candidates_found, source)
        VALUES (?, ?, ?, ?)
    """, (scan_date, total, total, source))


def sync_from_json(json_path: Path = MAIN_LIST):
    """Sync database from JSON scan results."""
    # Try top_picks.json first (most recent), then MAIN_LIST
    top_picks = DATA_DIR / "candidates" / "top_picks.json"
    if top_picks.exists():
        json_path = top_picks
    elif not json_path.exists():
        print(f"❌ JSON file not found: {json_path}")
        return False
    
    with open(json_path) as f:
        data = json.load(f)
    
    # Use today's date for the snapshot
    scan_date = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_connection()
    
    total = 0
    tiers = ['tier1_high_sustainable', 'tier2_moderate_sustainable', 'tier3_high_risk']
    
    # Handle different JSON formats
    if 'top_20' in data:
        # top_picks.json format
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
        pass  # scans table might not have all columns
    
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
    
    cursor.execute("SELECT COUNT(DISTINCT scan_date) FROM snapshots")
    scan_days = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM dividends WHERE ex_date >= date('now')")
    upcoming_divs = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT ticker, dividend_yield, dividend_score, capital_score 
        FROM snapshots 
        WHERE scan_date = (SELECT MAX(scan_date) FROM snapshots)
        ORDER BY dividend_yield DESC
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
        div_s = f"D:{'⭐'*row['dividend_score']}" if row['dividend_score'] else ""
        cap_s = f"C:{'⭐'*row['capital_score']}" if row['capital_score'] else ""
        print(f"   {row['ticker']:<10} {row['dividend_yield']:.1f}% {div_s} {cap_s}")


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
        # Default: sync from daily files first, then top_picks
        sync_from_daily_files()
        show_stats()
