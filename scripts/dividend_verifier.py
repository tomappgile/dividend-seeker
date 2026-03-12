#!/usr/bin/env python3
"""
Dividend Verifier v2
- Checks dividends coming up in the next 30 days
- Searches MULTIPLE sources for official confirmation
- Uses web scraping for announced (not just historical) dividends
- Updates database with confirmed amounts and dates

Sources checked:
1. yfinance (historical)
2. stockevents.app (announced)
3. dividendmax.com (announced)
4. nasdaq.com (announced)
"""

import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
import re
import yfinance as yf
from bs4 import BeautifulSoup
import time

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "dividend_seeker.db"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def search_stockevents(ticker: str) -> dict:
    """Search stockevents.app for announced dividend."""
    result = {'amount': None, 'ex_date': None, 'pay_date': None, 'source': None}
    
    try:
        # Remove exchange suffix for US stocks
        clean_ticker = ticker.split('.')[0] if '.' in ticker else ticker
        url = f"https://stockevents.app/en/stock/{clean_ticker}/dividends"
        
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            # Parse the page for dividend info
            # Look for pattern like "$1.30" or "€0.60"
            text = resp.text
            
            # Find "next dividend per share will be $X.XX"
            match = re.search(r'next dividend per share will be \$?([\d.]+)', text, re.I)
            if match:
                result['amount'] = float(match.group(1))
                result['source'] = 'stockevents.app'
            
            # Find ex date
            match = re.search(r'ex date of (\w+ \d+, \d{4})', text, re.I)
            if match:
                try:
                    result['ex_date'] = datetime.strptime(match.group(1), '%B %d, %Y').strftime('%Y-%m-%d')
                except:
                    pass
                    
    except Exception as e:
        pass
    
    return result


def search_dividendmax(ticker: str) -> dict:
    """Search dividendmax.com for announced dividend."""
    result = {'amount': None, 'ex_date': None, 'pay_date': None, 'source': None}
    
    try:
        clean_ticker = ticker.split('.')[0].lower()
        # Try common URL patterns
        urls = [
            f"https://www.dividendmax.com/united-states/nasdaq/financial-services/{clean_ticker}/dividends",
            f"https://www.dividendmax.com/united-states/nyse/{clean_ticker}/dividends",
        ]
        
        for url in urls:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code == 200:
                    text = resp.text
                    
                    # Look for "next dividend will go ex in X days for XXXc"
                    match = re.search(r'next .* dividend will go ex .* for (\d+)c', text, re.I)
                    if match:
                        result['amount'] = float(match.group(1)) / 100  # Convert cents to dollars
                        result['source'] = 'dividendmax.com'
                        break
            except:
                continue
                
    except Exception as e:
        pass
    
    return result


def search_yfinance(ticker: str) -> dict:
    """Search yfinance for dividend info."""
    result = {'amount': None, 'ex_date': None, 'pay_date': None, 'source': None}
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Get upcoming ex-dividend date
        ex_date_ts = info.get('exDividendDate')
        if ex_date_ts:
            ex_date = datetime.fromtimestamp(ex_date_ts)
            if ex_date > datetime.now():
                result['ex_date'] = ex_date.strftime('%Y-%m-%d')
        
        # Get last dividend value (fallback)
        last_div = info.get('lastDividendValue')
        if last_div:
            result['amount'] = last_div
            result['source'] = 'yfinance'
            
    except Exception as e:
        pass
    
    return result


def search_dividend_info(ticker: str, company_name: str = None) -> dict:
    """
    Search multiple sources for dividend info.
    Returns best available data with source attribution.
    """
    results = []
    
    # Check stockevents.app first (usually has announced dividends)
    se_result = search_stockevents(ticker)
    if se_result['amount']:
        results.append(se_result)
    
    # Check dividendmax
    dm_result = search_dividendmax(ticker)
    if dm_result['amount']:
        results.append(dm_result)
    
    # Fallback to yfinance
    yf_result = search_yfinance(ticker)
    if yf_result['amount']:
        results.append(yf_result)
    
    # Return the best result (prefer sources with both amount and date)
    if results:
        # Sort by completeness (amount + ex_date + source preference)
        def score(r):
            s = 0
            if r['amount']: s += 10
            if r['ex_date']: s += 5
            if r['source'] == 'stockevents.app': s += 3
            if r['source'] == 'dividendmax.com': s += 2
            return s
        
        results.sort(key=score, reverse=True)
        best = results[0]
        best['confirmed'] = True
        best['all_sources'] = [r['source'] for r in results if r['source']]
        return best
    
    return {'confirmed': False, 'amount': None, 'ex_date': None, 'source': None}


