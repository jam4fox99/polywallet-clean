"""
Supabase cache module for Polymarket wallet data.
Handles incremental syncing - only fetches new trades on subsequent runs.
"""
import os
import time
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env from project root (parent of src/)
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

_client = None

def get_client():
    """Lazy-load Supabase client."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return None
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def is_cache_enabled() -> bool:
    """Check if Supabase caching is configured."""
    return bool(SUPABASE_URL and SUPABASE_KEY)


def get_wallet_info(wallet: str) -> Optional[dict]:
    """Get wallet metadata including last sync timestamp."""
    client = get_client()
    if not client:
        return None
    try:
        result = client.table("wallets").select("*").eq("address", wallet).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[Cache] Error getting wallet info: {e}")
        return None


def get_last_trade_timestamp(wallet: str) -> int:
    """Get the timestamp of the most recent cached trade for a wallet."""
    info = get_wallet_info(wallet)
    return info.get("last_trade_timestamp", 0) if info else 0


def get_cached_trades(wallet: str) -> list:
    """Fetch all cached trades for a wallet with pagination."""
    client = get_client()
    if not client:
        return []
    try:
        all_trades = []
        offset = 0
        limit = 1000
        while True:
            result = client.table("trades").select("raw_data").eq("wallet", wallet).range(offset, offset + limit - 1).execute()
            if not result.data:
                break
            all_trades.extend([row["raw_data"] for row in result.data])
            if len(result.data) < limit:
                break
            offset += limit
        return all_trades
    except Exception as e:
        print(f"[Cache] Error getting cached trades: {e}")
        return []


def get_cached_closed_positions(wallet: str) -> list:
    """Fetch all cached closed positions for a wallet."""
    client = get_client()
    if not client:
        return []
    try:
        result = client.table("closed_positions").select("raw_data").eq("wallet", wallet).execute()
        return [row["raw_data"] for row in result.data] if result.data else []
    except Exception as e:
        print(f"[Cache] Error getting cached positions: {e}")
        return []


def save_wallet(wallet: str, username: str = "", rank: int = None):
    """Create or update wallet record."""
    client = get_client()
    if not client:
        return
    try:
        data = {
            "address": wallet,
            "username": username,
            "rank": rank,
            "last_sync": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        client.table("wallets").upsert(data, on_conflict="address").execute()
    except Exception as e:
        print(f"[Cache] Error saving wallet: {e}")


def save_trades(wallet: str, trades: list):
    """Bulk upsert trades and update last_trade_timestamp."""
    client = get_client()
    if not client or not trades:
        return
    
    try:
        # Deduplicate by trade ID
        seen_ids = set()
        records = []
        max_ts = 0
        for t in trades:
            trade_id = t.get("id") or f"{wallet}_{t.get('timestamp', 0)}_{t.get('conditionId', '')}_{t.get('side', '')}"
            if trade_id in seen_ids:
                continue
            seen_ids.add(trade_id)
            ts = t.get("timestamp", 0)
            if ts > max_ts:
                max_ts = ts
            records.append({
                "id": trade_id,
                "wallet": wallet,
                "condition_id": t.get("conditionId", ""),
                "timestamp": ts,
                "side": t.get("side", ""),
                "size": float(t.get("size", 0)),
                "price": float(t.get("price", 0)),
                "raw_data": t
            })
        
        BATCH_SIZE = 500
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            client.table("trades").upsert(batch, on_conflict="id").execute()
        
        if max_ts > 0:
            client.table("wallets").update({
                "last_trade_timestamp": max_ts,
                "last_sync": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }).eq("address", wallet).execute()
        
        print(f"[Cache] Saved {len(trades)} trades for {wallet[:10]}...")
    except Exception as e:
        print(f"[Cache] Error saving trades: {e}")


def save_closed_positions(wallet: str, positions: list):
    """Bulk upsert closed positions."""
    client = get_client()
    if not client or not positions:
        return
    
    try:
        records = []
        for p in positions:
            pos_id = f"{wallet}_{p.get('conditionId', '')}_{p.get('outcome', '')}"
            records.append({
                "id": pos_id,
                "wallet": wallet,
                "condition_id": p.get("conditionId", ""),
                "slug": p.get("slug", ""),
                "title": p.get("title", ""),
                "outcome": p.get("outcome", ""),
                "avg_price": float(p.get("avgPrice", 0)),
                "total_bought": float(p.get("totalBought", 0)),
                "realized_pnl": float(p.get("realizedPnl", 0)),
                "timestamp": p.get("timestamp", 0),
                "end_date": p.get("endDate", ""),
                "raw_data": p
            })
        
        BATCH_SIZE = 500
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            client.table("closed_positions").upsert(batch, on_conflict="id").execute()
        
        print(f"[Cache] Saved {len(positions)} closed positions for {wallet[:10]}...")
    except Exception as e:
        print(f"[Cache] Error saving positions: {e}")


def get_cached_market_tags(slugs: list) -> dict:
    """Get cached market tags for multiple slugs. Returns {slug: [tags]}."""
    client = get_client()
    if not client or not slugs:
        return {}
    
    try:
        result = client.table("market_tags").select("slug, tags").in_("slug", slugs).execute()
        return {row["slug"]: row["tags"] or [] for row in result.data} if result.data else {}
    except Exception as e:
        print(f"[Cache] Error getting market tags: {e}")
        return {}


def save_market_tags(slug: str, tags: list):
    """Save market tags for a slug."""
    client = get_client()
    if not client or not slug:
        return
    
    try:
        client.table("market_tags").upsert({
            "slug": slug,
            "tags": tags
        }, on_conflict="slug").execute()
    except Exception as e:
        print(f"[Cache] Error saving market tags: {e}")


def save_market_tags_bulk(tags_dict: dict):
    """Bulk save market tags. tags_dict = {slug: [tags]}."""
    client = get_client()
    if not client or not tags_dict:
        return
    
    try:
        records = [{"slug": slug, "tags": tags} for slug, tags in tags_dict.items()]
        BATCH_SIZE = 500
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            client.table("market_tags").upsert(batch, on_conflict="slug").execute()
        print(f"[Cache] Saved {len(tags_dict)} market tags")
    except Exception as e:
        print(f"[Cache] Error bulk saving market tags: {e}")


def save_wallet_stats(wallet: str, stats: dict):
    """Save calculated wallet statistics."""
    client = get_client()
    if not client or not stats:
        return
    
    try:
        record = {
            "wallet": wallet,
            "total_pnl": stats.get("total_pnl", 0),
            "realized_pnl": stats.get("realized_pnl", 0),
            "unrealized_pnl": stats.get("unrealized_pnl", 0),
            "volume": stats.get("volume", 0),
            "roi": stats.get("roi", 0),
            "rank": stats.get("rank") if stats.get("rank") != "N/A" else None,
            "wins": stats.get("wins", 0),
            "losses": stats.get("losses", 0),
            "win_rate": stats.get("win_rate", 0),
            "markets_traded": stats.get("markets_traded", 0),
            "total_trades": stats.get("total_trades", 0),
            "avg_bet_size": stats.get("avg_bet_size", 0),
            "avg_trade_size": stats.get("avg_trade_size", 0),
            "days_active": stats.get("days_active", 0),
            "trades_per_day": stats.get("trades_per_day", 0),
            "realized_1d": stats.get("realized_1d", 0),
            "realized_7d": stats.get("realized_7d", 0),
            "realized_30d": stats.get("realized_30d", 0),
            "calculated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        client.table("wallet_stats").upsert(record, on_conflict="wallet").execute()
        print(f"[Cache] Saved stats for {wallet[:10]}...")
    except Exception as e:
        print(f"[Cache] Error saving wallet stats: {e}")


def save_price_tiers(wallet: str, tiers: list):
    """Save price tier analysis for a wallet."""
    client = get_client()
    if not client or not tiers:
        return
    
    try:
        records = []
        for tier in tiers:
            records.append({
                "wallet": wallet,
                "tier": tier.get("tier", ""),
                "positions": tier.get("positions", 0),
                "pct_of_total": tier.get("pct_of_total", 0),
                "win_rate": tier.get("win_rate", 0),
                "total_pnl": tier.get("total_pnl", 0),
                "calculated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
        
        # Delete existing tiers for this wallet first, then insert
        client.table("wallet_price_tiers").delete().eq("wallet", wallet).execute()
        if records:
            client.table("wallet_price_tiers").insert(records).execute()
        print(f"[Cache] Saved {len(records)} price tiers for {wallet[:10]}...")
    except Exception as e:
        print(f"[Cache] Error saving price tiers: {e}")


def save_categories(wallet: str, categories: list):
    """Save category performance for a wallet."""
    client = get_client()
    if not client or not categories:
        return
    
    try:
        records = []
        for cat in categories:
            records.append({
                "wallet": wallet,
                "category": cat.get("category", "Unknown"),
                "pct_volume": cat.get("pct_volume", 0),
                "pnl": cat.get("pnl", 0),
                "calculated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
        
        # Delete existing categories for this wallet first, then insert
        client.table("wallet_categories").delete().eq("wallet", wallet).execute()
        if records:
            client.table("wallet_categories").insert(records).execute()
        print(f"[Cache] Saved {len(records)} categories for {wallet[:10]}...")
    except Exception as e:
        print(f"[Cache] Error saving categories: {e}")


def save_hold_times(wallet: str, hold_times: dict):
    """Save hold time analysis for a wallet."""
    client = get_client()
    if not client or not hold_times:
        return
    
    try:
        record = {
            "wallet": wallet,
            "avg_minutes": hold_times.get("avg_minutes", 0),
            "avg_hours": hold_times.get("avg_hours", 0),
            "min_minutes": hold_times.get("min_minutes", 0),
            "calculated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        client.table("wallet_hold_times").upsert(record, on_conflict="wallet").execute()
        print(f"[Cache] Saved hold times for {wallet[:10]}...")
    except Exception as e:
        print(f"[Cache] Error saving hold times: {e}")


def save_leaderboard(entries: list, time_period: str = "all"):
    """Save leaderboard entries for a specific time period."""
    client = get_client()
    if not client or not entries:
        return
    
    try:
        # Deduplicate by wallet (keep first occurrence which has best rank)
        seen_wallets = set()
        records = []
        for entry in entries:
            wallet = entry.get("proxyWallet") or entry.get("user", "")
            if not wallet or wallet in seen_wallets:
                continue
            seen_wallets.add(wallet)
            records.append({
                "wallet": wallet,
                "username": entry.get("userName", ""),
                "time_period": time_period,
                "rank": int(entry.get("rank", 0)) if entry.get("rank") else None,
                "pnl": float(entry.get("pnl", 0)),
                "volume": float(entry.get("vol", 0)),
                "markets_traded": int(entry.get("traded", 0)) if entry.get("traded") else 0,
                "num_trades": int(entry.get("numTrades", 0)) if entry.get("numTrades") else 0,
                "profit_trades": int(entry.get("profitTrades", 0)) if entry.get("profitTrades") else 0,
                "loss_trades": int(entry.get("lossTrades", 0)) if entry.get("lossTrades") else 0,
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
        
        BATCH_SIZE = 100
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            client.table("leaderboard_rankings").upsert(batch, on_conflict="wallet,time_period").execute()
        print(f"[Cache] Saved {len(records)} leaderboard entries ({time_period})")
    except Exception as e:
        print(f"[Cache] Error saving leaderboard: {e}")


def save_wallet_leaderboard_stats(wallet: str, lb_data: dict):
    """Save leaderboard stats for a wallet across all time periods."""
    client = get_client()
    if not client or not lb_data:
        return
    
    try:
        for time_period, entries in lb_data.items():
            if entries and len(entries) > 0:
                entry = entries[0]
                record = {
                    "wallet": wallet,
                    "username": entry.get("userName", ""),
                    "time_period": time_period,
                    "rank": int(entry.get("rank", 0)) if entry.get("rank") else None,
                    "pnl": float(entry.get("pnl", 0)),
                    "volume": float(entry.get("vol", 0)),
                    "markets_traded": int(entry.get("traded", 0)) if entry.get("traded") else 0,
                    "num_trades": int(entry.get("numTrades", 0)) if entry.get("numTrades") else 0,
                    "profit_trades": int(entry.get("profitTrades", 0)) if entry.get("profitTrades") else 0,
                    "loss_trades": int(entry.get("lossTrades", 0)) if entry.get("lossTrades") else 0,
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
                client.table("leaderboard_rankings").upsert(record, on_conflict="wallet,time_period").execute()
        print(f"[Cache] Saved leaderboard rankings for {wallet[:10]}...")
    except Exception as e:
        print(f"[Cache] Error saving wallet leaderboard stats: {e}")


def save_open_positions(wallet: str, positions: list):
    """Save current open positions for a wallet."""
    client = get_client()
    if not client:
        return
    
    try:
        # First, remove old open positions for this wallet (they may have closed)
        client.table("open_positions").delete().eq("wallet", wallet).execute()
        
        if not positions:
            print(f"[Cache] No open positions for {wallet[:10]}...")
            return
        
        records = []
        for p in positions:
            pos_id = f"{wallet}_{p.get('conditionId', '')}_{p.get('outcome', '')}"
            records.append({
                "id": pos_id,
                "wallet": wallet,
                "condition_id": p.get("conditionId", ""),
                "slug": p.get("slug", ""),
                "title": p.get("title", ""),
                "outcome": p.get("outcome", ""),
                "size": float(p.get("size", 0)),
                "avg_price": float(p.get("avgPrice", 0)),
                "current_value": float(p.get("currentValue", 0)),
                "cash_pnl": float(p.get("cashPnl", 0)),
                "realized_pnl": float(p.get("realizedPnl", 0)),
                "raw_data": p,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
        
        BATCH_SIZE = 500
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            client.table("open_positions").insert(batch).execute()
        
        print(f"[Cache] Saved {len(positions)} open positions for {wallet[:10]}...")
    except Exception as e:
        print(f"[Cache] Error saving open positions: {e}")


def save_position_snapshot(wallet: str, positions: list):
    """Save a snapshot of positions for historical tracking."""
    client = get_client()
    if not client or not positions:
        return
    
    try:
        records = []
        snapshot_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for p in positions:
            records.append({
                "wallet": wallet,
                "condition_id": p.get("conditionId", ""),
                "outcome": p.get("outcome", ""),
                "size": float(p.get("size", 0)),
                "avg_price": float(p.get("avgPrice", 0)),
                "cash_pnl": float(p.get("cashPnl", 0)),
                "snapshot_at": snapshot_time
            })
        
        BATCH_SIZE = 500
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            client.table("position_snapshots").insert(batch).execute()
        
        print(f"[Cache] Saved position snapshot ({len(positions)} positions) for {wallet[:10]}...")
    except Exception as e:
        print(f"[Cache] Error saving position snapshot: {e}")
