#!/usr/bin/env python3
"""
Dividend History Manager
- Imports historical dividends from yfinance
- Calculates real payment frequency from actual data
- Computes TTM yield (trailing 12 months)
- Estimates future dividends with is_estimated flag
"""

import yfinance as yf
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "dividend_seeker.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def import_dividend_history(ticker: str, years: int = 3) -> dict:
    """
    Import dividend history from yfinance and calculate real metrics.
    Returns: {
        'payments_imported': int,
        'frequency': str,
        'payments_per_year': float,
        'ttm_amount': float,
        'last_payment': float,
        'next_estimate': float
    }
    """
    try:
        stock = yf.Ticker(ticker)
        dividends = stock.dividends
        
        if dividends.empty:
            return {'error': 'No dividend history found'}
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get currency from stock info
        info = stock.info
        currency = info.get('currency', 'USD')
        
        # Import all historical dividends
        imported = 0
        for date, amount in dividends.items():
            ex_date = date.strftime('%Y-%m-%d')
            
            cursor.execute("""
                INSERT INTO dividends (ticker, ex_date, amount, currency, is_estimated, status)
                VALUES (?, ?, ?, ?, 0, 'paid')
                ON CONFLICT(ticker, ex_date) DO UPDATE SET
                    amount = excluded.amount,
                    is_estimated = 0,
                    status = 'paid'
            """, (ticker, ex_date, float(amount), currency))
            imported += 1
        
        # Calculate real frequency from last 18 months
        cutoff = datetime.now() - timedelta(days=548)
        recent_divs = dividends[dividends.index >= cutoff.strftime('%Y-%m-%d')]
        
        if len(recent_divs) >= 2:
            # Count payments per year based on actual data
            first_date = recent_divs.index[0].to_pydatetime()
            last_date = recent_divs.index[-1].to_pydatetime()
            days_span = (last_date - first_date).days
            
            if days_span > 0:
                payments_per_year = len(recent_divs) / (days_span / 365)
            else:
                payments_per_year = 1
            
            # Determine frequency label
            if payments_per_year >= 10:
                frequency = 'monthly'
            elif payments_per_year >= 3.5:
                frequency = 'quarterly'
            elif payments_per_year >= 2.5:
                frequency = 'three_per_year'
            elif payments_per_year >= 1.5:
                frequency = 'semiannual'
            else:
                frequency = 'annual'
        else:
            frequency = 'annual'
            payments_per_year = 1
        
        # Calculate TTM (trailing 12 months)
        ttm_cutoff = datetime.now() - timedelta(days=365)
        ttm_divs = dividends[dividends.index >= ttm_cutoff.strftime('%Y-%m-%d')]
        ttm_amount = float(ttm_divs.sum()) if len(ttm_divs) > 0 else 0
        
        # Last payment amount
        last_payment = float(dividends.iloc[-1]) if len(dividends) > 0 else 0
        
        # Estimate next payment (use average of last 3 payments)
        last_3 = dividends.tail(3)
        next_estimate = float(last_3.mean()) if len(last_3) > 0 else last_payment
        
        # Update frequency for all dividends of this ticker
        cursor.execute("""
            UPDATE dividends 
            SET payment_frequency = ?
            WHERE ticker = ?
        """, (frequency, ticker))
        
        conn.commit()
        conn.close()
        
        return {
            'payments_imported': imported,
            'frequency': frequency,
            'payments_per_year': round(payments_per_year, 1),
            'ttm_amount': round(ttm_amount, 4),
            'last_payment': round(last_payment, 4),
            'next_estimate': round(next_estimate, 4)
        }
        
    except Exception as e:
        return {'error': str(e)}


def estimate_next_dividend(ticker: str) -> dict:
    """
    Estimate next dividend based on historical pattern.
    Creates a future dividend record with is_estimated=1.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get last 4 dividends
    cursor.execute("""
        SELECT ex_date, amount, payment_frequency
        FROM dividends 
        WHERE ticker = ? AND is_estimated = 0
        ORDER BY ex_date DESC
        LIMIT 4
    """, (ticker,))
    
    rows = cursor.fetchall()
    if not rows:
        conn.close()
        return {'error': 'No historical dividends'}
    
    last_date = datetime.strptime(rows[0]['ex_date'], '%Y-%m-%d')
    last_amount = rows[0]['amount']
    frequency = rows[0]['payment_frequency']
    
    # Calculate average gap between payments
    if len(rows) >= 2:
        dates = [datetime.strptime(r['ex_date'], '%Y-%m-%d') for r in rows]
        gaps = [(dates[i] - dates[i+1]).days for i in range(len(dates)-1)]
        avg_gap = sum(gaps) / len(gaps)
    else:
        # Default gaps by frequency
        gap_map = {
            'monthly': 30,
            'quarterly': 91,
            'three_per_year': 122,
            'semiannual': 182,
            'annual': 365
        }
        avg_gap = gap_map.get(frequency, 91)
    
    # Estimate next ex_date
    next_date = last_date + timedelta(days=int(avg_gap))
    
    # If estimated date is in the past, project forward
    today = datetime.now()
    while next_date < today:
        next_date += timedelta(days=int(avg_gap))
    
    # Average of last payments for amount estimate
    amounts = [r['amount'] for r in rows]
    estimated_amount = sum(amounts) / len(amounts)
    
    # Get currency
    cursor.execute("SELECT currency FROM dividends WHERE ticker = ? LIMIT 1", (ticker,))
    curr_row = cursor.fetchone()
    currency = curr_row['currency'] if curr_row else 'USD'
    
    # Insert estimated dividend
    cursor.execute("""
        INSERT INTO dividends (ticker, ex_date, amount, currency, is_estimated, status, payment_frequency)
        VALUES (?, ?, ?, ?, 1, 'estimated', ?)
        ON CONFLICT(ticker, ex_date) DO UPDATE SET
            amount = excluded.amount,
            is_estimated = 1,
            status = 'estimated'
    """, (ticker, next_date.strftime('%Y-%m-%d'), estimated_amount, currency, frequency))
    
    conn.commit()
    conn.close()
    
    return {
        'ticker': ticker,
        'next_ex_date': next_date.strftime('%Y-%m-%d'),
        'estimated_amount': round(estimated_amount, 4),
        'frequency': frequency,
        'is_estimated': True
    }


def calculate_ttm_yield(ticker: str) -> dict:
    """Calculate real TTM yield from historical dividends."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get TTM dividends (last 365 days)
    cursor.execute("""
        SELECT SUM(amount) as ttm_amount
        FROM dividends 
        WHERE ticker = ? 
          AND ex_date >= date('now', '-365 days')
          AND is_estimated = 0
    """, (ticker,))
    
    ttm_row = cursor.fetchone()
    ttm_amount = ttm_row['ttm_amount'] or 0
    
    # Get current price
    cursor.execute("""
        SELECT price FROM snapshots 
        WHERE ticker = ? 
        ORDER BY scan_date DESC LIMIT 1
    """, (ticker,))
    
    price_row = cursor.fetchone()
    price = price_row['price'] if price_row else 0
    
    conn.close()
    
    if price > 0:
        ttm_yield = (ttm_amount / price) * 100
    else:
        ttm_yield = 0
    
    return {
        'ticker': ticker,
        'ttm_amount': round(ttm_amount, 4),
        'price': price,
        'ttm_yield': round(ttm_yield, 2)
    }


