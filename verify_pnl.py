"""
Verify Polymarket PnL correctness across wallets.
- Fetch leaderboard PnL
- Sum realized PnL from all closed positions
- Sum unrealized PnL from open positions
- Compare leaderboard PnL vs (realized + unrealized)
Saves a CSV with per-wallet diffs and prints a summary.
"""
import os
import argparse
import asyncio
from pathlib import Path
import aiohttp
import pandas as pd
import time

BASE_URL = "https://data-api.polymarket.com"
PROXY_URL = os.getenv("PROXY_URL")

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_WALLET_FILE = ROOT_DIR / "data" / "wallets.csv"
DEFAULT_OUTPUT_FILE = ROOT_DIR / "output" / "pnl_verification.csv"

MAX_CONCURRENT_WALLETS = 20
REQUEST_TIMEOUT = 8
MAX_RETRIES = 2

class PNLVerifier:
    def __init__(self, proxy_url: str | None):
        self.proxy_url = proxy_url
        self.sem = asyncio.Semaphore(MAX_CONCURRENT_WALLETS)
        self.api_calls = 0
        self.retries = 0
        self.errors = 0
        self.start_time = None
        self.completed = 0
        self.total = 0

    async def fetch(self, session, url, params=None):
        for _ in range(MAX_RETRIES):
            self.api_calls += 1
            try:
                async with session.get(
                    url,
                    params=params,
                    proxy=self.proxy_url,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                ) as r:
                    if r.status == 200:
                        return await r.json()
                    self.retries += 1
            except Exception:
                self.retries += 1
        self.errors += 1
        return None

    async def fetch_all_paginated(self, session, endpoint, params, limit=100):
        """Fetch all pages for an endpoint with offset/limit pagination (no hard cap)."""
        all_rows = []
        offset = 0
        while True:
            page_params = dict(params)
            page_params.update({"limit": limit, "offset": offset})
            data = await self.fetch(session, f"{BASE_URL}/{endpoint}", page_params)
            if not data:
                break
            all_rows.extend(data)
            offset += len(data)
            if len(data) < limit:
                break
        return all_rows

    async def process_wallet(self, session, wallet: str):
        async with self.sem:
            try:
                lb = await self.fetch(session, f"{BASE_URL}/v1/leaderboard", {"timePeriod": "all", "user": wallet})
                lb_pnl = float(lb[0].get("pnl", 0)) if lb and len(lb) > 0 else None

                # Closed positions for realized PnL
                # closed-positions limit is hard-capped at 50 by the API
                closed = await self.fetch_all_paginated(
                    session,
                    "closed-positions",
                    {"user": wallet, "sortBy": "timestamp", "sortDirection": "DESC"},
                    limit=50,
                )
                realized_closed = sum(float(p.get("realizedPnl", 0)) for p in closed)

                # Open positions for unrealized PnL
                positions = await self.fetch_all_paginated(
                    session,
                    "positions",
                    {"user": wallet, "sortBy": "CURRENT", "sortDirection": "DESC"},
                    limit=500,
                )
                unrealized = sum(float(p.get("cashPnl", 0)) for p in positions)
                realized_open = sum(float(p.get("realizedPnl", 0)) for p in positions)

                realized_total = realized_closed + realized_open
                computed = realized_total + unrealized
                diff = computed - lb_pnl if lb_pnl is not None else None

                self.completed += 1
                return {
                    "wallet": wallet,
                    "leaderboard_pnl": lb_pnl,
                    "realized_pnl_closed": round(realized_closed, 2),
                    "realized_pnl_open": round(realized_open, 2),
                    "realized_pnl_total": round(realized_total, 2),
                    "unrealized_pnl": round(unrealized, 2),
                    "computed_total": round(computed, 2),
                    "diff_vs_leaderboard": round(diff, 2) if diff is not None else None,
                    "closed_count": len(closed),
                    "open_count": len(positions),
                    "status": "ok",
                }
            except Exception as e:
                self.errors += 1
                self.completed += 1
                return {
                    "wallet": wallet,
                    "leaderboard_pnl": None,
                    "realized_pnl": 0,
                    "unrealized_pnl": 0,
                    "computed_total": 0,
                    "diff_vs_leaderboard": None,
                    "closed_count": 0,
                    "open_count": 0,
                    "status": f"error: {e}",
                }

    async def progress(self):
        while self.completed < self.total:
            await asyncio.sleep(5)
            elapsed = time.time() - self.start_time
            rate = self.completed / elapsed if elapsed else 0
            print(f"Progress: {self.completed}/{self.total} ({rate:.1f} w/s) | API calls: {self.api_calls} | Errors: {self.errors}")

    async def verify(self, wallets, output_path: Path):
        self.total = len(wallets)
        self.start_time = time.time()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
        async with aiohttp.ClientSession(connector=connector) as session:
            prog_task = asyncio.create_task(self.progress())
            tasks = [self.process_wallet(session, w) for w in wallets]
            results = await asyncio.gather(*tasks)
            prog_task.cancel()

        df = pd.DataFrame(results)
        df.to_csv(output_path, index=False)

        # Summary
        mismatched = df[df["diff_vs_leaderboard"].abs() > 1] if "diff_vs_leaderboard" in df else pd.DataFrame()
        print("\nVerification complete")
        print(f"Wallets: {len(df)} | Errors: {self.errors} | API calls: {self.api_calls} | Retries: {self.retries}")
        if not mismatched.empty:
            print(f"Mismatches (> $1 difference): {len(mismatched)}")
            print(mismatched[["wallet", "leaderboard_pnl", "computed_total", "diff_vs_leaderboard"]].head(10))
        else:
            print("All wallets matched within $1.")
        print(f"Results saved to: {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Verify Polymarket PnL vs leaderboard")
    parser.add_argument("--wallet-file", type=Path, default=DEFAULT_WALLET_FILE, help="CSV of wallets")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_FILE, help="Output CSV for verification")
    parser.add_argument("--limit", type=int, default=None, help="Limit wallets for a quick check")
    parser.add_argument("--no-proxy", action="store_true", help="Disable BrightData proxy")
    return parser.parse_args()


async def main():
    args = parse_args()
    wallet_file = args.wallet_file.expanduser()
    output_path = args.output.expanduser()

    if not wallet_file.is_file():
        raise FileNotFoundError(f"Wallet CSV not found: {wallet_file}")

    df = pd.read_csv(wallet_file)
    wallets = df["wallet"].tolist()
    if args.limit:
        wallets = wallets[: args.limit]

    print(f"Loaded {len(wallets)} wallets from {wallet_file}")
    print(f"Proxy: {'disabled' if args.no_proxy else 'enabled'}")
    verifier = PNLVerifier(proxy_url=None if args.no_proxy else PROXY_URL)
    await verifier.verify(wallets, output_path)


if __name__ == "__main__":
    asyncio.run(main())
