# Market Maker Detector - Polymarket Liquidity Rewards Analysis

## Description
Analyzes Polymarket wallets to detect market makers vs real predictive traders by examining liquidity rewards data. Helps identify which wallets are earning profits from genuine predictions vs farming market maker incentives.

## Model
inherit

## Tools
- mcp
- execute

---

## Key Knowledge: Polymarket Rewards System

### Two Types of Rewards

#### 1. Liquidity Rewards (Daily)
- Paid for posting **limit orders within the spread**
- Closer to midpoint = more rewards
- Two-sided liquidity (bids + asks) scores higher
- Formula favors tight spreads and balanced order books
- Paid daily at midnight UTC
- Minimum payout: $1

#### 2. Holding Rewards (4% APY)
- Paid for holding positions in certain long-term markets
- 4% annualized, calculated daily
- Only on eligible markets (elections, long-dated events)

---

## API Endpoint to Fetch Rewards

```
GET https://data-api.polymarket.com/activity?user=<WALLET>&type=REWARD
```

### Parameters:
- `user`: Wallet address (0x prefixed)
- `type`: `REWARD` for liquidity rewards
- `limit`: Max results (default 100, max 500)
- `sortBy`: `TIMESTAMP`
- `sortDirection`: `DESC`

### Response Fields:
- `usdcSize`: Reward amount in USDC
- `timestamp`: Unix timestamp
- `transactionHash`: On-chain tx hash
- `conditionId`: Market condition ID
- `title`: Market title

---

## Market Maker Detection Logic

```python
is_market_maker = TRUE if ANY of:
  - total_rewards > $1,000 (lifetime)
  - avg_daily_reward > $10
  - win_rate = 100% AND positions > 100
```

### Thresholds:
| Metric | Real Trader | Market Maker |
|--------|-------------|--------------|
| Total Rewards | < $100 | > $1,000 |
| Avg Daily | < $1 | > $10 |
| Win Rate | 65-95% | Often 100% |

---

## Database Tables

### `wallet_rewards`
Stores individual reward transactions:
```sql
- wallet TEXT
- timestamp BIGINT
- type TEXT ('REWARD')
- usdc_size NUMERIC
- transaction_hash TEXT
- condition_id TEXT
- title TEXT
```

### `wallet_reward_stats`
Summary statistics for quick lookups:
```sql
- wallet TEXT PRIMARY KEY
- total_rewards NUMERIC
- reward_count INTEGER
- first_reward_at BIGINT
- last_reward_at BIGINT
- avg_daily_reward NUMERIC
- is_market_maker BOOLEAN
```

---

## Python Module: `src/rewards_fetcher.py`

### Key Functions:
```python
fetch_wallet_rewards(wallet, limit=500) -> list
# Fetches reward transactions from Polymarket API

calculate_reward_stats(rewards) -> dict
# Returns: total_rewards, reward_count, avg_daily_reward, is_market_maker

analyze_wallet_rewards(wallet) -> dict
# Full analysis with stats and raw rewards

format_reward_report(stats) -> str
# Human-readable report
```

### Usage:
```bash
python src/rewards_fetcher.py <wallet_address>
```

---

## Verified Findings (Dec 2025)

### Confirmed Market Makers (High Rewards):
| Wallet | Username | Total Rewards | Avg/Day |
|--------|----------|---------------|---------|
| 0xbacd00c9080a82ded56f504ee8810af732b0ab35 | ScottyNooo | $27,252 | $116 |
| 0xd218e474776403a330142299f7796e8ba32eb5c9 | cigarettes | $31,081 | $68 |
| 0xe90bec87d9ef430f27f9dcfe72c34b76967d5da2 | gmanas | $450 | $22 |
| 0xdb27bf2ac5d428a9c63dbc914611036855a6c56e | DrPufferfish | $1,019 | $5 |

### Confirmed Real Traders (No/Minimal Rewards):
| Wallet | Username | Total Rewards | All-Time PnL |
|--------|----------|---------------|--------------|
| 0xb2e4567925b79231265adf5d54687ddfb761bc51 | Cortisfans | $0 | $854K |
| 0x8717e750e5e20cd0e28e39280e960cc020fb49a8 | fishuu | $0 | $116K |
| 0x39932ca2b7a1b8ab6cbf0b8f7419261b950ccded | Andromeda1 | $32 | $470K |
| 0x8c0b024c17831a0dde038547b7e791ae6a0d7aa5 | ESPORTSENTHUSIAST | $28 | $354K |
| 0xe00740bce98a594e26861838885ab310ec3b548c | distinct-baguette | $0 | $274K |

---

## Why This Matters for Copy Trading

### Market Makers:
- Profits come from bid/ask spread + liquidity rewards
- Often hedge both sides (100% win rate)
- Hard to copy (they use algorithms, execute in milliseconds)
- Their "edge" is speed and capital, not prediction skill

### Real Traders:
- Profits come from **actually predicting outcomes**
- Have losses (proves they take directional risk)
- Win rates 65-95% (not perfect)
- Their edge is **knowledge** you can copy

---

## Recommended Copy Trading Filters

```sql
-- Find real traders, not market makers
SELECT w.*, rs.total_rewards, rs.is_market_maker
FROM wallet_stats w
LEFT JOIN wallet_reward_stats rs ON w.wallet = rs.wallet
WHERE 
  rs.is_market_maker = FALSE OR rs.is_market_maker IS NULL
  AND w.all_time_pnl > 50000
  AND w.win_rate BETWEEN 65 AND 95
  AND w.total_losses > 5  -- Proves they take real bets
ORDER BY w.weekly_pnl DESC
```

---

## SQL Queries for Analysis

### Check if wallet is market maker:
```sql
SELECT 
  wallet,
  total_rewards,
  reward_count,
  avg_daily_reward,
  is_market_maker
FROM wallet_reward_stats
WHERE wallet = '<WALLET_ADDRESS>'
```

### Top market makers by rewards:
```sql
SELECT * FROM wallet_reward_stats
WHERE is_market_maker = TRUE
ORDER BY total_rewards DESC
LIMIT 20
```

### Real traders with best performance:
```sql
SELECT 
  w.username,
  w.wallet,
  w.all_time_pnl,
  w.weekly_pnl,
  w.win_rate,
  COALESCE(rs.total_rewards, 0) as rewards
FROM wallet_stats w
LEFT JOIN wallet_reward_stats rs ON w.wallet = rs.wallet
WHERE COALESCE(rs.is_market_maker, FALSE) = FALSE
  AND w.all_time_pnl > 100000
ORDER BY w.weekly_pnl DESC
```

---

## Common Questions

**Q: Can market makers still be good copy targets?**
A: It depends. Some like DrPufferfish earn moderate rewards but also make real predictions. Check their win rate - if <100%, they're taking real bets too.

**Q: Why do some 100% win rate wallets have $0 rewards?**
A: They may be arbitrage bots using market orders (not limit orders), or using a different profit strategy like split/merge arbitrage.

**Q: How often should I refresh reward data?**
A: Weekly is fine. Rewards are paid daily but patterns emerge over time.

**Q: What's the minimum threshold to flag as market maker?**
A: $1,000 lifetime OR $10/day average. These are conservative thresholds.
