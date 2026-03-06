#!/usr/bin/env python3
"""
Dividend Seeker - Web Dashboard
Flask API + Static Dashboard
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import json
from pathlib import Path
from datetime import datetime
import os
import requests

app = Flask(__name__, static_folder='static')
CORS(app)

# Handle paths for both local and Railway deployment
BASE_DIR = Path(__file__).parent.parent
DATA_PATH = BASE_DIR / 'data'

# GitHub raw URL for fresh data
GITHUB_DATA_URL = "https://raw.githubusercontent.com/tomappgile/dividend-seeker/main/data/candidates/MAIN_LIST.json"

# Cache for GitHub data (refresh every 5 minutes)
_cache = {'data': None, 'timestamp': None}
CACHE_TTL = 300  # 5 minutes


def load_candidates():
    """Load candidates from GitHub (with cache) or fallback to local file"""
    import time
    
    # Check cache
    if _cache['data'] and _cache['timestamp']:
        if time.time() - _cache['timestamp'] < CACHE_TTL:
            return _cache['data']
    
    # Try GitHub first
    try:
        response = requests.get(GITHUB_DATA_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            _cache['data'] = data
            _cache['timestamp'] = time.time()
            return data
    except Exception as e:
        print(f"GitHub fetch failed: {e}")
    
    # Fallback to local file
    main_list = DATA_PATH / 'candidates' / 'MAIN_LIST.json'
    if main_list.exists():
        with open(main_list) as f:
            return json.load(f)
    
    return {'stocks': [], 'scan_date': 'N/A'}


def get_all_stocks():
    """Get all stocks from all tiers or flat list"""
    data = load_candidates()
    
    # New format: flat 'stocks' list
    if 'stocks' in data:
        return data['stocks']
    
    # Old format: tiered lists
    all_stocks = (
        data.get('tier1_high_sustainable', []) +
        data.get('tier2_moderate_sustainable', []) +
        data.get('tier3_high_risk', [])
    )
    return all_stocks


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/stock.html')
def stock_page():
    return send_from_directory('static', 'stock.html')


@app.route('/api/debug')
def api_debug():
    """Debug endpoint to check file paths"""
    import os
    main_list = DATA_PATH / 'candidates' / 'MAIN_LIST.json'
    
    info = {
        'base_dir': str(BASE_DIR),
        'data_path': str(DATA_PATH),
        'main_list_path': str(main_list),
        'main_list_exists': main_list.exists(),
        'cwd': os.getcwd(),
        'files_in_candidates': []
    }
    
    candidates_dir = DATA_PATH / 'candidates'
    if candidates_dir.exists():
        info['files_in_candidates'] = os.listdir(candidates_dir)
    
    if main_list.exists():
        with open(main_list) as f:
            data = json.load(f)
        info['scan_date'] = data.get('scan_date', 'N/A')
        info['total_stocks'] = data.get('total', len(data.get('stocks', [])))
        info['first_ticker'] = data.get('stocks', [{}])[0].get('ticker', 'N/A') if data.get('stocks') else 'N/A'
    
    return jsonify(info)


@app.route('/api/stats')
def api_stats():
    """Dashboard stats"""
    stocks = get_all_stocks()
    
    if not stocks:
        return jsonify({
            'total_stocks': 0,
            'avg_yield': 0,
            'max_yield': 0,
            'min_yield': 0,
            'tier1_count': 0,
            'last_scan': None
        })
    
    yields = [s.get('dividend_yield', 0) for s in stocks]
    data = load_candidates()
    
    return jsonify({
        'total_stocks': len(stocks),
        'avg_yield': round(sum(yields) / len(yields), 2) if yields else 0,
        'max_yield': round(max(yields), 2) if yields else 0,
        'min_yield': round(min(yields), 2) if yields else 0,
        'tier1_count': len(data.get('tier1_high_sustainable', [])),
        'last_scan': data.get('scan_date', '2026-02-15')
    })


@app.route('/api/stocks')
def api_stocks():
    """List all stocks with filters"""
    min_yield = request.args.get('min_yield', 5, type=float)
    market = request.args.get('market', None)
    sustainable_only = request.args.get('sustainable', 'false') == 'true'
    min_div_score = request.args.get('min_div_score', 0, type=int)
    min_cap_score = request.args.get('min_cap_score', 0, type=int)
    asset_type = request.args.get('asset_type', None)  # stock, etf, reit, mreit, bdc, cef
    stocks_only = request.args.get('stocks_only', 'false') == 'true'  # Exclude ETFs/funds
    sort_by = request.args.get('sort', 'yield')  # yield, score, dividend_score, capital_score
    limit = request.args.get('limit', 100, type=int)
    
    stocks = get_all_stocks()
    
    # Filter
    filtered = []
    for s in stocks:
        if s.get('dividend_yield', 0) < min_yield:
            continue
        # Market filter - check both ocean_market and market fields
        if market:
            stock_market = s.get('ocean_market', '') or s.get('market', '')
            if market.lower() not in stock_market.lower():
                continue
        if sustainable_only and not s.get('sustainable', True):
            continue
        if s.get('dividend_score', 0) < min_div_score:
            continue
        if s.get('capital_score', 0) < min_cap_score:
            continue
        # Asset type filter
        if asset_type and s.get('asset_type', 'stock') != asset_type:
            continue
        # Stocks only - exclude ETFs, CEFs, and other funds
        if stocks_only and s.get('asset_type', 'stock') in ['etf', 'cef']:
            continue
        filtered.append(s)
    
    # Sort
    if sort_by == 'score':
        filtered.sort(key=lambda x: (x.get('dividend_score', 0) + x.get('capital_score', 0), x.get('dividend_yield', 0)), reverse=True)
    elif sort_by == 'dividend_score':
        filtered.sort(key=lambda x: (x.get('dividend_score', 0), x.get('dividend_yield', 0)), reverse=True)
    elif sort_by == 'capital_score':
        filtered.sort(key=lambda x: (x.get('capital_score', 0), x.get('dividend_yield', 0)), reverse=True)
    else:
        filtered.sort(key=lambda x: x.get('dividend_yield', 0), reverse=True)
    
    return jsonify(filtered[:limit])


@app.route('/api/top-scores')
def api_top_scores():
    """Get stocks with best combined scores"""
    limit = request.args.get('limit', 20, type=int)
    min_yield = request.args.get('min_yield', 5, type=float)
    
    stocks = get_all_stocks()
    
    # Filter and add total score
    scored = []
    for s in stocks:
        if s.get('dividend_yield', 0) < min_yield:
            continue
        div_score = s.get('dividend_score', 0)
        cap_score = s.get('capital_score', 0)
        if div_score and cap_score:
            s['total_score'] = div_score + cap_score
            scored.append(s)
    
    # Sort by total score, then yield
    scored.sort(key=lambda x: (x['total_score'], x.get('dividend_yield', 0)), reverse=True)
    
    return jsonify(scored[:limit])


@app.route('/api/top-opportunities')
def api_top_opportunities():
    """Get stocks with high yield AND positive analyst consensus (best of both worlds)"""
    limit = request.args.get('limit', 20, type=int)
    min_yield = request.args.get('min_yield', 5, type=float)
    min_upside = request.args.get('min_upside', 0, type=float)
    
    import sqlite3
    db_path = DATA_PATH / 'dividend_seeker.db'
    
    if not db_path.exists():
        return jsonify({'error': 'Database not found'}), 500
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            s.ticker, s.name, s.sector, s.market,
            sn.price, sn.dividend_yield, sn.payout_ratio,
            sn.dividend_score, sn.capital_score,
            sn.price_target_avg, sn.price_target_high, sn.price_target_low,
            sn.upside_potential, sn.analyst_rating, sn.analyst_count
        FROM stocks s
        JOIN snapshots sn ON s.ticker = sn.ticker
        WHERE sn.scan_date = (SELECT MAX(scan_date) FROM snapshots)
          AND sn.dividend_yield >= ?
          AND sn.upside_potential >= ?
          AND sn.analyst_count > 0
        ORDER BY 
            CASE WHEN sn.analyst_rating = 'Strong Buy' THEN 5
                 WHEN sn.analyst_rating = 'Buy' THEN 4
                 WHEN sn.analyst_rating = 'Hold' THEN 3
                 WHEN sn.analyst_rating = 'Sell' THEN 2
                 ELSE 1 END DESC,
            sn.upside_potential DESC
        LIMIT ?
    """, (min_yield, min_upside, limit))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({
        'description': 'Acciones con yield alto + consenso positivo de analistas',
        'count': len(results),
        'filters': {'min_yield': min_yield, 'min_upside': min_upside},
        'stocks': results
    })


