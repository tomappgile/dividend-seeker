#!/usr/bin/env python3
"""
Dividend Seeker - Smart Scan
Only reports:
1. NEW stocks crossing the 5% threshold
2. Stocks with yield increase > 0.5%
3. URGENT alerts for stocks > 6.5%
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
DB_PATH = Path(__file__).parent.parent / "data" / "dividend_seeker.db"
DATA_DIR = Path(__file__).parent.parent / "data"
MIN_YIELD = 5.0
URGENT_YIELD = 6.5
YIELD_CHANGE_THRESHOLD = 0.5  # +0.5% change triggers notification

def get_db():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)

def get_previous_yields() -> dict:
    """Get the most recent yield for each stock."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticker, dividend_yield, scan_date
        FROM snapshots s1
        WHERE scan_date = (
            SELECT MAX(scan_date) FROM snapshots s2 WHERE s2.ticker = s1.ticker
        )
    """)
    result = {row[0]: {'yield': row[1], 'date': row[2]} for row in cursor.fetchall()}
    conn.close()
    return result

def get_already_notified() -> set:
    """Get tickers that were already notified as 'new'."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM first_qualified WHERE notified_at IS NOT NULL")
    result = {row[0] for row in cursor.fetchall()}
    conn.close()
    return result

def get_recent_notifications(days: int = 7) -> dict:
    """Get recent yield increase notifications to avoid spam."""
    conn = get_db()
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor.execute("""
        SELECT ticker, MAX(notified_at) 
        FROM yield_notifications 
        WHERE notified_at > ?
        GROUP BY ticker
    """, (cutoff,))
    result = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return result

