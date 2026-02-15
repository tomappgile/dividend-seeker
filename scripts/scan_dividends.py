#!/usr/bin/env python3
"""
Dividend Seeker - Stock Scanner
Scans markets for stocks with dividend yield > 5%
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
MIN_YIELD = 5.0  # Minimum dividend yield %
MAX_PAYOUT_RATIO = 100  # Maximum payout ratio %
DATA_DIR = Path(__file__).parent.parent / "data"


def load_market_tickers(market: str) -> list[str]:
    """Load ticker list for a market."""
    market_file = DATA_DIR / "markets" / f"{market}.json"
    if not market_file.exists():
        print(f"⚠️  Market file not found: {market_file}")
        return []
    
    with open(market_file) as f:
        data = json.load(f)
    return data.get("tickers", [])


def get_stock_data(ticker: str) -> dict | None:
    """Fetch dividend and price data for a stock."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Get key metrics
        # Note: yfinance returns dividendYield already as percentage (e.g., 5.77 = 5.77%)
        dividend_yield_pct = info.get("dividendYield", 0) or 0
        
        # Skip if no dividend or below threshold
        if dividend_yield_pct < MIN_YIELD:
            return None
        
        # Get additional data
        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        dividend_rate = info.get("dividendRate", 0) or 0
        payout_ratio = (info.get("payoutRatio", 0) or 0) * 100
        market_cap = info.get("marketCap", 0) or 0
        pe_ratio = info.get("trailingPE", 0) or 0
        sector = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")
        name = info.get("shortName") or info.get("longName", ticker)
        currency = info.get("currency", "USD")
        
        # 52-week data
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", 0) or 0
        fifty_two_week_low = info.get("fiftyTwoWeekLow", 0) or 0
        
        # Calculate discount from 52-week high
        discount_from_high = 0
        if fifty_two_week_high > 0 and current_price > 0:
            discount_from_high = ((fifty_two_week_high - current_price) / fifty_two_week_high) * 100
        
        # Ex-dividend date
        ex_div_date = info.get("exDividendDate")
        if ex_div_date:
            ex_div_date = datetime.fromtimestamp(ex_div_date).strftime("%Y-%m-%d")
        
        return {
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "industry": industry,
            "currency": currency,
            "price": round(current_price, 2),
            "dividend_yield": round(dividend_yield_pct, 2),
            "dividend_rate": round(dividend_rate, 2),
            "payout_ratio": round(payout_ratio, 2),
            "pe_ratio": round(pe_ratio, 2) if pe_ratio else None,
            "market_cap": market_cap,
            "market_cap_b": round(market_cap / 1e9, 2) if market_cap else 0,
            "52w_high": round(fifty_two_week_high, 2),
            "52w_low": round(fifty_two_week_low, 2),
            "discount_from_high": round(discount_from_high, 2),
            "ex_dividend_date": ex_div_date,
            "sustainable": payout_ratio <= MAX_PAYOUT_RATIO,
            "scanned_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error fetching {ticker}: {e}")
        return None


def scan_market(market: str, max_workers: int = 5) -> list[dict]:
    """Scan all tickers in a market for dividend opportunities."""
    tickers = load_market_tickers(market)
    if not tickers:
        return []
    
    print(f"\n📊 Scanning {market.upper()}: {len(tickers)} stocks...")
    
    candidates = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(get_stock_data, t): t for t in tickers}
        
        for i, future in enumerate(as_completed(futures), 1):
            ticker = futures[future]
            try:
                result = future.result()
                if result:
                    candidates.append(result)
                    print(f"  ✅ {ticker}: {result['dividend_yield']:.1f}% yield")
            except Exception as e:
                print(f"  ❌ {ticker}: {e}")
            
            # Progress
            if i % 50 == 0:
                print(f"  ... processed {i}/{len(tickers)}")
    
    return candidates


def save_results(candidates: list[dict], market: str):
    """Save scan results to JSON."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Daily results
    output_file = DATA_DIR / "dividends" / f"{today}_{market}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Sort by yield
    candidates.sort(key=lambda x: x["dividend_yield"], reverse=True)
    
    with open(output_file, "w") as f:
        json.dump({
            "market": market,
            "scanned_at": datetime.now().isoformat(),
            "min_yield": MIN_YIELD,
            "total_candidates": len(candidates),
            "candidates": candidates
        }, f, indent=2)
    
    print(f"\n💾 Saved {len(candidates)} candidates to {output_file}")
    return output_file


def print_summary(candidates: list[dict]):
    """Print a summary table of top candidates."""
    if not candidates:
        print("\n😕 No candidates found with yield > 5%")
        return
    
    print(f"\n{'='*80}")
    print(f"🏆 TOP DIVIDEND CANDIDATES (Yield > {MIN_YIELD}%)")
    print(f"{'='*80}")
    print(f"{'Ticker':<8} {'Name':<25} {'Yield':>7} {'Price':>10} {'Sector':<15} {'Sust.'}")
    print("-" * 80)
    
    for c in candidates[:20]:  # Top 20
        name = c['name'][:24] if len(c['name']) > 24 else c['name']
        sust = "✅" if c['sustainable'] else "⚠️"
        print(f"{c['ticker']:<8} {name:<25} {c['dividend_yield']:>6.1f}% {c['price']:>9.2f} {c['sector'][:14]:<15} {sust}")
    
    if len(candidates) > 20:
        print(f"\n... and {len(candidates) - 20} more candidates")


def main():
    """Main entry point."""
    # Markets to scan (can be passed as arguments)
    markets = sys.argv[1:] if len(sys.argv) > 1 else ["sp500"]
    
    all_candidates = []
    
    for market in markets:
        candidates = scan_market(market)
        if candidates:
            save_results(candidates, market)
            all_candidates.extend(candidates)
    
    # Combined summary
    if all_candidates:
        all_candidates.sort(key=lambda x: x["dividend_yield"], reverse=True)
        print_summary(all_candidates)
        
        # Save combined top picks
        top_picks_file = DATA_DIR / "candidates" / "top_picks.json"
        with open(top_picks_file, "w") as f:
            json.dump({
                "updated_at": datetime.now().isoformat(),
                "total": len(all_candidates),
                "top_20": all_candidates[:20]
            }, f, indent=2)
        print(f"\n🎯 Top picks saved to {top_picks_file}")


if __name__ == "__main__":
    main()
