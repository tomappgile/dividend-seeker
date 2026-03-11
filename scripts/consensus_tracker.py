#!/usr/bin/env python3
"""
Consensus/Sentiment Tracker
- Fetches analyst ratings and price targets from yfinance
- Stores historical data for trend analysis
- Calculates sentiment scores

Column naming convention (Hungarian notation):
- i = INTEGER, s = TEXT, r = REAL, b = BOOLEAN, d = DATE, t = TIMESTAMP
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


def fetch_consensus(ticker: str) -> dict:
    """Fetch analyst consensus data from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Price targets
        price_current = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        price_target_low = info.get('targetLowPrice')
        price_target_avg = info.get('targetMeanPrice')
        price_target_high = info.get('targetHighPrice')
        
        # Calculate upside
        upside = None
        if price_current and price_target_avg:
            upside = ((price_target_avg - price_current) / price_current) * 100
        
        # Analyst recommendations
        analyst_count = info.get('numberOfAnalystOpinions', 0)
        recommendation = info.get('recommendationKey', '').lower()
        recommendation_mean = info.get('recommendationMean')  # 1.0 (Strong Buy) to 5.0 (Strong Sell)
        
        # Map recommendation to standard rating
        rating_map = {
            'strong_buy': 'Strong Buy',
            'buy': 'Buy',
            'hold': 'Hold',
            'sell': 'Sell',
            'strong_sell': 'Strong Sell'
        }
        rating = rating_map.get(recommendation, 'Hold')
        
        # Try to get recommendation breakdown
        try:
            recs = stock.recommendations
            if recs is not None and len(recs) > 0:
                # Get most recent recommendations (last 3 months)
                recent = recs.tail(10)
                strong_buy = int(recent.get('strongBuy', recent.get('Strong Buy', 0)).sum()) if 'strongBuy' in recent or 'Strong Buy' in recent else 0
                buy = int(recent.get('buy', recent.get('Buy', 0)).sum()) if 'buy' in recent or 'Buy' in recent else 0
                hold = int(recent.get('hold', recent.get('Hold', 0)).sum()) if 'hold' in recent or 'Hold' in recent else 0
                sell = int(recent.get('sell', recent.get('Sell', 0)).sum()) if 'sell' in recent or 'Sell' in recent else 0
                strong_sell = int(recent.get('strongSell', recent.get('Strong Sell', 0)).sum()) if 'strongSell' in recent or 'Strong Sell' in recent else 0
            else:
                strong_buy = buy = hold = sell = strong_sell = 0
        except:
            strong_buy = buy = hold = sell = strong_sell = 0
        
        # Calculate sentiment
        if recommendation_mean:
            # Convert 1-5 scale to -1 to +1
            sentiment_score = (3 - recommendation_mean) / 2  # 1->1.0, 3->0, 5->-1.0
            if sentiment_score > 0.3:
                sentiment = 'bullish'
            elif sentiment_score < -0.3:
                sentiment = 'bearish'
            else:
                sentiment = 'neutral'
        else:
            sentiment_score = 0
            sentiment = 'neutral'
        
        return {
            'price_current': price_current,
            'price_target_low': price_target_low,
            'price_target_avg': price_target_avg,
            'price_target_high': price_target_high,
            'upside_potential': upside,
            'rating': rating,
            'rating_score': recommendation_mean,
            'analyst_count': analyst_count,
            'strong_buy': strong_buy,
            'buy': buy,
            'hold': hold,
            'sell': sell,
            'strong_sell': strong_sell,
            'sentiment': sentiment,
            'sentiment_score': round(sentiment_score, 2) if sentiment_score else 0
        }
        
    except Exception as e:
        return {'error': str(e)}


