# Project Structure

This document explains the codebase organization for the Polymarket Wallet Checker.

## Directory Layout

```
polywallet-db/
|-- src/                    # All Python source code
|   |-- __init__.py         # Package marker
|   |-- report.py           # Main report generator
|   |-- db_cache.py         # Supabase caching module
|   |-- verify_pnl.py       # PnL verification script
|   +-- test_proxy.py       # Proxy connection tester
|
|-- data/                   # Input data files
|   +-- wallets.csv         # Wallet addresses to analyze
|
|-- output/                 # Generated outputs
|   +-- report.xlsx         # Excel reports
|
|-- docs/                   # Documentation
|   +-- CALCULATIONS.md     # How metrics are calculated
|
|-- .env                    # Your credentials (git ignored)
|-- .env.example            # Template for .env
|-- .gitignore              # Git ignore rules
|-- requirements.txt        # Python dependencies
|-- run.py                  # Main entry point
|-- README.md               # Project overview
+-- STRUCTURE.md            # This file
```

## Where to Put New Files

| File Type | Location | Example |
|-----------|----------|---------|
| Python modules | `src/` | `src/new_feature.py` |
| Input data (CSV, JSON) | `data/` | `data/new_wallets.csv` |
| Generated reports | `output/` | `output/detailed_report.xlsx` |
| Documentation | `docs/` | `docs/API_REFERENCE.md` |
| Config files | Root | `.env`, `config.yaml` |

## Running the Scripts

```bash
# Main report generator
python run.py --wallet-file data/wallets.csv --output output/report.xlsx

# With options
python run.py --limit 5 --no-proxy --no-cache

# Verify PnL calculations
python -m src.verify_pnl --wallet-file data/wallets.csv

# Test proxy connection
python -m src.test_proxy
```

## Adding New Features

1. Create your Python file in `src/`
2. Import it in `src/__init__.py` if needed
3. If it needs CLI access, create an entry point or add to `run.py`

## Environment Variables

Required in `.env`:
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase anon/public key
- `PROXY_URL` - (Optional) BrightData proxy URL
