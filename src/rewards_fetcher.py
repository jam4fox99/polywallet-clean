"""
Polymarket Rewards Fetcher - Detect market makers by liquidity rewards.

Uses Polymarket Data API to fetch reward transactions and identify
wallets that are earning market maker incentives.
"""
import requests
from typing import Optional
from datetime import datetime, timezone


POLYMARKET_DATA_API = "https://data-api.polymarket.com"


def fetch_wallet_rewards(wallet: str, limit: int = 500) -> list:
    """
    Fetch liquidity rewards for a wallet from Polymarket API.
    
    Args:
        wallet: Wallet address (0x prefixed)
        limit: Max number of reward transactions to fetch
    
    Returns:
        List of reward transaction dicts
    """
    url = f"{POLYMARKET_DATA_API}/activity"
    params = {
        "user": wallet,
        "type": "REWARD",
        "limit": limit,
        "sortBy": "TIMESTAMP",
        "sortDirection": "DESC"
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.ok:
            return response.json()
        else:
            print(f"Error fetching rewards for {wallet}: {response.status_code}")
            return []
    except Exception as e:
        print(f"Exception fetching rewards for {wallet}: {e}")
        return []


def calculate_reward_stats(rewards: list) -> dict:
    """
    Calculate reward statistics for market maker detection.
    
    Args:
        rewards: List of reward transactions from fetch_wallet_rewards
    
    Returns:
        dict with total_rewards, reward_count, is_market_maker, etc.
    """
    if not rewards:
        return {
            "total_rewards": 0,
            "reward_count": 0,
            "first_reward_at": None,
            "last_reward_at": None,
            "avg_daily_reward": 0,
            "is_market_maker": False
        }
    
    total = sum(float(r.get("usdcSize", 0) or 0) for r in rewards)
    
    timestamps = [r.get("timestamp", 0) for r in rewards if r.get("timestamp")]
    first_ts = min(timestamps) if timestamps else None
    last_ts = max(timestamps) if timestamps else None
    
    # Calculate average daily reward
    avg_daily = 0
    if first_ts and last_ts and first_ts != last_ts:
        days = (last_ts - first_ts) / 86400
        if days > 0:
            avg_daily = total / days
    
    # Market maker detection:
    # - Total rewards > $1,000 lifetime, OR
    # - Average daily reward > $10
    is_mm = total > 1000 or avg_daily > 10
    
    return {
        "total_rewards": round(total, 2),
        "reward_count": len(rewards),
        "first_reward_at": first_ts,
        "last_reward_at": last_ts,
        "avg_daily_reward": round(avg_daily, 2),
        "is_market_maker": is_mm
    }


def analyze_wallet_rewards(wallet: str) -> dict:
    """
    Full reward analysis for a wallet - fetch and calculate stats.
    
    Args:
        wallet: Wallet address
    
    Returns:
        Complete reward analysis dict
    """
    rewards = fetch_wallet_rewards(wallet)
    stats = calculate_reward_stats(rewards)
    
    # Add raw rewards for detailed inspection
    stats["rewards"] = rewards
    stats["wallet"] = wallet
    
    return stats


def format_reward_report(stats: dict) -> str:
    """
    Format reward stats into a readable report.
    
    Args:
        stats: Output from analyze_wallet_rewards
    
    Returns:
        Formatted string report
    """
    wallet = stats.get("wallet", "Unknown")
    total = stats.get("total_rewards", 0)
    count = stats.get("reward_count", 0)
    avg_daily = stats.get("avg_daily_reward", 0)
    is_mm = stats.get("is_market_maker", False)
    
    first_ts = stats.get("first_reward_at")
    last_ts = stats.get("last_reward_at")
    
    first_date = datetime.fromtimestamp(first_ts, tz=timezone.utc).strftime("%Y-%m-%d") if first_ts else "N/A"
    last_date = datetime.fromtimestamp(last_ts, tz=timezone.utc).strftime("%Y-%m-%d") if last_ts else "N/A"
    
    mm_status = "YES - MARKET MAKER" if is_mm else "NO - Real Trader"
    
    report = f"""
=== Liquidity Rewards Report ===
Wallet: {wallet}

Total Rewards:     ${total:,.2f}
Reward Count:      {count}
Avg Daily Reward:  ${avg_daily:,.2f}
First Reward:      {first_date}
Last Reward:       {last_date}

Market Maker?      {mm_status}
================================
"""
    return report


def prepare_rewards_for_db(wallet: str, rewards: list) -> list:
    """
    Prepare reward transactions for database insertion.
    
    Args:
        wallet: Wallet address
        rewards: Raw rewards from API
    
    Returns:
        List of dicts ready for DB insert
    """
    records = []
    for r in rewards:
        records.append({
            "wallet": wallet,
            "timestamp": r.get("timestamp"),
            "type": r.get("type", "REWARD"),
            "usdc_size": float(r.get("usdcSize", 0) or 0),
            "transaction_hash": r.get("transactionHash"),
            "condition_id": r.get("conditionId"),
            "title": r.get("title")
        })
    return records


if __name__ == "__main__":
    # Test with a sample wallet
    import sys
    
    if len(sys.argv) > 1:
        test_wallet = sys.argv[1]
    else:
        # Default test wallet (ESPORTSENTHUSIAST)
        test_wallet = "0x8c0b024c17831a0dde038547b7e791ae6a0d7aa5"
    
    print(f"Analyzing rewards for: {test_wallet}")
    stats = analyze_wallet_rewards(test_wallet)
    print(format_reward_report(stats))
    
    # Show sample rewards
    if stats["rewards"]:
        print(f"Sample rewards (first 5):")
        for r in stats["rewards"][:5]:
            date = datetime.fromtimestamp(r.get("timestamp", 0), tz=timezone.utc).strftime("%Y-%m-%d")
            amount = r.get("usdcSize", 0)
            title = r.get("title", "Unknown")[:50]
            print(f"  {date}: ${amount:.2f} - {title}")
