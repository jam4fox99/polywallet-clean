"""
Fix market names and categories from closed_positions data.
Uses title and slug fields that are already stored.
"""
import asyncio
import aiohttp
import os
import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
from pathlib import Path
from collections import defaultdict

load_dotenv(Path(__file__).parent.parent / ".env")
from src import db_cache

GAMMA_URL = "https://gamma-api.polymarket.com"
PROXY_URL = os.getenv("PROXY_URL")

slug_cache = {}

async def fetch(session, url):
    try:
        async with session.get(url, proxy=PROXY_URL, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                return await r.json()
    except:
        pass
    return None

async def get_category(session, slug, client):
    """Get category from slug via Gamma API."""
    if not slug:
        return "Other"
    
    if slug in slug_cache:
        return slug_cache[slug]
    
    # Check DB cache
    try:
        r = client.table("market_names").select("category").eq("condition_id", slug).execute()
        if r.data and r.data[0]["category"] != "Other":
            slug_cache[slug] = r.data[0]["category"]
            return slug_cache[slug]
    except:
        pass
    
    # Fetch from Gamma API
    data = await fetch(session, f"{GAMMA_URL}/markets?slug={slug}")
    if data and len(data) > 0:
        market_id = data[0].get("id")
        if market_id:
            tags_data = await fetch(session, f"{GAMMA_URL}/markets/{market_id}/tags")
            if tags_data:
                # Get first non-generic tag
                for t in tags_data:
                    label = t.get("label", "")
                    if label and label not in ["All", "Games"]:
                        slug_cache[slug] = label
                        # Cache in DB
                        try:
                            client.table("market_names").upsert({
                                "condition_id": slug,
                                "market_name": data[0].get("question", "")[:100],
                                "category": label
                            }).execute()
                        except:
                            pass
                        return label
    
    slug_cache[slug] = "Other"
    return "Other"

async def fix_wallet(session, wallet, client):
    """Fix market data for one wallet."""
    ws = wallet[:10]
    
    # Get closed positions with title and slug
    positions = client.table("closed_positions").select("*").eq("wallet", wallet).execute()
    if not positions.data:
        return 0
    
    print(f"  {ws}: {len(positions.data)} positions", flush=True)
    
    # Get unique slugs and fetch categories
    slugs = list(set(p["slug"] for p in positions.data if p.get("slug")))
    for slug in slugs[:20]:  # Limit API calls
        await get_category(session, slug, client)
    
    # Update positions_enriched with correct market names
    for p in positions.data[:30]:
        title = p.get("title", "Unknown")
        slug = p.get("slug", "")
        category = slug_cache.get(slug, "Other")
        cid = p.get("condition_id", "")
        pnl = float(p.get("realized_pnl") or 0)
        size = float(p.get("total_bought") or 0) * float(p.get("avg_price") or 0)
        roi = round((pnl / size) * 100, 1) if size > 0 else 0
        
        try:
            client.table("positions_enriched").upsert({
                "wallet": wallet,
                "condition_id": cid,
                "market_name": title[:200] if title else "Unknown",
                "outcome": p.get("outcome", ""),
                "category": category,
                "entry_price": float(p.get("avg_price") or 0),
                "usd_amount": size,
                "pnl": pnl,
                "roi": roi,
                "exit_date": p.get("end_date", "")[:10] if p.get("end_date") else None,
                "is_open": False
            }).execute()
        except:
            pass
    
    # Update wallet_categories
    cat_stats = defaultdict(lambda: {"vol": 0, "pnl": 0, "count": 0})
    for p in positions.data:
        slug = p.get("slug", "")
        category = slug_cache.get(slug, "Other")
        pnl = float(p.get("realized_pnl") or 0)
        cat_stats[category]["pnl"] += pnl
        cat_stats[category]["count"] += 1
    
    for cat, data in cat_stats.items():
        try:
            client.table("wallet_categories").upsert({
                "wallet": wallet,
                "category": cat,
                "pct_volume": 0,
                "pnl": round(data["pnl"], 2),
                "positions_count": data["count"]
            }).execute()
        except:
            pass
    
    return len(positions.data)

async def main():
    print("=" * 60, flush=True)
    print("FIXING MARKET NAMES AND CATEGORIES", flush=True)
    print("=" * 60, flush=True)
    
    client = db_cache.get_client()
    
    # Get wallets with stats (already analyzed)
    wallets = client.table("wallet_stats").select("wallet").limit(100).execute()
    print(f"Fixing {len(wallets.data)} wallets...\n", flush=True)
    
    async with aiohttp.ClientSession() as session:
        for w in wallets.data:
            await fix_wallet(session, w["wallet"], client)
    
    print("\nDone!", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