def update_all_histories():
    """Import history for all tracked stocks."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT ticker FROM stocks")
    tickers = [row['ticker'] for row in cursor.fetchall()]
    conn.close()
    
    print(f"📊 Importing dividend history for {len(tickers)} stocks...")
    
    results = []
    for i, ticker in enumerate(tickers):
        result = import_dividend_history(ticker)
        if 'error' not in result:
            print(f"  ✅ {ticker}: {result['frequency']} ({result['payments_per_year']}/yr), TTM: ${result['ttm_amount']:.2f}")
            results.append((ticker, result))
        else:
            print(f"  ⚠️ {ticker}: {result['error']}")
        
        # Progress indicator
        if (i + 1) % 20 == 0:
            print(f"  ... {i+1}/{len(tickers)} processed")
    
    print(f"\n✅ Imported history for {len(results)} stocks")
    return results


def show_ttm_comparison():
    """Show TTM yield vs reported yield for verification."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            s.ticker,
            snap.dividend_yield as reported_yield,
            snap.price,
            (
                SELECT SUM(d.amount) 
                FROM dividends d 
                WHERE d.ticker = s.ticker 
                  AND d.ex_date >= date('now', '-365 days')
                  AND d.is_estimated = 0
            ) as ttm_amount
        FROM stocks s
        JOIN snapshots snap ON s.ticker = snap.ticker
            AND snap.scan_date = (SELECT MAX(scan_date) FROM snapshots WHERE ticker = s.ticker)
        WHERE snap.dividend_yield > 5
        ORDER BY snap.dividend_yield DESC
        LIMIT 20
    """)
    
    print(f"\n{'Ticker':<10} {'Reported':<10} {'TTM Yield':<10} {'Diff':<8}")
    print("-" * 40)
    
    for row in cursor.fetchall():
        reported = row['reported_yield'] or 0
        ttm_amount = row['ttm_amount'] or 0
        price = row['price'] or 1
        ttm_yield = (ttm_amount / price) * 100 if price > 0 else 0
        diff = reported - ttm_yield
        
        flag = "⚠️" if abs(diff) > 1.5 else ""
        print(f"{row['ticker']:<10} {reported:<10.2f} {ttm_yield:<10.2f} {diff:+.2f} {flag}")
    
    conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--all":
            update_all_histories()
            print("\n" + "="*50)
            show_ttm_comparison()
        elif arg == "--compare":
            show_ttm_comparison()
        else:
            ticker = arg.upper()
            print(f"\n📊 Importing history for {ticker}...")
            result = import_dividend_history(ticker)
            
            if 'error' in result:
                print(f"❌ Error: {result['error']}")
            else:
                print(f"✅ Imported {result['payments_imported']} dividends")
                print(f"   Frequency: {result['frequency']} ({result['payments_per_year']}/year)")
                print(f"   TTM Amount: ${result['ttm_amount']:.2f}")
                print(f"   Last Payment: ${result['last_payment']:.4f}")
                print(f"   Next Estimate: ${result['next_estimate']:.4f}")
                
                # Calculate and show TTM yield
                ttm = calculate_ttm_yield(ticker)
                print(f"\n   TTM Yield: {ttm['ttm_yield']:.2f}% (${ttm['ttm_amount']:.2f} / ${ttm['price']:.2f})")
                
                # Estimate next dividend
                if len(sys.argv) > 2 and sys.argv[2] == "--estimate":
                    est = estimate_next_dividend(ticker)
                    print(f"\n   📅 Next estimated: {est['next_ex_date']} (${est['estimated_amount']:.4f})")
    else:
        print("Usage:")
        print("  python dividend_history.py TICKER          - Import history for one stock")
        print("  python dividend_history.py TICKER --estimate - Also estimate next dividend")
        print("  python dividend_history.py --all           - Import all tracked stocks")
        print("  python dividend_history.py --compare       - Compare TTM vs reported yields")
