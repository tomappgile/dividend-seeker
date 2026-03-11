#!/usr/bin/env python3
"""
Dividend Seeker - Smart Scan
Only reports:
1. NEW stocks crossing the 5% threshold
2. Stocks with yield increase > 0.5%
3. URGENT alerts for stocks > 6.5%

Column naming convention (Hungarian notation):
- i = INTEGER, s = TEXT, r = REAL, b = BOOLEAN, d = DATE, t = TIMESTAMP
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "dividend_seeker.db"
DATA_DIR = Path(__file__).parent.parent / "data"
MIN_YIELD = 5.0
URGENT_YIELD = 6.5
YIELD_CHANGE_THRESHOLD = 0.5

def get_db():
    return sqlite3.connect(DB_PATH)

def get_previous_yields() -> dict:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sticker, rdividend_yield, dscan_date
        FROM snapshots s1
        WHERE dscan_date = (
            SELECT MAX(dscan_date) FROM snapshots s2 WHERE s2.sticker = s1.sticker
        )
    """)
    result = {row[0]: {'yield': row[1], 'date': row[2]} for row in cursor.fetchall()}
    conn.close()
    return result

def get_already_notified() -> set:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT sticker FROM first_qualified WHERE tnotified_at IS NOT NULL")
    result = {row[0] for row in cursor.fetchall()}
    conn.close()
    return result

def get_recent_notifications(days: int = 7) -> dict:
    conn = get_db()
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor.execute("""
        SELECT sticker, MAX(tnotified_at) 
        FROM yield_notifications 
        WHERE tnotified_at > ?
        GROUP BY sticker
    """, (cutoff,))
    result = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return result

