# Polymarket Wallet Report - Calculation Documentation

This document explains how all metrics are calculated in `src/run_468_report.py`.

## Data Sources (Polymarket APIs)

| Endpoint | Purpose |
|----------|---------|
| `/v1/leaderboard?timePeriod=all&user={wallet}` | Official total PnL, volume, rank |
| `/traded?user={wallet}` | Number of markets traded |
| `/trades?user={wallet}` | Individual trade history (buys/sells) |
| `/closed-positions?user={wallet}` | Closed positions with realized PnL |
| `/positions?user={wallet}` | Open positions with unrealized PnL |
| `/markets?slug={slug}` (Gamma API) | Market metadata for category tags |

---

## PnL Calculations

### Realized PnL (Total)
```python
realized_closed = sum(realizedPnl from closed-positions)
realized_open = sum(realizedPnl from open positions)  # Partial sells
realized_pnl = realized_closed + realized_open
```

**Why both?** Open positions can have `realizedPnl` if you've partially sold. For example:
- Buy 100 shares at $0.50
- Sell 50 shares at $0.70 → realized profit on those 50
- Still holding 50 shares → unrealized PnL on remaining

### Unrealized PnL
```python
unrealized_pnl = sum(cashPnl from open positions)
```
`cashPnl` = current market value - initial cost basis

### Total PnL (Calculated)
```python
calc_total_pnl = realized_pnl + unrealized_pnl
```

### Leaderboard PnL
```python
total_pnl = leaderboard[0].pnl  # Official Polymarket number
```

**Note:** `calc_total_pnl` should approximately equal `total_pnl`. Differences may occur due to:
- API pagination limits
- Timing differences
- Rounding

### Time-Period PnL (1D, 7D, 30D)
```python
realized_1d = sum(realizedPnl for p in closed if p.timestamp > now - 86400)
realized_7d = sum(realizedPnl for p in closed if p.timestamp > now - 604800)
realized_30d = sum(realizedPnl for p in closed if p.timestamp > now - 2592000)
```

**Unrealized for 1D/7D/30D:** Shown as "-" because unrealized PnL is a current snapshot, not historical. The API doesn't provide "what was unrealized 7 days ago."

---

## Stats Calculations

### Volume
```python
volume = leaderboard[0].vol  # Total USD traded (from Polymarket)
```

### ROI (Return on Investment)
```python
roi = (total_pnl / volume) * 100
```
Example: $35,000 profit on $500,000 volume = 7% ROI

### Win Rate
```python
wins = count(closed positions where realizedPnl > 0)
losses = count(closed positions where realizedPnl < 0)
win_rate = (wins / (wins + losses)) * 100
```

### Average Bet Size
```python
total_positions = len(closed) + len(open positions)
avg_bet_size = volume / total_positions
```

### Markets Traded
```python
markets_traded = traded.traded  # From /traded endpoint
```

### Total Trades
```python
total_trades = len(trades)  # From /trades endpoint (individual buy/sell orders)
```

---

## Price Tier Calculations

Positions are grouped by entry price (in cents):

| Tier | Entry Price Range |
|------|-------------------|
| 90-100c | $0.90 - $1.00 |
| 80-90c | $0.80 - $0.89 |
| 70-80c | $0.70 - $0.79 |
| ... | ... |
| 0-10c | $0.00 - $0.09 |

```python
entry_cents = int(avgPrice * 100)
tier = find_tier(entry_cents)

# Per tier:
positions = count of positions in tier
pct_of_total = (tier_positions / total_positions) * 100
win_rate = (tier_wins / (tier_wins + tier_losses)) * 100
total_pnl = sum(realizedPnl for positions in tier)
```

---

## Category Calculations

Categories are fetched from Gamma API market tags (Sports, Esports, Crypto, Politics, etc.)

```python
# Per category:
category_pnl = sum(realizedPnl for positions with this category)
category_volume = sum(totalBought * avgPrice for positions with this category)
pct_volume = (category_volume / total_volume) * 100
```

Categories are sorted by total PnL (highest first).

---

## Individual Trade Calculations

### Entry Amount (USD)
```python
usd_amount = avgPrice * totalBought
```
Where:
- `avgPrice` = average entry price per share
- `totalBought` = number of shares purchased

### ROI per Trade
```python
roi = (realizedPnl / usd_amount) * 100
```
Example: $180 profit on $500 bet = 36% ROI

### Entry/Exit Dates
```python
# Entry date: First BUY trade for this conditionId
entry_date = min(timestamp for trades where side="BUY" and conditionId matches)

# Exit date: From position's endDate or timestamp
exit_date = position.endDate or datetime.fromtimestamp(position.timestamp)
```

---

## Known Limitations

1. **API Pagination:** Trades endpoint is capped at 5000 pages to prevent infinite loops
2. **Category Lookup Errors:** Some markets fail to fetch tags (shown as "Other")
3. **Unrealized PnL Timing:** Only reflects current market prices, not historical
4. **Closed Positions Limit:** API enforces max 50 per page (we paginate through all)

---

## Verification Checklist

To verify calculations are correct:

1. **Total PnL Match:** `calc_total_pnl` ≈ `total_pnl` (leaderboard)
2. **Position Counts:** `closed_positions` + `open_positions` = total unique markets
3. **Win/Loss Sum:** `wins + losses` = `closed_positions`
4. **Category PnL Sum:** Sum of all category PnLs ≈ `realized_pnl`
5. **Price Tier Sum:** Sum of all tier PnLs ≈ `realized_pnl` (from closed only)

---

## File Locations

- Main report generator: `src/run_468_report.py`
- PnL verification script: `src/verify_pnl.py`
- Debug scripts: `research/debug_pnl*.py`
