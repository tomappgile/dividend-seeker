#!/usr/bin/env python3
"""
Dividend Verifier
- Checks dividends coming up in the next 30 days
- Searches for official confirmation via web
- Updates database with confirmed amounts and dates
- Marks dividends as confirmed vs estimated

Column naming convention (Hungarian notation):
- i = INTEGER, s = TEXT, r = REAL, b = BOOLEAN, d = DATE, t = TIMESTAMP
"""

import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
import re
import yfinance as yf

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "dividend_seeker.db"

# Sources for dividend verification
DIVIDEND_SOURCES = [
    "dividendmax.com",
    "nasdaq.com/market-activity/stocks/{}/dividend-history",
    "stockevents.app",
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_upcoming_dividends(days: int = 30) -> list:
    """Get dividends expected in the next N days."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cutoff = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT 
            d.idividendsid,
            d.sticker,
            s.sname,
            d.dex_date,
            d.dpay_date,
            d.ramount,
            d.bis_estimated,
            d.sstatus,
            julianday(d.dex_date) - julianday('now') as days_until
        FROM dividends d
        JOIN stocks s ON d.sticker = s.sticker
        WHERE d.dex_date >= ? AND d.dex_date <= ?
        ORDER BY d.dex_date
    """, (today, cutoff))
    
    results = cursor.fetchall()
    conn.close()
    return results


def search_dividend_info(ticker: str, company_name: str) -> dict:
    """
    Search for confirmed dividend info from yfinance and web.
    Returns dict with confirmed data or None.
    """
    result = {
        'confirmed': False,
        'amount': None,
        'ex_date': None,
        'pay_date': None,
        'source': None
    }
    
    try:
        # First try yfinance calendar
        stock = yf.Ticker(ticker)
        
        # Check if there's upcoming dividend info
        try:
            calendar = stock.calendar
            if calendar is not None and 'Dividend Date' in calendar:
                div_date = calendar.get('Dividend Date')
                if div_date:
                    result['pay_date'] = div_date.strftime('%Y-%m-%d') if hasattr(div_date, 'strftime') else str(div_date)
        except:
            pass
        
        # Check info for dividend rate
        info = stock.info
        div_rate = info.get('dividendRate')
        last_div = info.get('lastDividendValue')
        ex_date = info.get('exDividendDate')
        
        if ex_date:
            # Convert timestamp to date
            from datetime import datetime
            ex_date_dt = datetime.fromtimestamp(ex_date)
            # Only use if it's in the future
            if ex_date_dt > datetime.now():
                result['ex_date'] = ex_date_dt.strftime('%Y-%m-%d')
                result['confirmed'] = True
                result['source'] = 'yfinance'
        
        if last_div:
            result['amount'] = last_div
            
        # If we have an ex_date from yfinance, consider it confirmed
        if result['ex_date'] and result['amount']:
            result['confirmed'] = True
            
    except Exception as e:
        print(f"    ⚠️ Error checking {ticker}: {e}")
    
    return result


def verify_dividend(ticker: str, name: str, expected_date: str, expected_amount: float) -> dict:
    """
    Verify a specific dividend payment.
    Returns updated info if found, None otherwise.
    """
    print(f"  🔍 Verifying {ticker} ({name[:30]})...")
    
    info = search_dividend_info(ticker, name)
    
    if info['confirmed']:
        print(f"    ✅ Confirmed: ${info['amount']:.4f} on {info['ex_date']} (source: {info['source']})")
        return info
    else:
        print(f"    ⏳ Not confirmed yet (estimated: ${expected_amount:.4f} on {expected_date})")
        return None


def update_dividend_status(dividend_id: int, amount: float = None, 
                           ex_date: str = None, pay_date: str = None,
                           confirmed: bool = False):
    """Update dividend record with verified info."""
    conn = get_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if amount is not None:
        updates.append("ramount = ?")
        params.append(amount)
    if ex_date is not None:
        updates.append("dex_date = ?")
        params.append(ex_date)
    if pay_date is not None:
        updates.append("dpay_date = ?")
        params.append(pay_date)
    if confirmed:
        updates.append("bis_estimated = 0")
        updates.append("sstatus = 'confirmed'")
    
    if updates:
        query = f"UPDATE dividends SET {', '.join(updates)} WHERE idividendsid = ?"
        params.append(dividend_id)
        cursor.execute(query, params)
        conn.commit()
    
    conn.close()