def mark_as_notified(ticker: str, old_yield: float, new_yield: float, 
                     notification_type: str):
    """Record that we notified about this stock."""
    conn = get_db()
    cursor = conn.cursor()
    
    change_pct = new_yield - old_yield
    
    # Insert notification record
    cursor.execute("""
        INSERT INTO yield_notifications (ticker, old_yield, new_yield, change_pct, notification_type)
        VALUES (?, ?, ?, ?, ?)
    """, (ticker, old_yield, new_yield, change_pct, notification_type))
    
    # If new, also record in first_qualified
    if notification_type == 'new':
        cursor.execute("""
            INSERT OR REPLACE INTO first_qualified (ticker, first_yield, first_date, notified_at)
            VALUES (?, ?, ?, ?)
        """, (ticker, new_yield, datetime.now().strftime('%Y-%m-%d'), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

def analyze_candidates(current_candidates: list[dict]) -> dict:
    """
    Analyze candidates and categorize them:
    - new: First time crossing 5% threshold
    - increase: Yield increased by >0.5%
    - urgent: Yield > 6.5% (regardless of being new or not)
    
    Returns dict with 'new', 'increase', 'urgent' lists
    """
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
        
        # Check if urgent (>6.5%) - always include if not recently notified
        is_urgent = current_yield >= URGENT_YIELD
        
        # Check previous data
        prev_data = previous_yields.get(ticker)
        
        if prev_data is None or ticker not in already_notified:
            # NEW: Never seen before with yield > 5%
            if ticker not in already_notified:
                candidate['_notification_type'] = 'new'
                candidate['_prev_yield'] = None
                results['new'].append(candidate)
                
                if is_urgent:
                    results['urgent'].append(candidate)
                continue
        
        # Check yield change
        prev_yield = prev_data['yield'] if prev_data else 0
        yield_change = current_yield - prev_yield
        
        # INCREASE: Yield went up by >0.5%
        if yield_change >= YIELD_CHANGE_THRESHOLD:
            # Don't notify if we notified about this stock in last 7 days
            if ticker not in recent_notifications:
                candidate['_notification_type'] = 'increase'
                candidate['_prev_yield'] = prev_yield
                candidate['_yield_change'] = yield_change
                results['increase'].append(candidate)
        
        # URGENT: >6.5% - only notify if:
        # 1. Not recently notified (within 7 days), OR
        # 2. Yield increased by >0.5% since last notification
        if is_urgent and candidate not in results['new']:
            should_notify_urgent = False
            
            if ticker not in recent_notifications:
                # Never notified as urgent, or more than 7 days ago
                should_notify_urgent = True
            elif yield_change >= YIELD_CHANGE_THRESHOLD:
                # Already notified, but yield went UP significantly
                should_notify_urgent = True
                candidate['_yield_change'] = yield_change
            
            if should_notify_urgent:
                candidate['_notification_type'] = 'urgent'
                candidate['_prev_yield'] = prev_yield
                if candidate not in results['urgent']:
                    results['urgent'].append(candidate)
    
    return results

def format_telegram_message(analysis: dict) -> str:
    """Format the analysis results for Telegram."""
    lines = []
    now = datetime.now().strftime('%d %b %Y')
    
    total_alerts = len(analysis['new']) + len(analysis['increase']) + len(analysis['urgent'])
    
    if total_alerts == 0:
        return ""  # Nothing to report
    
    lines.append(f"🔔 <b>Dividend Seeker - {now}</b>\n")
    
    # Urgent alerts (>6.5%)
    if analysis['urgent']:
        lines.append("🚨 <b>URGENTE (Yield > 6.5%)</b>")
        for c in analysis['urgent'][:5]:
            emoji = "⚠️" if not c.get('sustainable', True) else "🔥"
            lines.append(f"  {emoji} <b>{c['ticker']}</b> | {c['dividend_yield']:.1f}% | {c['sector'][:15]}")
        lines.append("")
    
    # New stocks crossing 5%
    if analysis['new']:
        lines.append("🆕 <b>Nuevos candidatos (>5%)</b>")
        for c in analysis['new'][:5]:
            if c in analysis['urgent']:
                continue  # Already shown above
            emoji = "✅" if c.get('sustainable', True) else "⚠️"
            lines.append(f"  {emoji} <b>{c['ticker']}</b> | {c['dividend_yield']:.1f}% | {c['sector'][:15]}")
        lines.append("")
    
    # Yield increases
    if analysis['increase']:
        lines.append("📈 <b>Subidas de yield (+0.5%)</b>")
        for c in analysis['increase'][:5]:
            change = c.get('_yield_change', 0)
            prev = c.get('_prev_yield', 0)
            lines.append(f"  📊 <b>{c['ticker']}</b> | {prev:.1f}% → {c['dividend_yield']:.1f}% (+{change:.1f}%)")
        lines.append("")
    
    # Summary
    lines.append(f"📊 <i>Total alertas: {total_alerts}</i>")
    
    return "\n".join(lines)

def save_analysis(analysis: dict):
    """Save analysis results to JSON."""
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
    """Main entry point - analyze top_picks.json."""
    # Load current candidates from the regular scan
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
    
    # Analyze for new/changes/urgent
    analysis = analyze_candidates(candidates)
    
    print(f"\n📈 Results:")
    print(f"   🆕 New: {len(analysis['new'])}")
    print(f"   📈 Increases: {len(analysis['increase'])}")
    print(f"   🚨 Urgent: {len(analysis['urgent'])}")
    
    # Save analysis
    save_analysis(analysis)
    
    # Format message
    message = format_telegram_message(analysis)
    
    if message:
        print(f"\n📨 Telegram message:\n{message}")
        
        # Mark all as notified
        for c in analysis['new']:
            mark_as_notified(c['ticker'], 0, c['dividend_yield'], 'new')
        for c in analysis['increase']:
            mark_as_notified(c['ticker'], c.get('_prev_yield', 0), c['dividend_yield'], 'increase')
        for c in analysis['urgent']:
            # Only mark if not already marked as new (avoid duplicates)
            if c not in analysis['new']:
                mark_as_notified(c['ticker'], c.get('_prev_yield', 0), c['dividend_yield'], 'urgent')
        
        # Save message for nightly_scan.sh to send
        msg_file = DATA_DIR / "candidates" / "telegram_message.txt"
        with open(msg_file, 'w') as f:
            f.write(message)
        print(f"💾 Message saved to {msg_file}")
    else:
        print("\n✅ No new alerts to send")

if __name__ == "__main__":
    main()