def mark_as_notified(ticker: str, old_yield: float, new_yield: float, 
                     notification_type: str):
    conn = get_db()
    cursor = conn.cursor()
    
    change_pct = new_yield - old_yield
    
    cursor.execute("""
        INSERT INTO yield_notifications (sticker, rold_yield, rnew_yield, rchange_pct, snotification_type)
        VALUES (?, ?, ?, ?, ?)
    """, (ticker, old_yield, new_yield, change_pct, notification_type))
    
    if notification_type == 'new':
        cursor.execute("""
            INSERT OR REPLACE INTO first_qualified (sticker, rfirst_yield, dfirst_date, tnotified_at)
            VALUES (?, ?, ?, ?)
        """, (ticker, new_yield, datetime.now().strftime('%Y-%m-%d'), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

def analyze_candidates(current_candidates: list[dict]) -> dict:
    previous_yields = get_previous_yields()
    already_notified = get_already_notified()
    recent_notifications = get_recent_notifications(days=7)
    
    results = {
        'new': [],
        'increase': [],
        'urgent': []
    }
    
    for candidate in current_candidates:
        ticker = candidate['ticker']
        current_yield = candidate['dividend_yield']
        
        is_urgent = current_yield >= URGENT_YIELD
        
        prev_data = previous_yields.get(ticker)
        
        if prev_data is None or ticker not in already_notified:
            if ticker not in already_notified:
                candidate['_notification_type'] = 'new'
                candidate['_prev_yield'] = None
                results['new'].append(candidate)
                
                if is_urgent:
                    results['urgent'].append(candidate)
                continue
        
        prev_yield = prev_data['yield'] if prev_data else 0
        yield_change = current_yield - prev_yield
        
        if yield_change >= YIELD_CHANGE_THRESHOLD:
            if ticker not in recent_notifications:
                candidate['_notification_type'] = 'increase'
                candidate['_prev_yield'] = prev_yield
                candidate['_yield_change'] = yield_change
                results['increase'].append(candidate)
        
        if is_urgent and candidate not in results['new']:
            should_notify_urgent = False
            
            if ticker not in recent_notifications:
                should_notify_urgent = True
            elif yield_change >= YIELD_CHANGE_THRESHOLD:
                should_notify_urgent = True
                candidate['_yield_change'] = yield_change
            
            if should_notify_urgent:
                candidate['_notification_type'] = 'urgent'
                candidate['_prev_yield'] = prev_yield
                if candidate not in results['urgent']:
                    results['urgent'].append(candidate)
    
    return results

def format_telegram_message(analysis: dict) -> str:
    lines = []
    now = datetime.now().strftime('%d %b %Y')
    
    total_alerts = len(analysis['new']) + len(analysis['increase']) + len(analysis['urgent'])
    
    if total_alerts == 0:
        return ""
    
    lines.append(f"🔔 <b>Dividend Seeker - {now}</b>\n")
    
    if analysis['urgent']:
        lines.append("🚨 <b>URGENTE (Yield > 6.5%)</b>")
        for c in analysis['urgent'][:5]:
            emoji = "⚠️" if not c.get('sustainable', True) else "🔥"
            lines.append(f"  {emoji} <b>{c['ticker']}</b> | {c['dividend_yield']:.1f}% | {c['sector'][:15]}")
        lines.append("")
    
    if analysis['new']:
        lines.append("🆕 <b>Nuevos candidatos (>5%)</b>")
        for c in analysis['new'][:5]:
            if c in analysis['urgent']:
                continue
            emoji = "✅" if c.get('sustainable', True) else "⚠️"
            lines.append(f"  {emoji} <b>{c['ticker']}</b> | {c['dividend_yield']:.1f}% | {c['sector'][:15]}")
        lines.append("")
    
    if analysis['increase']:
        lines.append("📈 <b>Subidas de yield (+0.5%)</b>")
        for c in analysis['increase'][:5]:
            change = c.get('_yield_change', 0)
            prev = c.get('_prev_yield', 0)
            lines.append(f"  📊 <b>{c['ticker']}</b> | {prev:.1f}% → {c['dividend_yield']:.1f}% (+{change:.1f}%)")
        lines.append("")
    
    lines.append(f"📊 <i>Total alertas: {total_alerts}</i>")
    
    return "\n".join(lines)

def save_analysis(analysis: dict):
    output_file = DATA_DIR / "candidates" / "smart_analysis.json"
    with open(output_file, 'w') as f:
        json.dump({
            'analyzed_at': datetime.now().isoformat(),
            'summary': {
                'new_count': len(analysis['new']),
                'increase_count': len(analysis['increase']),
                'urgent_count': len(analysis['urgent'])
            },
            'new': analysis['new'],
            'increase': analysis['increase'],
            'urgent': analysis['urgent']
        }, f, indent=2, default=str)
    print(f"💾 Analysis saved to {output_file}")

def main():
    top_picks_file = DATA_DIR / "candidates" / "top_picks.json"
    
    if not top_picks_file.exists():
        print("❌ No top_picks.json found. Run scan_dividends.py first.")
        return
    
    with open(top_picks_file) as f:
        data = json.load(f)
    
    candidates = data.get('top_20', [])
    if not candidates:
        print("📭 No candidates in top_picks.json")
        return
    
    print(f"📊 Analyzing {len(candidates)} candidates...")
    
    analysis = analyze_candidates(candidates)
    
    print(f"\n📈 Results:")
    print(f"   🆕 New: {len(analysis['new'])}")
    print(f"   📈 Increases: {len(analysis['increase'])}")
    print(f"   🚨 Urgent: {len(analysis['urgent'])}")
    
    save_analysis(analysis)
    
    message = format_telegram_message(analysis)
    
    if message:
        print(f"\n📨 Telegram message:\n{message}")
        
        for c in analysis['new']:
            mark_as_notified(c['ticker'], 0, c['dividend_yield'], 'new')
        for c in analysis['increase']:
            mark_as_notified(c['ticker'], c.get('_prev_yield', 0), c['dividend_yield'], 'increase')
        for c in analysis['urgent']:
            if c not in analysis['new']:
                mark_as_notified(c['ticker'], c.get('_prev_yield', 0), c['dividend_yield'], 'urgent')
        
        msg_file = DATA_DIR / "candidates" / "telegram_message.txt"
        with open(msg_file, 'w') as f:
            f.write(message)
        print(f"💾 Message saved to {msg_file}")
    else:
        print("\n✅ No new alerts to send")

if __name__ == "__main__":
    main()
