# Polymarket Wallet Analyzer

Analyze top Polymarket traders, cache data in Supabase, and backtest copy trading strategies.

## Features

- Fetch and Cache top 10,000 weekly traders from Polymarket leaderboard
- Full Analysis: Store trades, positions, stats, price tiers for each wallet
- Zero-API Reports: Generate Excel reports entirely from cached Supabase data
- Copy Trading Backtest: Simulate copy trading strategies to find best wallets

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

- SUPABASE_URL - Your Supabase project URL (from Settings > API)
- SUPABASE_KEY - Your Supabase anon key (from Settings > API)
- PROXY_URL - Optional BrightData proxy URL

### 3. Database Setup

Create the required tables in Supabase SQL Editor. See docs/COMMANDS.md for schema.

## Usage

### Fetch Leaderboard
```bash
python src/fetch_leaderboard.py
```

### Analyze Wallets
```bash
python -u src/analyze_weekly_leaders.py
```

### Generate Reports (from cache)
```bash
python src/generate_report.py --limit 30
```

### Backtest Copy Trading
```bash
python src/backtest_copy.py
```

## Project Structure

```
src/
  db_cache.py              - Supabase caching layer
  analyze_weekly_leaders.py - Bulk wallet analyzer
  generate_report.py       - Excel from cache
  fetch_leaderboard.py     - Fetch top traders
  backtest_copy.py         - Copy trading simulator
output/                    - Generated Excel reports
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| SUPABASE_URL | Yes | Supabase project URL |
| SUPABASE_KEY | Yes | Supabase anon key |
| PROXY_URL | No | Proxy for rate limits |
