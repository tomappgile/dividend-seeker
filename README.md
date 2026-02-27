# 📈 Dividend Seeker

AI-powered dividend stock screener to find undervalued stocks with optimal, sustainable dividends.

## 🎯 Objective

Instead of manually researching individual stocks, Dividend Seeker **proactively suggests** stocks that meet specific dividend criteria:

- **Dividend yield > 5%** on current price
- **Sustainable payout** (reasonable payout ratio vs earnings)
- **Undervalued** — recent price decline (1-2 years)
- **Solid fundamentals** — positive earnings trend
- **Strategic sustainability** — company with long-term viability

## 📊 Key Metrics

| Metric | Description | Source |
|--------|-------------|--------|
| Dividend per Share | Annual dividend payment | Yahoo Finance |
| Shares Outstanding | Total shares issued | Yahoo Finance |
| Net Income / EBITDA | Profitability | Yahoo Finance |
| Payout Ratio | Dividend ÷ Earnings | Calculated |
| Price Change (YTD, 1Y, 2Y) | Valuation trend | Yahoo Finance |
| Market Cap | Price × Shares | Calculated |
| Strategic Plan | Company outlook | News / Filings |

## 🌍 Target Markets

- 🇺🇸 S&P 500
- 🇺🇸 NASDAQ
- 🇪🇺 Eurostoxx
- 🇫🇷 CAC 40 (France)
- 🇮🇹 FTSE MIB (Milan)

## 🏭 Preferred Sectors

| Sector | Rationale |
|--------|-----------|
| 🍎 Food & Agriculture | Essential, evergreen demand |
| 💊 Pharmaceuticals | Healthcare always needed |
| ⚡ Energy | Infrastructure backbone |
| 🛡️ Defense | Geopolitical stability needs |

*Avoiding: Pure tech/AI hype stocks (high speculation, low dividends)*

## 💡 Investment Strategy

1. **Core: Long-term** — Hold and collect dividends (target 6%+ annual)
2. **Opportunistic:** If stock appreciates significantly (e.g., +25% quickly), capture gains and rotate to another opportunity
3. **Downside:** If price drops but fundamentals are solid, hold for dividends

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Data Sources   │────▶│   Data Pipeline  │────▶│   AI Screener   │
│  (Yahoo, etc.)  │     │   (ETL + Store)  │     │  (Analysis)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────┐
                                                 │  Recommendations │
                                                 │  (Bot / API)     │
                                                 └─────────────────┘
```

## 📅 Roadmap

See [GitHub Issues](https://github.com/tomappgile/dividend-seeker/issues) and Milestones for detailed planning.

## ⚠️ Disclaimer

This tool provides **information for educational purposes only** — not financial advice. Always do your own research and consider consulting a financial advisor before making investment decisions.

## 👥 Contributors

- Javier Corona
- Tomás Corral ([@Tomixter](https://github.com/tomappgile))

---

*Project inception: January 10, 2026*
# Force rebuild Fri Feb 27 19:18:07 CET 2026