def save_consensus(ticker: str, data: dict):
    """Save consensus data to database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get security_id for this ticker
    cursor.execute("SELECT isecuritiesid FROM stocks WHERE sticker = ?", (ticker,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    
    security_id = row['isecuritiesid']
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Get previous data for change calculation
    cursor.execute("""
        SELECT rprice_target_avg, rrating_score 
        FROM consensus 
        WHERE isecuritiesid = ? AND dcapture_date < ?
        ORDER BY dcapture_date DESC LIMIT 1
    """, (security_id, today))
    prev = cursor.fetchone()
    
    price_target_change = None
    rating_change = None
    if prev and data.get('price_target_avg') and prev['rprice_target_avg']:
        price_target_change = ((data['price_target_avg'] - prev['rprice_target_avg']) / prev['rprice_target_avg']) * 100
    if prev and data.get('rating_score') and prev['rrating_score']:
        rating_change = data['rating_score'] - prev['rrating_score']
    
    cursor.execute("""
        INSERT INTO consensus (
            isecuritiesid, dcapture_date,
            rprice_target_low, rprice_target_avg, rprice_target_high,
            rprice_current, rupside_potential,
            srating, rrating_score, ianalyst_count,
            istrong_buy, ibuy, ihold, isell, istrong_sell,
            ssentiment, rsentiment_score,
            rprice_target_change_1m, rrating_change_1m
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(isecuritiesid, dcapture_date) DO UPDATE SET
            rprice_target_low = excluded.rprice_target_low,
            rprice_target_avg = excluded.rprice_target_avg,
            rprice_target_high = excluded.rprice_target_high,
            rprice_current = excluded.rprice_current,
            rupside_potential = excluded.rupside_potential,
            srating = excluded.srating,
            rrating_score = excluded.rrating_score,
            ianalyst_count = excluded.ianalyst_count,
            istrong_buy = excluded.istrong_buy,
            ibuy = excluded.ibuy,
            ihold = excluded.ihold,
            isell = excluded.isell,
            istrong_sell = excluded.istrong_sell,
            ssentiment = excluded.ssentiment,
            rsentiment_score = excluded.rsentiment_score,
            rprice_target_change_1m = excluded.rprice_target_change_1m,
            rrating_change_1m = excluded.rrating_change_1m
    """, (
        security_id, today,
        data.get('price_target_low'),
        data.get('price_target_avg'),
        data.get('price_target_high'),
        data.get('price_current'),
        data.get('upside_potential'),
        data.get('rating'),
        data.get('rating_score'),
        data.get('analyst_count'),
        data.get('strong_buy', 0),
        data.get('buy', 0),
        data.get('hold', 0),
        data.get('sell', 0),
        data.get('strong_sell', 0),
        data.get('sentiment'),
        data.get('sentiment_score'),
        price_target_change,
        rating_change
    ))
    
    conn.commit()
    conn.close()
    return True


def update_consensus(ticker: str) -> dict:
    """Fetch and save consensus for a ticker."""
    data = fetch_consensus(ticker)
    if 'error' in data:
        return data
    
    save_consensus(ticker, data)
    return data


def update_all_consensus():
    """Update consensus for all tracked stocks."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT sticker FROM stocks")
    tickers = [row['sticker'] for row in cursor.fetchall()]
    conn.close()
    
    print(f"📊 Updating consensus for {len(tickers)} stocks...")
    
    results = []
    for i, ticker in enumerate(tickers):
        data = update_consensus(ticker)
        if 'error' not in data:
            upside = data.get('upside_potential')
            upside_str = f"{upside:+.1f}%" if upside else "N/A"
            sentiment = data.get('sentiment', 'N/A')
            print(f"  ✅ {ticker}: {data.get('rating', 'N/A')} | Upside: {upside_str} | {sentiment}")
            results.append((ticker, data))
        else:
            print(f"  ⚠️ {ticker}: {data['error'][:50]}")
        
        if (i + 1) % 20 == 0:
            print(f"  ... {i+1}/{len(tickers)} processed")
    
    print(f"\n✅ Updated consensus for {len(results)} stocks")
    return results


