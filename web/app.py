#!/usr/bin/env python3
"""
Dividend Seeker - Web Dashboard
Flask API + Static Dashboard
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import sqlite3
import json
from pathlib import Path
from datetime import datetime

app = Flask(__name__, static_folder='static')
CORS(app)

import os

# Handle paths for both local and Railway deployment
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / 'data' / 'dividend_seeker.db'
DATA_PATH = BASE_DIR / 'data'

# Create data directory if it doesn't exist
DATA_PATH.mkdir(parents=True, exist_ok=True)


def init_db():
    """Initialize database if it doesn't exist"""
    if not DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT UNIQUE NOT NULL,
                name TEXT, sector TEXT, industry TEXT, currency TEXT, market TEXT,
                ocean_accessible BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL, scan_date DATE NOT NULL,
                price REAL, dividend_yield REAL, dividend_rate REAL,
                payout_ratio REAL, pe_ratio REAL, market_cap REAL,
                week_52_high REAL, week_52_low REAL, change_6m REAL,
                sustainable BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, scan_date)
            );
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date DATE NOT NULL, markets_scanned TEXT,
                total_scanned INTEGER, candidates_found INTEGER,
                duration_seconds REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()
        conn.close()


def get_db():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/stats')
def api_stats():
    """Dashboard stats"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE ocean_accessible = 1")
    total_stocks = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(dividend_yield), MAX(dividend_yield), MIN(dividend_yield) FROM snapshots WHERE scan_date = (SELECT MAX(scan_date) FROM snapshots)")
    row = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM snapshots WHERE dividend_yield >= 6 AND sustainable = 1 AND scan_date = (SELECT MAX(scan_date) FROM snapshots)")
    tier1_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT MAX(scan_date) FROM scans")
    last_scan = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_stocks': total_stocks,
        'avg_yield': round(row[0] or 0, 2),
        'max_yield': round(row[1] or 0, 2),
        'min_yield': round(row[2] or 0, 2),
        'tier1_count': tier1_count,
        'last_scan': last_scan
    })


@app.route('/api/stocks')
def api_stocks():
    """List all stocks with filters"""
    min_yield = request.args.get('min_yield', 5, type=float)
    market = request.args.get('market', None)
    sustainable_only = request.args.get('sustainable', 'false') == 'true'
    sort_by = request.args.get('sort', 'dividend_yield')
    limit = request.args.get('limit', 100, type=int)
    
    conn = get_db()
    cursor = conn.cursor()
    
    query = '''
        SELECT s.ticker, st.name, st.sector, st.market, st.currency,
               s.price, s.dividend_yield, s.payout_ratio, s.change_6m, s.sustainable
        FROM snapshots s
        JOIN stocks st ON s.ticker = st.ticker
        WHERE s.scan_date = (SELECT MAX(scan_date) FROM snapshots)
          AND s.dividend_yield >= ?
    '''
    params = [min_yield]
    
    if market:
        query += " AND st.market LIKE ?"
        params.append(f"%{market}%")
    
    if sustainable_only:
        query += " AND s.sustainable = 1"
    
    query += f" ORDER BY s.{sort_by} DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])


@app.route('/api/stock/<ticker>')
def api_stock_detail(ticker):
    """Get stock details"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Current data
    cursor.execute('''
        SELECT s.*, st.name, st.sector, st.market, st.currency
        FROM snapshots s
        JOIN stocks st ON s.ticker = st.ticker
        WHERE s.ticker = ?
        ORDER BY s.scan_date DESC
        LIMIT 1
    ''', (ticker,))
    current = dict(cursor.fetchone() or {})
    
    # History
    cursor.execute('''
        SELECT scan_date, price, dividend_yield
        FROM snapshots
        WHERE ticker = ?
        ORDER BY scan_date DESC
        LIMIT 30
    ''', (ticker,))
    history = [dict(row) for row in cursor.fetchall()]
    
    # Dividends
    cursor.execute('''
        SELECT ex_date, amount, currency
        FROM dividends
        WHERE ticker = ?
        ORDER BY ex_date DESC
        LIMIT 10
    ''', (ticker,))
    dividends = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'current': current,
        'history': history,
        'dividends': dividends
    })


@app.route('/api/markets')
def api_markets():
    """Get market breakdown"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT st.market, COUNT(*) as count, AVG(s.dividend_yield) as avg_yield
        FROM snapshots s
        JOIN stocks st ON s.ticker = st.ticker
        WHERE s.scan_date = (SELECT MAX(scan_date) FROM snapshots)
        GROUP BY st.market
        ORDER BY count DESC
    ''')
    markets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(markets)


@app.route('/api/top/<int:n>')
def api_top(n):
    """Get top N stocks by yield"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.ticker, st.name, st.market, s.dividend_yield, s.price, 
               s.change_6m, s.sustainable, st.sector
        FROM snapshots s
        JOIN stocks st ON s.ticker = st.ticker
        WHERE s.scan_date = (SELECT MAX(scan_date) FROM snapshots)
        ORDER BY s.dividend_yield DESC
        LIMIT ?
    ''', (n,))
    stocks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(stocks)


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    print(f"🚀 Dividend Seeker Dashboard")
    print(f"   http://localhost:{port}")
    app.run(debug=debug, host='0.0.0.0', port=port)
