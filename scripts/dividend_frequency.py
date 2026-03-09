#!/usr/bin/env python3
"""
Dividend Frequency Detector
Analyzes dividend history to determine payment frequency and next payment amount.
"""

import yfinance as yf
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "dividend_seeker.db"


def detect_frequency(ticker: str) -> dict:
    """
    Detect dividend payment frequency from history.
    Returns: {
        'frequency': 'quarterly' | 'semiannual' | 'annual' | 'monthly' | 'unknown',
        'payments_per_year': int,
        'last_amount': float,
        'annual_amount': float,
        'next_payment_estimate': float
    }
    """
    try:
        stock = yf.Ticker(ticker)
        
        # Get dividend history (last 2 years)
        dividends = stock.dividends
        if dividends.empty:
            return {'frequency': 'unknown', 'payments_per_year': 0}
        
        # Filter last 18 months to detect pattern
        cutoff = datetime.now() - timedelta(days=548)
        recent_divs = dividends[dividends.index >= cutoff.strftime('%Y-%m-%d')]
        
        if len(recent_divs) == 0:
            recent_divs = dividends.tail(4)  # Fallback to last 4 payments
        
        # Count payments per year
        if len(recent_divs) >= 2:
            # Calculate average days between payments
            dates = recent_divs.index.to_pydatetime()
            gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            avg_gap = sum(gaps) / len(gaps) if gaps else 365
            
            # Determine frequency from gap
            if avg_gap <= 45:  # ~monthly
                frequency = 'monthly'
                payments_per_year = 12
            elif avg_gap <= 105:  # ~quarterly (90 days +/- 15)
                frequency = 'quarterly'
                payments_per_year = 4
            elif avg_gap <= 200:  # ~semiannual (180 days +/- 20)
                frequency = 'semiannual'
                payments_per_year = 2
            else:  # annual
                frequency = 'annual'
                payments_per_year = 1
        else:
            frequency = 'annual'
            payments_per_year = 1
        
        # Calculate amounts
        last_amount = float(recent_divs.iloc[-1]) if len(recent_divs) > 0 else 0
        
        # Sum last year's dividends for annual amount
        one_year_ago = datetime.now() - timedelta(days=365)
        yearly_divs = dividends[dividends.index >= one_year_ago.strftime('%Y-%m-%d')]
        annual_amount = float(yearly_divs.sum()) if len(yearly_divs) > 0 else last_amount * payments_per_year
        
        # Next payment estimate = last payment amount (most accurate)
        next_payment_estimate = last_amount
        
        return {
            'frequency': frequency,
            'payments_per_year': payments_per_year,
            'last_amount': round(last_amount, 4),
            'annual_amount': round(annual_amount, 4),
            'next_payment_estimate': round(next_payment_estimate, 4)
        }
        
    except Exception as e:
        print(f"⚠️ Error detecting frequency for {ticker}: {e}")
        return {'frequency': 'unknown', 'payments_per_year': 0}


def update_dividend_frequency(ticker: str, ex_date: str = None):
    """Update dividend record with frequency info."""
    freq_data = detect_frequency(ticker)
    
    if freq_data['frequency'] == 'unknown':
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Update all records for this ticker, or specific ex_date
    if ex_date:
        cursor.execute("""
            UPDATE dividends 
            SET payment_frequency = ?, amount = ?
            WHERE ticker = ? AND ex_date = ?
        """, (freq_data['frequency'], freq_data['next_payment_estimate'], ticker, ex_date))
    else:
        # Update frequency for all, and amount for upcoming dividends
        cursor.execute("""
            UPDATE dividends 
            SET payment_frequency = ?
            WHERE ticker = ?
        """, (freq_data['frequency'], ticker))
        
        # Update amount for future dividends (force update with correct per-payment amount)
        cursor.execute("""
            UPDATE dividends 
            SET amount = ?
            WHERE ticker = ? AND ex_date >= date('now')
        """, (freq_data['next_payment_estimate'], ticker))
    
    conn.commit()
    conn.close()
    
    return freq_data


def update_all_frequencies():
    """Update frequency for all stocks with upcoming dividends."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT ticker FROM dividends 
        WHERE ex_date >= date('now')
    """)
    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"📊 Updating frequency for {len(tickers)} tickers...")
    
    results = []
    for ticker in tickers:
        freq_data = update_dividend_frequency(ticker)
        if freq_data:
            results.append((ticker, freq_data))
            print(f"  ✅ {ticker}: {freq_data['frequency']} (${freq_data['next_payment_estimate']:.2f}/pago)")
    
    print(f"\n✅ Updated {len(results)} tickers")
    return results


def show_upcoming_with_frequency():
    """Show upcoming dividends with correct per-payment yields."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            d.ticker,
            s.name,
            d.ex_date,
            d.amount as next_payment,
            d.payment_frequency,
            snap.price,
            snap.dividend_yield as yield_annual,
            CASE 
                WHEN snap.price > 0 AND d.amount > 0 
                THEN ROUND(d.amount / snap.price * 100, 2)
                ELSE NULL 
            END as yield_payment
        FROM dividends d
        JOIN stocks s ON d.ticker = s.ticker
        LEFT JOIN snapshots snap ON d.ticker = snap.ticker
            AND snap.scan_date = (SELECT MAX(scan_date) FROM snapshots WHERE ticker = d.ticker)
        WHERE d.ex_date >= date('now')
        ORDER BY d.ex_date
        LIMIT 20
    """)
    
    print(f"\n{'Ticker':<8} {'Ex-Date':<12} {'Freq':<10} {'Pago':<8} {'Yield Pago':<12} {'Yield Anual':<12}")
    print("-" * 70)
    
    for row in cursor.fetchall():
        freq = row['payment_frequency'] or 'annual'
        pago = f"${row['next_payment']:.2f}" if row['next_payment'] else "?"
        yield_p = f"{row['yield_payment']:.2f}%" if row['yield_payment'] else "?"
        yield_a = f"{row['yield_annual']:.2f}%" if row['yield_annual'] else "?"
        print(f"{row['ticker']:<8} {row['ex_date']:<12} {freq:<10} {pago:<8} {yield_p:<12} {yield_a:<12}")
    
    conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        ticker = sys.argv[1].upper()
        result = detect_frequency(ticker)
        print(f"\n📊 {ticker} Dividend Frequency Analysis:")
        print(f"   Frequency: {result['frequency']}")
        print(f"   Payments/year: {result['payments_per_year']}")
        print(f"   Last payment: ${result.get('last_amount', 0):.4f}")
        print(f"   Annual total: ${result.get('annual_amount', 0):.4f}")
        print(f"   Next payment est: ${result.get('next_payment_estimate', 0):.4f}")
        
        if len(sys.argv) > 2 and sys.argv[2] == "--update":
            update_dividend_frequency(ticker)
            print(f"\n✅ Database updated for {ticker}")
    else:
        update_all_frequencies()
        print("\n" + "="*70)
        show_upcoming_with_frequency()
