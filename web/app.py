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
    """Get all stocks from all tiers"""
    data = load_candidates()
    all_stocks = (
        data.get('tier1_high_sustainable', []) +
        data.get('tier2_moderate_sustainable', []) +
        data.get('tier3_high_risk', [])
    )
    return all_stocks


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


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
    limit = request.args.get('limit', 100, type=int)
    
    stocks = get_all_stocks()
    
    # Filter
    filtered = []
    for s in stocks:
        if s.get('dividend_yield', 0) < min_yield:
            continue
        if market and market not in s.get('ocean_market', ''):
            continue
        if sustainable_only and not s.get('sustainable', True):
            continue
        filtered.append(s)
    
    # Sort by yield
    filtered.sort(key=lambda x: x.get('dividend_yield', 0), reverse=True)
    
    return jsonify(filtered[:limit])


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
