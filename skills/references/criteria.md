# Screening Criteria Reference

## Primary Filters

### 1. Dividend Yield (≥ 5%)

```
Dividend Yield = (Annual Dividend / Current Price) × 100
```

- Yahoo Finance provides this directly as `dividendYield`
- Already expressed as percentage (5.77 = 5.77%)
- Threshold: 5% minimum

### 2. Payout Ratio (≤ 100%)

```
Payout Ratio = (Total Dividends Paid / Net Income) × 100
```

- Measures dividend sustainability
- **< 60%**: Very sustainable, room to grow
- **60-80%**: Sustainable for mature companies
- **80-100%**: Sustainable but tight
- **> 100%**: ⚠️ Paying more than earnings (unsustainable)

## Secondary Indicators

### Undervaluation Score

Look for stocks trading below recent highs:

```
Discount = ((52w High - Current Price) / 52w High) × 100
```

Signals:
- **> 20% discount**: Potentially undervalued
- **> 30% discount**: Investigate fundamentals
- **> 50% discount**: Likely fundamental issues

### Dividend History

Prefer companies with:
- 5+ years consecutive dividends
- Growing or stable dividend rate
- No recent dividend cuts

### Sector Stability

Rank by long-term stability:

| Tier | Sectors |
|------|---------|
| S | Utilities, Consumer Staples, Healthcare |
| A | Energy, Financials, Industrials |
| B | Materials, Real Estate |
| C | Consumer Discretionary, Communication |
| D | Technology (low dividend culture) |

## Composite Score (Future)

Planned weighted scoring:

| Factor | Weight |
|--------|--------|
| Dividend Yield | 30% |
| Undervaluation | 25% |
| Sustainability | 25% |
| Dividend Growth | 10% |
| Sector Bonus | 10% |

## Red Flags

Automatically flag or exclude:
- Payout ratio > 150%
- Negative earnings (trailing 12M)
- Recent dividend cut
- Penny stocks (price < $1)
- Low liquidity (volume < 10K daily)

## Investment Strategy

### Long-term (default)
- Hold for dividend income
- Target 6%+ annual yield
- Reinvest dividends (DRIP)

### Opportunistic
- If stock rises > 20% quickly, consider capturing gains
- Rotate to another undervalued dividend payer
- Never pure trading — always have dividend backstop
