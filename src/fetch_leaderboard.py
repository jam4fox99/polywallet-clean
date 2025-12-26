"""Fetch top N wallets from Polymarket leaderboard and store in Supabase."""
import asyncio
import aiohttp
import sys
sys.path.insert(0, ".")
from src import db_cache

BASE_URL = "https://data-api.polymarket.com"

async def fetch_leaderboard(limit=10000, time_period="all"):
    """Fetch top N wallets from leaderboard."""
    all_entries = []
    offset = 0
    batch_size = 50  # API max per request
    
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        while offset < limit:
            current_batch = min(batch_size, limit - offset)
            url = f"{BASE_URL}/v1/leaderboard"
            params = {"timePeriod": time_period, "limit": current_batch, "offset": offset}
            
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    if r.status == 200:
                        data = await r.json()
                        if not data:
                            print(f"  No more data at offset {offset}")
                            break
                        all_entries.extend(data)
                        if offset % 500 == 0 or len(all_entries) >= limit:
                            print(f"  Fetched {len(all_entries)}/{limit} ({time_period})...")
                        if len(data) < current_batch:
                            break
                    else:
                        print(f"  Error: {r.status}")
                        break
            except Exception as e:
                print(f"  Error at offset {offset}: {e}")
                break
            
            offset += current_batch
            await asyncio.sleep(0.05)  # Small delay to be nice to API
    
    return all_entries

async def main():
    print("=" * 60)
    print("FETCHING TOP 10,000 WALLETS FROM POLYMARKET LEADERBOARD")
    print("=" * 60)
    
    # Fetch for all time periods
    for period in ["all", "month", "week", "day"]:
        print(f"\nFetching {period} leaderboard...")
        entries = await fetch_leaderboard(limit=10000, time_period=period)
        print(f"  Total: {len(entries)} entries")
        
        if entries:
            print(f"  Saving to Supabase...")
            db_cache.save_leaderboard(entries, time_period=period)
    
    print("\n" + "=" * 60)
    print("DONE! Check your Supabase leaderboard_rankings table.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
