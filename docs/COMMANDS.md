# Command Reference

Complete documentation of all CLI commands and options.

---

## Main Report Generator

### Basic Usage
```bash
python run.py [options]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--wallet-file` | `data/wallets.csv` | Path to CSV file with wallet addresses |
| `--output` | `output/report.xlsx` | Path for generated Excel report |
| `--limit N` | None (all) | Only process first N wallets (for testing) |
| `--no-proxy` | False | Disable BrightData proxy, call APIs directly |
| `--no-cache` | False | Disable Supabase caching, fetch all fresh |

### Examples

```bash
# Run with all defaults
python run.py

# Test with 5 wallets, no proxy
python run.py --limit 5 --no-proxy

# Custom input/output files
python run.py --wallet-file data/top_traders.csv --output output/top_traders.xlsx

# Force fresh data (ignore cache)
python run.py --no-cache

# Full production run with proxy and cache
python run.py --wallet-file data/wallets.csv
```

---

## Input File Format

### wallets.csv
```csv
wallet
0x8c0b024c17831a0dde038547b7e791ae6a0d7aa5
0xabc123def456...
```

- Header must be `wallet`
- One wallet address per line
- Ethereum addresses (0x...)

---

## Output

### report.xlsx
Excel workbook with one sheet per wallet containing:
- PnL Breakdown (1D, 7D, 30D, All-time)
- Stats (Volume, ROI, Win Rate, Avg Bet Size)
- Price Tier Analysis
- Category Performance
- All Trades by Category

---

## Other Scripts

### Verify PnL Calculations
```bash
python -m src.verify_pnl --wallet-file data/wallets.csv --output output/verification.csv
```

### Test Proxy Connection
```bash
python -m src.test_proxy
```

---

## Environment Variables

Set in `.env` file:

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | For caching | Supabase project URL |
| `SUPABASE_KEY` | For caching | Supabase anon/public key |
| `PROXY_URL` | Optional | BrightData proxy URL |

---

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `/v1/leaderboard` | Wallet stats, rank, PnL |
| `/traded` | Number of markets traded |
| `/trades` | Individual trade history (paginated) |
| `/closed-positions` | Closed positions with PnL |
| `/positions` | Current open positions |
| `gamma-api/markets` | Market metadata |
| `gamma-api/markets/{id}/tags` | Market categories |

---

## Future Commands (Planned)

| Command | Description |
|---------|-------------|
| `--fetch-leaderboard N` | Fetch top N wallets from Polymarket leaderboard |
| `--update-only` | Only fetch new trades for existing wallets |
| `--export-db` | Export cached data to CSV |
