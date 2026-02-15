---
name: dividend-scanner
description: Scan stock markets for high-dividend opportunities with yield above 5 percent. Use when searching for dividend stocks, running market scans, checking dividend yields, finding undervalued dividend payers, or scheduling automated dividend screening. Supports SP500, NASDAQ100, Eurostoxx50, DAX40, CAC40, FTSE MIB, IBEX35.
---

# Dividend Scanner

Scan multiple stock markets to find high-yield dividend opportunities using Yahoo Finance data.

## Quick Start

### Run a market scan
```bash
cd /Users/tomix/.openclaw/workspace-dividend-seeker/dividend-seeker
source venv/bin/activate
python scripts/scan_dividends.py <market>
```

Markets: `sp500`, `nasdaq100`, `eurostoxx50`, `dax40`, `cac40`, `ftse_mib`, `ibex35`

### Scan all markets
```bash
./scripts/nightly_scan.sh
```

## Output Files

| Path | Content |
|------|---------|
| `data/dividends/YYYY-MM-DD_<market>.json` | Daily scan results |
| `data/candidates/top_picks.json` | Combined top candidates |
| `data/markets/<market>.json` | Ticker lists |

## Screening Criteria

Default filters (configurable in script):
- **Minimum yield**: 5%
- **Maximum payout ratio**: 100%
- **Sustainability flag**: payout ≤ 100%

## Data Points Collected

For each qualifying stock:
- Ticker, name, sector, industry
- Current price, currency
- Dividend yield (%), dividend rate
- Payout ratio, P/E ratio
- Market cap
- 52-week high/low, discount from high
- Ex-dividend date
- Sustainability flag

## Interpreting Results

### Sustainability Flags
- ✅ **Sustainable**: Payout ratio ≤ 100%
- ⚠️ **Warning**: Payout > 100% (paying more than earnings)

### Discount from High
Higher discount = potentially undervalued. Look for:
- Discount > 20% with solid fundamentals
- Consistent dividend history

## Preferred Sectors

Focus on evergreen sectors:
- 🍎 Food/Agriculture
- 💊 Pharmaceuticals  
- ⚡ Energy
- 🛡️ Defense

Avoid pure tech/AI hype (low dividends, high volatility).

## References

- [markets.md](references/markets.md) - Market details and ticker counts
- [criteria.md](references/criteria.md) - Detailed screening methodology
