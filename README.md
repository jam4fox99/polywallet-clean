# Polymarket Wallet Checker

Generate detailed XLSX reports for Polymarket wallet performance analysis.

## Features

- Fetch wallet PnL, trades, and positions from Polymarket APIs
- Generate Excel reports with:
  - PnL breakdown (1D, 7D, 30D, All-time)
  - Stats (volume, ROI, win rate, avg bet size)
  - Price tier analysis
  - Category breakdown (Sports, Esports, Crypto, etc.)
  - All trades grouped by category with ROI %
- Support for BrightData proxy to avoid rate limits

## Setup

1. Clone the repo:
```bash
git clone https://github.com/YOUR_USERNAME/poly-wallet-checker.git
cd poly-wallet-checker
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Set up proxy - create `.env` file:
```
PROXY_URL=http://your-brightdata-proxy-url
```

## Usage

### Generate Report

Create a CSV file with wallet addresses (one per line with header "wallet"):
```csv
wallet
0x8c0b024c17831a0dde038547b7e791ae6a0d7aa5
0xabc123...
```

Run the report:
```bash
# With proxy
python run_468_report.py --wallet-file data/wallets.csv --output output/report.xlsx

# Without proxy (direct API calls)
python run_468_report.py --wallet-file data/wallets.csv --output output/report.xlsx --no-proxy

# Test with limited wallets
python run_468_report.py --wallet-file data/wallets.csv --limit 5 --no-proxy
```

### Verify PnL Calculations

```bash
python verify_pnl.py --wallet-file data/wallets.csv --output output/verification.csv
```

### Test Proxy Connection

```bash
python test_proxy.py
```

## Files

| File | Purpose |
|------|---------|
| `run_468_report.py` | Main report generator |
| `verify_pnl.py` | Verify PnL calculations match leaderboard |
| `test_proxy.py` | Test BrightData proxy connection |
| `CALCULATIONS.md` | Documentation of all calculations |

## Documentation

See [CALCULATIONS.md](CALCULATIONS.md) for detailed explanation of how all metrics are calculated.