def show_consensus_summary():
    """Show summary of current consensus data."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            s.sticker,
            c.srating,
            c.rupside_potential,
            c.ssentiment,
            c.ianalyst_count,
            snap.rdividend_yield
        FROM consensus c
        JOIN stocks s ON c.isecuritiesid = s.isecuritiesid
        JOIN snapshots snap ON s.sticker = snap.sticker
            AND snap.dscan_date = (SELECT MAX(dscan_date) FROM snapshots WHERE sticker = s.sticker)
        WHERE c.dcapture_date = (SELECT MAX(dcapture_date) FROM consensus WHERE isecuritiesid = c.isecuritiesid)
        AND snap.rdividend_yield >= 5
        ORDER BY c.rupside_potential DESC
        LIMIT 20
    """)
    
    print(f"\n{'Ticker':<10} {'Rating':<12} {'Upside':<10} {'Sentiment':<10} {'Yield':<8} {'Analysts':<8}")
    print("-" * 65)
    
    for row in cursor.fetchall():
        upside = f"{row['rupside_potential']:+.1f}%" if row['rupside_potential'] else "N/A"
        yield_str = f"{row['rdividend_yield']:.1f}%" if row['rdividend_yield'] else "N/A"
        print(f"{row['sticker']:<10} {row['srating'] or 'N/A':<12} {upside:<10} {row['ssentiment'] or 'N/A':<10} {yield_str:<8} {row['ianalyst_count'] or 0:<8}")
    
    conn.close()


def show_trend(ticker: str, days: int = 30):
    """Show consensus trend for a specific ticker."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            c.dcapture_date,
            c.rprice_target_avg,
            c.rupside_potential,
            c.srating,
            c.rsentiment_score
        FROM consensus c
        JOIN stocks s ON c.isecuritiesid = s.isecuritiesid
        WHERE s.sticker = ?
        ORDER BY c.dcapture_date DESC
        LIMIT ?
    """, (ticker, days))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print(f"❌ No consensus data for {ticker}")
        return
    
    print(f"\n📈 Consensus Trend for {ticker}:")
    print(f"{'Date':<12} {'Target':<10} {'Upside':<10} {'Rating':<12} {'Sentiment':<10}")
    print("-" * 55)
    
    for row in rows:
        target = f"${row['rprice_target_avg']:.2f}" if row['rprice_target_avg'] else "N/A"
        upside = f"{row['rupside_potential']:+.1f}%" if row['rupside_potential'] else "N/A"
        sent = f"{row['rsentiment_score']:+.2f}" if row['rsentiment_score'] else "N/A"
        print(f"{row['dcapture_date']:<12} {target:<10} {upside:<10} {row['srating'] or 'N/A':<12} {sent:<10}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--all":
            update_all_consensus()
            print("\n" + "="*65)
            show_consensus_summary()
        elif arg == "--summary":
            show_consensus_summary()
        elif arg == "--trend" and len(sys.argv) > 2:
            show_trend(sys.argv[2].upper())
        else:
            ticker = arg.upper()
            print(f"\n📊 Fetching consensus for {ticker}...")
            data = update_consensus(ticker)
            
            if 'error' in data:
                print(f"❌ Error: {data['error']}")
            else:
                print(f"✅ Consensus data for {ticker}:")
                print(f"   Rating: {data.get('rating', 'N/A')} ({data.get('rating_score', 'N/A')})")
                print(f"   Analysts: {data.get('analyst_count', 0)}")
                print(f"   Target: ${data.get('price_target_avg', 0):.2f} (${data.get('price_target_low', 0):.2f} - ${data.get('price_target_high', 0):.2f})")
                upside = data.get('upside_potential')
                print(f"   Upside: {upside:+.1f}%" if upside else "   Upside: N/A")
                print(f"   Sentiment: {data.get('sentiment', 'N/A')} ({data.get('sentiment_score', 0):+.2f})")
                
                if len(sys.argv) > 2 and sys.argv[2] == "--trend":
                    show_trend(ticker)
    else:
        print("Usage:")
        print("  python consensus_tracker.py TICKER          - Fetch consensus for one stock")
        print("  python consensus_tracker.py TICKER --trend  - Also show historical trend")
        print("  python consensus_tracker.py --all           - Update all tracked stocks")
        print("  python consensus_tracker.py --summary       - Show current consensus summary")
        print("  python consensus_tracker.py --trend TICKER  - Show trend for ticker")