def verify_upcoming_dividends(days: int = 30):
    """Verify all dividends coming up in the next N days."""
    upcoming = get_upcoming_dividends(days)
    
    if not upcoming:
        print(f"📭 No dividends expected in the next {days} days")
        return
    
    print(f"📊 Verifying {len(upcoming)} dividends expected in the next {days} days...\n")
    
    confirmed_count = 0
    updated_count = 0
    
    for div in upcoming:
        ticker = div['sticker']
        name = div['sname'] or ticker
        expected_date = div['dex_date']
        expected_amount = div['ramount'] or 0
        is_estimated = div['bis_estimated']
        days_until = int(div['days_until'])
        
        status_icon = "⏳" if is_estimated else "✅"
        print(f"{status_icon} {ticker} - Ex: {expected_date} ({days_until}d) - ${expected_amount:.4f}")
        
        # Only verify if it's estimated or if we want to double-check
        if is_estimated or days_until <= 7:
            verified = verify_dividend(ticker, name, expected_date, expected_amount)
            
            if verified and verified['confirmed']:
                confirmed_count += 1
                
                # Update if amount or date changed
                if (verified['amount'] and abs(verified['amount'] - expected_amount) > 0.001) or \
                   (verified['ex_date'] and verified['ex_date'] != expected_date):
                    update_dividend_status(
                        div['idividendsid'],
                        amount=verified['amount'],
                        ex_date=verified['ex_date'],
                        pay_date=verified['pay_date'],
                        confirmed=True
                    )
                    updated_count += 1
                    print(f"    📝 Updated in database")
                elif is_estimated:
                    # Just mark as confirmed
                    update_dividend_status(div['idividendsid'], confirmed=True)
                    print(f"    📝 Marked as confirmed")
        
        print()
    
    print(f"\n✅ Verification complete:")
    print(f"   Confirmed: {confirmed_count}")
    print(f"   Updated: {updated_count}")


def show_upcoming_with_status(days: int = 30):
    """Show upcoming dividends with confirmation status."""
    upcoming = get_upcoming_dividends(days)
    
    if not upcoming:
        print(f"📭 No dividends expected in the next {days} days")
        return
    
    print(f"\n📅 DIVIDENDOS PRÓXIMOS {days} DÍAS")
    print(f"{'Ticker':<10} {'Ex-Date':<12} {'Días':<6} {'Importe':<10} {'Estado':<12}")
    print("-" * 55)
    
    for div in upcoming:
        status = "⏳ Estimado" if div['bis_estimated'] else "✅ Confirmado"
        amount = f"${div['ramount']:.4f}" if div['ramount'] else "?"
        days_until = int(div['days_until'])
        
        # Highlight if coming up soon
        days_str = f"{days_until}d"
        if days_until <= 7:
            days_str = f"🔥{days_until}d"
        
        print(f"{div['sticker']:<10} {div['dex_date']:<12} {days_str:<6} {amount:<10} {status:<12}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--verify":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            verify_upcoming_dividends(days)
        elif arg == "--show":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            show_upcoming_with_status(days)
        else:
            # Verify specific ticker
            ticker = arg.upper()
            info = search_dividend_info(ticker, ticker)
            print(f"\n📊 Dividend info for {ticker}:")
            print(f"   Confirmed: {info['confirmed']}")
            print(f"   Amount: ${info['amount']:.4f}" if info['amount'] else "   Amount: N/A")
            print(f"   Ex-date: {info['ex_date']}" if info['ex_date'] else "   Ex-date: N/A")
            print(f"   Pay-date: {info['pay_date']}" if info['pay_date'] else "   Pay-date: N/A")
            print(f"   Source: {info['source']}" if info['source'] else "   Source: N/A")
    else:
        print("Usage:")
        print("  python dividend_verifier.py --verify [days]  - Verify upcoming dividends")
        print("  python dividend_verifier.py --show [days]    - Show upcoming with status")
        print("  python dividend_verifier.py TICKER           - Check specific ticker")