@app.route('/api/consensus/<ticker>')
def api_consensus(ticker):
    """Get analyst consensus data for a specific stock"""
    import sqlite3
    db_path = DATA_PATH / 'dividend_seeker.db'
    
    if not db_path.exists():
        return jsonify({'error': 'Database not found'}), 500
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            s.ticker, s.name,
            sn.price,
            sn.price_target_avg, sn.price_target_high, sn.price_target_low,
            sn.upside_potential, sn.analyst_rating, sn.analyst_count,
            sn.scan_date
        FROM stocks s
        JOIN snapshots sn ON s.ticker = sn.ticker
        WHERE s.ticker = ?
        ORDER BY sn.scan_date DESC
        LIMIT 1
    """, (ticker,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Stock not found'}), 404
    
    data = dict(row)
    
    # Add interpretation
    upside = data.get('upside_potential')
    rating = data.get('analyst_rating')
    
    if upside and rating:
        if upside > 20 and rating in ['Strong Buy', 'Buy']:
            data['interpretation'] = '🟢 Muy infravalorado según analistas'
        elif upside > 10 and rating in ['Strong Buy', 'Buy']:
            data['interpretation'] = '🟢 Infravalorado con consenso positivo'
        elif upside > 0 and rating == 'Hold':
            data['interpretation'] = '🟡 Ligero potencial, consenso neutral'
        elif upside < 0:
            data['interpretation'] = '🔴 Sobrevalorado según analistas'
        else:
            data['interpretation'] = '⚪ Sin señal clara'
    else:
        data['interpretation'] = '⚪ Sin datos de consenso'
    
    return jsonify(data)


@app.route('/api/stock/<ticker>')
def api_stock_detail(ticker):
    """Get stock details"""
    stocks = get_all_stocks()
    
    for s in stocks:
        if s['ticker'] == ticker:
            return jsonify({
                'current': s,
                'history': [],
                'dividends': []
            })
    
    return jsonify({'error': 'Stock not found'}), 404


def get_cached_analysis(ticker):
    """Get cached analysis for a stock"""
    cache_file = DATA_PATH / 'analysis' / f'{ticker.replace(".", "_")}.json'
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)
    return None


def save_analysis(ticker, analysis):
    """Save analysis to cache"""
    cache_dir = DATA_PATH / 'analysis'
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f'{ticker.replace(".", "_")}.json'
    with open(cache_file, 'w') as f:
        json.dump(analysis, f, indent=2)


def generate_analysis(ticker):
    """Generate fresh analysis for a stock using yfinance"""
    try:
        import yfinance as yf
        
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period='1y')
        divs = stock.dividends
        
        # Basic data
        analysis = {
            'ticker': ticker,
            'analyzed_at': datetime.now().isoformat(),
            'name': info.get('longName') or info.get('shortName'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'currency': info.get('currency'),
            'price': info.get('currentPrice') or info.get('regularMarketPrice'),
            'dividend_yield': info.get('dividendYield', 0),
            'dividend_rate': info.get('dividendRate'),
            'payout_ratio': (info.get('payoutRatio') or 0) * 100,
            'pe_ratio': info.get('trailingPE'),
            'pb_ratio': info.get('priceToBook'),
            'market_cap': info.get('marketCap'),
            'market_cap_b': round(info.get('marketCap', 0) / 1e9, 2) if info.get('marketCap') else None,
            'week_52_high': info.get('fiftyTwoWeekHigh'),
            'week_52_low': info.get('fiftyTwoWeekLow'),
        }
        
        # Calculate discount from 52-week high
        if analysis['week_52_high'] and analysis['price']:
            analysis['discount_from_high'] = round(
                ((analysis['week_52_high'] - analysis['price']) / analysis['week_52_high']) * 100, 1
            )
        
        # Get ex-dividend date
        ex_div = info.get('exDividendDate')
        if ex_div:
            from datetime import datetime as dt
            analysis['ex_dividend_date'] = dt.fromtimestamp(ex_div).strftime('%Y-%m-%d')
        
        # Find dates of 52-week high and low from history
        if len(hist) > 0:
            high_idx = hist['High'].idxmax()
            low_idx = hist['Low'].idxmin()
            analysis['week_52_high_date'] = high_idx.strftime('%d %b %Y')
            analysis['week_52_low_date'] = low_idx.strftime('%d %b %Y')
        
        # Performance
        if len(hist) > 0:
            current = hist['Close'].iloc[-1]
            if len(hist) >= 21:
                analysis['change_1m'] = round(((current - hist['Close'].iloc[-21]) / hist['Close'].iloc[-21]) * 100, 1)
            if len(hist) >= 63:
                analysis['change_3m'] = round(((current - hist['Close'].iloc[-63]) / hist['Close'].iloc[-63]) * 100, 1)
            if len(hist) >= 126:
                analysis['change_6m'] = round(((current - hist['Close'].iloc[-126]) / hist['Close'].iloc[-126]) * 100, 1)
            if len(hist) >= 252:
                analysis['change_1y'] = round(((current - hist['Close'].iloc[-252]) / hist['Close'].iloc[-252]) * 100, 1)
        
        # Dividend history
        analysis['dividend_history'] = []
        if len(divs) > 0:
            for date, amount in list(divs.tail(10).items()):
                analysis['dividend_history'].append({
                    'date': date.strftime('%Y-%m-%d'),
                    'amount': round(float(amount), 4)
                })
        
        # Generate summary
        div_yield = analysis.get('dividend_yield', 0)
        if div_yield and div_yield < 1:
            div_yield = div_yield * 100
        
        payout = analysis.get('payout_ratio', 0)
        pe = analysis.get('pe_ratio')
        change_6m = analysis.get('change_6m', 0)
        
        summary_parts = []
        summary_parts.append(f"📊 {analysis['name']} ({ticker})")
        summary_parts.append(f"\n\n💰 DIVIDENDO")
        summary_parts.append(f"• Yield: {div_yield:.1f}%")
        summary_parts.append(f"• Payout ratio: {payout:.0f}%" + (" ✅ Sostenible" if payout <= 100 else " ⚠️ Alto"))
        
        if analysis['dividend_history']:
            summary_parts.append(f"\n\n📈 EVOLUCIÓN DIVIDENDO")
            for d in analysis['dividend_history'][-4:]:
                summary_parts.append(f"• {d['date']}: {analysis.get('currency', '€')} {d['amount']:.4f}")
        
        summary_parts.append(f"\n\n📊 VALORACIÓN")
        if pe:
            summary_parts.append(f"• P/E: {pe:.1f}x" + (" (Barato)" if pe < 12 else " (Caro)" if pe > 20 else ""))
        
        summary_parts.append(f"\n\n🚀 MOMENTUM")
        summary_parts.append(f"• 6 meses: {'+' if change_6m > 0 else ''}{change_6m:.1f}%")
        
        analysis['summary'] = '\n'.join(summary_parts)
        
        # Cache the analysis
        save_analysis(ticker, analysis)
        
        return analysis
        
    except Exception as e:
        return {'error': str(e), 'ticker': ticker}


@app.route('/api/stock/<ticker>/full')
def api_stock_full(ticker):
    """Get full stock analysis (cached or fresh)"""
    # First get basic stock data from our list
    stocks = get_all_stocks()
    stock_data = None
    for s in stocks:
        if s['ticker'] == ticker:
            stock_data = s
            break
    
    if not stock_data:
        return jsonify({'error': 'Stock not found'}), 404
    
    # Check cache
    cached = get_cached_analysis(ticker)
    if cached:
        # Check if cache is fresh (less than 24 hours old)
        try:
            cached_time = datetime.fromisoformat(cached.get('analyzed_at', '2000-01-01'))
            if (datetime.now() - cached_time).total_seconds() < 86400:  # 24 hours
                return jsonify({
                    'stock': stock_data,
                    'analysis': cached,
                    'cached': True
                })
        except:
            pass
    
    # Generate fresh analysis
    analysis = generate_analysis(ticker)
    
    return jsonify({
        'stock': stock_data,
        'analysis': analysis,
        'cached': False
    })


@app.route('/api/markets')
def api_markets():
    """Get market breakdown"""
    stocks = get_all_stocks()
    
    markets = {}
    for s in stocks:
        m = s.get('ocean_market', 'Unknown')
        if m not in markets:
            markets[m] = {'market': m, 'count': 0, 'total_yield': 0}
        markets[m]['count'] += 1
        markets[m]['total_yield'] += s.get('dividend_yield', 0)
    
    result = []
    for m, data in markets.items():
        result.append({
            'market': m,
            'count': data['count'],
            'avg_yield': round(data['total_yield'] / data['count'], 2) if data['count'] > 0 else 0
        })
    
    result.sort(key=lambda x: x['count'], reverse=True)
    return jsonify(result)


@app.route('/api/top/<int:n>')
def api_top(n):
    """Get top N stocks by yield"""
    stocks = get_all_stocks()
    stocks.sort(key=lambda x: x.get('dividend_yield', 0), reverse=True)
    return jsonify(stocks[:n])


@app.route('/api/calendar')
def api_calendar():
    """Get upcoming dividend calendar from database"""
    import sqlite3
    
    days = request.args.get('days', 30, type=int)
    min_yield = request.args.get('min_yield', 0, type=float)
    
    db_path = DATA_PATH / 'dividend_seeker.db'
    if not db_path.exists():
        return jsonify({'error': 'Database not found'}), 500
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            d.ticker,
            s.name,
            d.ex_date,
            d.pay_date,
            d.amount,
            d.currency,
            d.dividend_type,
            d.status,
            d.fiscal_year,
            sn.price,
            sn.dividend_yield as annual_yield,
            CASE WHEN sn.price > 0 THEN ROUND((d.amount / sn.price) * 100, 2) ELSE 0 END as payment_yield,
            CAST(julianday(d.ex_date) - julianday('now') AS INTEGER) as days_until
        FROM dividends d
        JOIN stocks s ON d.ticker = s.ticker
        LEFT JOIN snapshots sn ON d.ticker = sn.ticker 
            AND sn.scan_date = (SELECT MAX(scan_date) FROM snapshots)
        WHERE d.ex_date >= date('now')
          AND d.ex_date <= date('now', '+' || ? || ' days')
        ORDER BY d.ex_date ASC
    """, (days,))
    
    results = []
    for row in cursor.fetchall():
        item = dict(row)
        # Filter by payment yield if specified
        if min_yield > 0 and (item.get('payment_yield') or 0) < min_yield:
            continue
        results.append(item)
    
    conn.close()
    
    return jsonify({
        'count': len(results),
        'days_range': days,
        'dividends': results
    })


