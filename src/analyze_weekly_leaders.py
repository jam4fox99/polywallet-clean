"""
Analyze weekly traders - FAST VERSION (no category lookups).
Categories can be added later with fix_market_data.py
"""
import asyncio
import aiohttp
import time
import os
import sys
from datetime import datetime
from collections import defaultdict

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, ".")

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent / ".env")

from src import db_cache
from src.pnl_calculator import calculate_time_period_pnl, calculate_unrealized_pnl

BASE_URL = "https://data-api.polymarket.com"
PROXY_URL = os.getenv("PROXY_URL")

CONCURRENT_WALLETS = 50
PARALLEL_PAGES = 5
WEEKLY_POSITION_LIMIT = 300
WEEK_AGO = time.time() - 604800
DAY_AGO = time.time() - 86400

PRICE_TIERS = [
    (90, 100, "90-100c", 1), (80, 90, "80-90c", 2), (70, 80, "70-80c", 3),
    (60, 70, "60-70c", 4), (50, 60, "50-60c", 5), (40, 50, "40-50c", 6),
    (30, 40, "30-40c", 7), (20, 30, "20-30c", 8), (10, 20, "10-20c", 9), (0, 10, "0-10c", 10)
]

async def fetch(session, url, params=None):
    for _ in range(2):
        try:
            async with session.get(url, params=params, proxy=PROXY_URL,
                                   timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status == 200:
                    return await r.json()
        except:
            await asyncio.sleep(0.2)
    return None

async def fetch_pages(session, url, wallet, page_size=500):
    all_data = []
    offset = 0
    for _ in range(3):
        tasks = [fetch(session, url, {"user": wallet, "limit": page_size, "offset": offset + (i * page_size)}) 
                 for i in range(PARALLEL_PAGES)]
        results = await asyncio.gather(*tasks)
        for data in results:
            if data:
                for item in data:
                    ts = item.get("timestamp") or 0
                    if ts >= WEEK_AGO:
                        all_data.append(item)
        if any(r is None or len(r) < page_size for r in results):
            break
        offset += PARALLEL_PAGES * page_size
    return all_data

async def analyze_wallet(session, wallet, lb_data, client):
    username = lb_data.get("username", "")
    rank = lb_data.get("rank")
    lb_pnl = float(lb_data.get("pnl") or 0)
    volume = float(lb_data.get("volume") or 0)
    
    # Fetch data
    trades = await fetch_pages(session, f"{BASE_URL}/trades", wallet, 500)
    closed = await fetch_pages(session, f"{BASE_URL}/closed-positions", wallet, 50)
    positions = await fetch(session, f"{BASE_URL}/positions", {"user": wallet, "limit": 500}) or []
    
    # Save raw data
    if trades:
        db_cache.save_trades(wallet, trades)
    if closed:
        db_cache.save_closed_positions(wallet, closed)
    if positions:
        db_cache.save_open_positions(wallet, positions)
    
    # Count weekly positions
    weekly_buys = [t for t in trades if t.get("side") == "BUY"]
    unique_markets = set(t.get("conditionId") for t in weekly_buys if t.get("conditionId"))
    weekly_positions = len(unique_markets)
    
    # Calculate stats using correct methodology (resolution timestamp-based)
    # Key: Use timestamp field which is the RESOLUTION time, not entry time
    pnl_stats = calculate_time_period_pnl(closed)
    unrealized_stats = calculate_unrealized_pnl(positions)
    
    realized_1d = pnl_stats["realized_1d"]
    realized_7d = pnl_stats["realized_7d"]
    unrealized = unrealized_stats["unrealized_pnl"]
    wins = pnl_stats["wins"]
    losses = pnl_stats["losses"]
    win_rate = pnl_stats["win_rate"]
    
    total_invested = sum(float(t.get("usdcSize", 0)) for t in trades if t.get("side") == "BUY")
    roi = round((realized_7d / total_invested) * 100, 2) if total_invested > 0 else 0
    avg_bet = round(total_invested / len(trades), 2) if trades else 0
    
    # Save wallet stats with correct time-based PnL calculations
    try:
        client.table("wallet_stats").upsert({
            "wallet": wallet, "username": username, "rank": rank,
            "realized_1d": realized_1d, "realized_7d": realized_7d,
            "realized_30d": pnl_stats["realized_30d"], 
            "realized_all": pnl_stats["realized_all"],
            "unrealized_pnl": unrealized, "total_pnl": realized_7d + unrealized,
            "volume": volume, "roi": roi, "win_rate": win_rate,
            "wins": wins, "losses": losses,
            "markets_traded": len(set(p.get("conditionId") for p in closed)),
            "total_trades": len(trades), "avg_bet_size": avg_bet,
            "lb_pnl": lb_pnl, "calc_pnl": realized_7d + unrealized,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
    except:
        pass
    
    # Price tiers only (fast, no API calls)
    tier_stats = defaultdict(lambda: {"pos": 0, "wins": 0, "pnl": 0})
    for p in closed:
        price = float(p.get("avgPrice", 0)) * 100
        pnl = float(p.get("realizedPnl", 0))
        for low, high, name, order in PRICE_TIERS:
            if low <= price < high:
                tier_stats[name]["pos"] += 1
                tier_stats[name]["pnl"] += pnl
                if pnl > 0:
                    tier_stats[name]["wins"] += 1
                break
    
    total_pos = len(closed)
    for low, high, name, order in PRICE_TIERS:
        ts = tier_stats[name]
        try:
            client.table("wallet_price_tiers").upsert({
                "wallet": wallet, "tier": name, "tier_order": order,
                "positions": ts["pos"],
                "pct_of_total": round((ts["pos"] / total_pos) * 100, 1) if total_pos > 0 else 0,
                "win_rate": round((ts["wins"] / ts["pos"]) * 100, 1) if ts["pos"] > 0 else 0,
                "total_pnl": round(ts["pnl"], 2)
            }).execute()
        except:
            pass
    
    # Store positions with title from API (no category lookup)
    for p in closed[:15]:
        title = p.get("title", "Unknown")
        cid = p.get("conditionId", "")
        pnl = float(p.get("realizedPnl", 0))
        size = float(p.get("totalBought", 0)) * float(p.get("avgPrice", 0))
        roi_pos = round((pnl / size) * 100, 1) if size > 0 else 0
        end_date = p.get("endDate", "")[:10] if p.get("endDate") else None
        try:
            client.table("positions_enriched").upsert({
                "wallet": wallet, "condition_id": cid,
                "market_name": title[:200] if title else "Unknown",
                "outcome": p.get("outcome", ""), "category": "TBD",
                "entry_price": float(p.get("avgPrice", 0)),
                "usd_amount": size, "pnl": pnl, "roi": roi_pos,
                "exit_date": end_date, "is_open": False
            }).execute()
        except:
            pass
    
    return weekly_positions, len(closed), len(positions)

async def process_wallet(session, wallet, rank, lb_data, semaphore, client):
    async with semaphore:
        ws = wallet[:10]
        try:
            weekly_pos, closed, opened = await analyze_wallet(session, wallet, lb_data, client)
            
            is_hf = weekly_pos > WEEKLY_POSITION_LIMIT
            client.table("leaderboard_rankings").update({
                "weekly_positions": weekly_pos,
                "high_frequency": is_hf,
                "fully_analyzed": not is_hf,
                "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }).eq("wallet", wallet).eq("time_period", "week").execute()
            
            return f"#{rank} {ws}: {'HF' if is_hf else 'OK'} ({weekly_pos}p {closed}c)"
        except Exception as e:
            return f"#{rank} {ws}: ERR"

async def main():
    print("=" * 60, flush=True)
    print("WEEKLY ANALYSIS - FAST MODE (no category lookups)", flush=True)
    print(f"Concurrent: {CONCURRENT_WALLETS} | Proxy: {'ON' if PROXY_URL else 'OFF'}", flush=True)
    print("=" * 60, flush=True)
    
    client = db_cache.get_client()
    
    result = client.table("leaderboard_rankings")\
        .select("wallet, rank, username, pnl, volume")\
        .eq("time_period", "week")\
        .is_("analyzed_at", "null")\
        .order("rank")\
        .limit(10000)\
        .execute()
    
    wallets = [(r["wallet"], r["rank"], r) for r in result.data]
    print(f"Wallets: {len(wallets)}\n", flush=True)
    
    if not wallets:
        print("Done!", flush=True)
        return
    
    semaphore = asyncio.Semaphore(CONCURRENT_WALLETS)
    connector = aiohttp.TCPConnector(limit=200)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        hf, done = 0, 0
        start = time.time()
        
        batch_size = 20
        for i in range(0, len(wallets), batch_size):
            batch = wallets[i:i + batch_size]
            tasks = [process_wallet(session, w, r, lb, semaphore, client) for w, r, lb in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for r in results:
                if isinstance(r, str):
                    print(f"  {r}", flush=True)
                    if "HF" in r: hf += 1
                    elif "OK" in r: done += 1
            
            elapsed = time.time() - start
            rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
            eta = (len(wallets) - i - len(batch)) / rate / 60 if rate > 0 else 0
            print(f"\n>> {i+len(batch)}/{len(wallets)} | {rate:.1f}/s | ETA:{eta:.0f}m\n", flush=True)
    
    print(f"\nDONE! HF:{hf} OK:{done}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
