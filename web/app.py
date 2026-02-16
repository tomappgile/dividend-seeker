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

app = Flask(__name__, static_folder='static')
CORS(app)

# Handle paths for both local and Railway deployment
BASE_DIR = Path(__file__).parent.parent
DATA_PATH = BASE_DIR / 'data'


def load_candidates():
    """Load candidates from JSON file"""
    main_list = DATA_PATH / 'candidates' / 'MAIN_LIST.json'
    if main_list.exists():
        with open(main_list) as f:
            return json.load(f)
    return {'tier1_high_sustainable': [], 'tier2_moderate_sustainable': [], 'tier3_high_risk': []}


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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    print(f"🚀 Dividend Seeker Dashboard")
    print(f"   http://localhost:{port}")
    app.run(debug=debug, host='0.0.0.0', port=port)
