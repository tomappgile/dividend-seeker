# Markets Reference

## Supported Markets

| Market | Region | Index | Tickers | Focus |
|--------|--------|-------|---------|-------|
| `sp500` | 🇺🇸 USA | S&P 500 | ~154 | Large-cap dividend payers |
| `nasdaq100` | 🇺🇸 USA | NASDAQ 100 | ~30 | Tech with dividends |
| `eurostoxx50` | 🇪🇺 Europe | Euro Stoxx 50 | ~46 | European blue chips |
| `dax40` | 🇩🇪 Germany | DAX 40 | ~40 | German large-cap |
| `cac40` | 🇫🇷 France | CAC 40 | ~38 | French large-cap |
| `ftse_mib` | 🇮🇹 Italy | FTSE MIB | ~35 | Italian large-cap |
| `ibex35` | 🇪🇸 Spain | IBEX 35 | ~35 | Spanish large-cap |

## Market Files

Located in `data/markets/<market>.json`:

```json
{
  "name": "sp500",
  "description": "S&P 500 - US Large Cap",
  "updated_at": "2026-02-15T...",
  "count": 154,
  "tickers": ["AAPL", "ABBV", ...]
}
```

## Updating Market Lists

```bash
python scripts/fetch_market_lists.py
```

Sources:
- Wikipedia (S&P 500, NASDAQ 100, Euro Stoxx 50)
- Hardcoded fallbacks for smaller markets

## Currency Notes

| Market | Currency |
|--------|----------|
| US markets | USD |
| German (DAX) | EUR |
| French (CAC) | EUR |
| Italian (MIB) | EUR |
| Spanish (IBEX) | EUR |

Yahoo Finance returns dividends in native currency.