@app.route('/api/calendar/urgent')
def api_calendar_urgent():
    """Get dividends with ex-date in next 3 days and payment yield > 3%"""
    import sqlite3
    
    days = request.args.get('days', 3, type=int)  # Default 3 días
    min_yield = request.args.get('min_yield', 3, type=float)
    
    db_path = DATA_PATH / 'dividend_seeker.db'
    if not db_path.exists():
        return jsonify({'error': 'Database not found'}), 500
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            d.ticker,
            s.name,
            d.ex_date,
            d.pay_date,
            d.amount,
            d.currency,
            d.dividend_type,
            d.status,
            sn.price,
            CASE WHEN sn.price > 0 THEN ROUND((d.amount / sn.price) * 100, 2) ELSE 0 END as payment_yield,
            CAST(julianday(d.ex_date) - julianday('now') AS INTEGER) as days_until
        FROM dividends d
        JOIN stocks s ON d.ticker = s.ticker
        LEFT JOIN snapshots sn ON d.ticker = sn.ticker 
            AND sn.scan_date = (SELECT MAX(scan_date) FROM snapshots)
        WHERE d.ex_date >= date('now')
          AND d.ex_date <= date('now', '+' || ? || ' days')
          AND sn.price > 0
          AND (d.amount / sn.price) * 100 >= ?
        ORDER BY d.ex_date ASC, payment_yield DESC
    """, (days, min_yield))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({
        'count': len(results),
        'days_ahead': days,
        'min_yield': min_yield,
        'alert': f'🚨 Ex-dates próximos {days} días con yield >{min_yield}%',
        'dividends': results
    })


@app.route('/api/stock/<ticker>/health')
def api_stock_health(ticker):
    """Get dividend sustainability health check for a stock"""
    import sqlite3
    
    db_path = DATA_PATH / 'dividend_seeker.db'
    if not db_path.exists():
        return jsonify({'error': 'Database not found'}), 500
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get latest snapshot data
    cursor.execute("""
        SELECT s.ticker, s.name, s.sector,
               sn.price, sn.dividend_yield, sn.payout_ratio, sn.pe_ratio,
               sn.dividend_score, sn.capital_score
        FROM stocks s
        LEFT JOIN snapshots sn ON s.ticker = sn.ticker
            AND sn.scan_date = (SELECT MAX(scan_date) FROM snapshots)
        WHERE s.ticker = ?
    """, (ticker,))
    
    stock_row = cursor.fetchone()
    if not stock_row:
        conn.close()
        return jsonify({'error': 'Stock not found'}), 404
    
    stock = dict(stock_row)
    
    # Get fundamentals if available
    cursor.execute("""
        SELECT * FROM fundamentals 
        WHERE ticker = ? 
        ORDER BY report_date DESC LIMIT 1
    """, (ticker,))
    
    fund_row = cursor.fetchone()
    fundamentals = dict(fund_row) if fund_row else None
    
    # Calculate health score and risk level
    alerts = []
    risk_score = 0  # 0 = healthy, higher = more risky
    
    payout = stock.get('payout_ratio') or 0
    div_yield = stock.get('dividend_yield') or 0
    
    # Payout ratio checks
    if payout > 100:
        alerts.append('🚨 Payout ratio >100% - pagando más de lo que ganan')
        risk_score += 3
    elif payout > 80:
        alerts.append('⚠️ Payout ratio alto (>80%)')
        risk_score += 1
    
    # Yield too high can be a trap
    if div_yield > 10:
        alerts.append('⚠️ Yield muy alto (>10%) - posible trampa de dividendo')
        risk_score += 2
    
    # Check fundamentals if available
    if fundamentals:
        eps_growth = fundamentals.get('eps_growth_yoy')
        if eps_growth is not None and eps_growth < -10:
            alerts.append(f'🚨 EPS cayendo {eps_growth:.1f}% YoY')
            risk_score += 2
        
        fcf = fundamentals.get('fcf')
        if fcf is not None and fcf < 0:
            alerts.append('🚨 Free Cash Flow negativo')
            risk_score += 3
        
        coverage = fundamentals.get('dividend_coverage')
        if coverage is not None and coverage < 1:
            alerts.append(f'🚨 Cobertura dividendo insuficiente ({coverage:.2f}x)')
            risk_score += 2
        
        impairments = fundamentals.get('impairments')
        if impairments is not None and impairments > 0:
            alerts.append(f'⚠️ Impairments/deterioros: ${impairments/1e9:.1f}B')
            risk_score += 1
    
    # Determine risk level
    if risk_score == 0:
        risk_level = 'low'
        risk_emoji = '🟢'
        risk_label = 'Sostenible'
    elif risk_score <= 2:
        risk_level = 'medium'
        risk_emoji = '🟡'
        risk_label = 'Vigilar'
    else:
        risk_level = 'high'
        risk_emoji = '🔴'
        risk_label = 'Riesgo'
    
    # Calculate sustainability score (1-5)
    sustainability_score = max(1, 5 - risk_score)
    
    conn.close()
    
    return jsonify({
        'ticker': ticker,
        'name': stock.get('name'),
        'sector': stock.get('sector'),
        'health': {
            'risk_level': risk_level,
            'risk_emoji': risk_emoji,
            'risk_label': risk_label,
            'sustainability_score': sustainability_score,
            'alerts': alerts,
            'risk_score_raw': risk_score
        },
        'metrics': {
            'dividend_yield': div_yield,
            'payout_ratio': payout,
            'pe_ratio': stock.get('pe_ratio'),
            'dividend_score': stock.get('dividend_score'),
            'capital_score': stock.get('capital_score')
        },
        'fundamentals': fundamentals
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    print(f"🚀 Dividend Seeker Dashboard")
    print(f"   http://localhost:{port}")
    app.run(debug=debug, host='0.0.0.0', port=port)