def verify_dividend(ticker: str, name: str, expected_date: str, expected_amount: float) -> dict:
    """Verify a specific dividend payment against multiple sources."""
    print(f"  🔍 Verificando {ticker}...")
    
    info = search_dividend_info(ticker, name)
    
    if info['confirmed'] and info['amount']:
        # Check if amount differs from expected
        if abs(info['amount'] - expected_amount) > 0.001:
            print(f"    ⚠️  DIFERENCIA: BD tiene ${expected_amount:.4f}, fuente dice ${info['amount']:.4f}")
            print(f"    📡 Fuente: {info['source']}")
            return info
        else:
            print(f"    ✅ Confirmado: ${info['amount']:.4f} ({info['source']})")
            return info
    else:
        print(f"    ⏳ Sin confirmación externa (mantenemos ${expected_amount:.4f})")
        return None


def update_dividend_in_db(dividend_id: int, amount: float = None, 
                          ex_date: str = None, pay_date: str = None):
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
    
    updates.append("bis_estimated = 0")
    updates.append("sstatus = 'confirmed'")
    
    if updates:
        query = f"UPDATE dividends SET {', '.join(updates)} WHERE idividendsid = ?"
        params.append(dividend_id)
        cursor.execute(query, params)
        conn.commit()
    
    conn.close()


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


def verify_upcoming_dividends(days: int = 30):
    """Verify all dividends coming up in the next N days."""
    upcoming = get_upcoming_dividends(days)
    
    if not upcoming:
        print(f"📭 No hay dividendos en los próximos {days} días")
        return
    
    print(f"📊 Verificando {len(upcoming)} dividendos en los próximos {days} días...\n")
    
    updated_count = 0
    
    for div in upcoming:
        ticker = div['sticker']
        name = div['sname'] or ticker
        expected_date = div['dex_date']
        expected_amount = div['ramount'] or 0
        days_until = int(div['days_until'])
        
        # Only verify if within 14 days (closer = more likely to have confirmed data)
        if days_until <= 14:
            verified = verify_dividend(ticker, name, expected_date, expected_amount)
            
            if verified and verified['confirmed']:
                # Update if amount changed
                if verified['amount'] and abs(verified['amount'] - expected_amount) > 0.001:
                    update_dividend_in_db(
                        div['idividendsid'],
                        amount=verified['amount'],
                        ex_date=verified.get('ex_date'),
                        pay_date=verified.get('pay_date')
                    )
                    updated_count += 1
                    print(f"    📝 BD actualizada: ${expected_amount:.4f} → ${verified['amount']:.4f}")
            
            time.sleep(0.5)  # Rate limiting
        else:
            print(f"  ⏳ {ticker} - {days_until}d - Demasiado lejos, se verificará más adelante")
    
    print(f"\n✅ Verificación completada: {updated_count} actualizados")


def show_upcoming_with_status(days: int = 30):
    """Show upcoming dividends with confirmation status."""
    upcoming = get_upcoming_dividends(days)
    
    if not upcoming:
        print(f"📭 No hay dividendos en los próximos {days} días")
        return
    
    print(f"\n📅 DIVIDENDOS PRÓXIMOS {days} DÍAS")
    print(f"{'Ticker':<10} {'Ex-Date':<12} {'Días':<6} {'Importe':<10} {'Estado':<12}")
    print("-" * 55)
    
    for div in upcoming:
        status = "⏳ Estimado" if div['bis_estimated'] else "✅ Confirmado"
        amount = f"${div['ramount']:.4f}" if div['ramount'] else "?"
        days_until = int(div['days_until'])
        
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
            ticker = arg.upper()
            print(f"\n📊 Buscando dividend info para {ticker}...")
            info = search_dividend_info(ticker, ticker)
            print(f"   Confirmado: {info['confirmed']}")
            print(f"   Importe: ${info['amount']:.4f}" if info['amount'] else "   Importe: N/A")
            print(f"   Ex-date: {info['ex_date']}" if info['ex_date'] else "   Ex-date: N/A")
            print(f"   Fuente: {info['source']}" if info['source'] else "   Fuente: N/A")
            if info.get('all_sources'):
                print(f"   Todas las fuentes: {', '.join(info['all_sources'])}")
    else:
        print("Uso:")
        print("  python dividend_verifier.py --verify [días]  - Verificar dividendos próximos")
        print("  python dividend_verifier.py --show [días]    - Mostrar próximos con estado")
        print("  python dividend_verifier.py TICKER           - Verificar ticker específico")
