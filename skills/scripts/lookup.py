#!/usr/bin/env python3
"""
Quick dividend lookup for a single stock.
Usage: python lookup.py TICKER [TICKER2] ...
"""

import sys
import json
import yfinance as yf

def lookup(ticker: str) -> dict:
    """Get dividend info for a single ticker."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        dividend_yield = info.get("dividendYield", 0) or 0
        dividend_rate = info.get("dividendRate", 0) or 0
        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        payout_ratio = (info.get("payoutRatio", 0) or 0) * 100
        pe_ratio = info.get("trailingPE", 0) or 0
        market_cap = info.get("marketCap", 0) or 0
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", 0) or 0
        
        discount = 0
        if fifty_two_week_high > 0 and current_price > 0:
            discount = ((fifty_two_week_high - current_price) / fifty_two_week_high) * 100
        
        ex_div = info.get("exDividendDate")
        if ex_div:
            from datetime import datetime
            ex_div = datetime.fromtimestamp(ex_div).strftime("%Y-%m-%d")
        
        return {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName", ticker),
            "sector": info.get("sector", "Unknown"),
            "price": round(current_price, 2),
            "currency": info.get("currency", "USD"),
            "dividend_yield": round(dividend_yield, 2),
            "dividend_rate": round(dividend_rate, 2),
            "payout_ratio": round(payout_ratio, 1),
            "pe_ratio": round(pe_ratio, 2) if pe_ratio else None,
            "market_cap_b": round(market_cap / 1e9, 2) if market_cap else 0,
            "52w_high": round(fifty_two_week_high, 2),
            "discount_from_high": round(discount, 1),
            "ex_dividend_date": ex_div,
            "sustainable": payout_ratio <= 100
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def main():
    if len(sys.argv) < 2:
        print("Usage: python lookup.py TICKER [TICKER2] ...")
        sys.exit(1)
    
    tickers = sys.argv[1:]
    results = []
    
    for ticker in tickers:
        print(f"🔍 Looking up {ticker}...", file=sys.stderr)
        result = lookup(ticker.upper())
        results.append(result)
        
        if "error" in result:
            print(f"❌ {ticker}: {result['error']}")
        else:
            print(f"\n{'='*50}")
            print(f"📊 {result['ticker']} - {result['name']}")
            print(f"{'='*50}")
            print(f"Sector:          {result['sector']}")
            print(f"Price:           {result['currency']} {result['price']}")
            print(f"Dividend Yield:  {result['dividend_yield']}%")
            print(f"Dividend Rate:   {result['currency']} {result['dividend_rate']}/share")
            print(f"Payout Ratio:    {result['payout_ratio']}% {'✅' if result['sustainable'] else '⚠️'}")
            print(f"P/E Ratio:       {result['pe_ratio'] or 'N/A'}")
            print(f"Market Cap:      ${result['market_cap_b']}B")
            print(f"52W High:        {result['currency']} {result['52w_high']}")
            print(f"Discount:        {result['discount_from_high']}%")
            print(f"Ex-Dividend:     {result['ex_dividend_date'] or 'N/A'}")
    
    if len(results) > 1:
        print(f"\n📋 JSON Output:")
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
