"""
Backtest copy trading - Uses leaderboard PnL (Polymarket's calculation).
"""
import sys
sys.path.insert(0, ".")
from src import db_cache

COPY_PCT = 0.03
MAX_BET = 500

def backtest_wallet(wallet, client):
    """Calculate copy-trade PnL using leaderboard data."""
    
    # Get wallet stats with leaderboard PnL
    stats = client.table("wallet_stats").select("lb_pnl, volume").eq("wallet", wallet).execute()
    if not stats.data:
        return None
    
    lb_pnl = float(stats.data[0].get("lb_pnl") or 0)
    volume = float(stats.data[0].get("volume") or 0)
    
    if volume <= 0:
        return None
    
    # Get trades to calculate copy size
    trades = client.table("trades").select("side, size, price").eq("wallet", wallet).execute()
    
    buy_volume = sum(
        float(t.get("size") or 0) * float(t.get("price") or 0)
        for t in trades.data if t.get("side") == "BUY"
    )
    
    if buy_volume <= 0:
        buy_volume = volume  # Fallback to leaderboard volume
    
    # Calculate copy trade results
    # ROI from actual wallet
    roi = lb_pnl / buy_volume if buy_volume > 0 else 0
    
    # Your copy size (capped at MAX_BET per trade)
    num_trades = len([t for t in trades.data if t.get("side") == "BUY"]) or 1
    avg_trade = buy_volume / num_trades
    copy_per_trade = min(avg_trade * COPY_PCT, MAX_BET)
    total_copy_invested = copy_per_trade * num_trades
    
    # Your copy PnL
    copy_pnl = total_copy_invested * roi
    
    return {
        "wallet": wallet,
        "positions_copied": num_trades,
        "total_invested": round(total_copy_invested, 2),
        "total_pnl": round(copy_pnl, 2),
        "roi_pct": round(roi * 100, 2),
        "actual_pnl": lb_pnl  # Wallet's actual PnL from leaderboard
    }

if __name__ == "__main__":
    client = db_cache.get_client()
    
    print("Testing with leaderboard PnL...")
    for name in ["benwyatt", "crag1"]:
        wallet = client.table("wallet_stats").select("wallet").eq("username", name).execute().data[0]["wallet"]
        result = backtest_wallet(wallet, client)
        if result:
            print(f"\n{name}:")
            print(f"  Actual wallet PnL: ${result['actual_pnl']:,.2f}")
            print(f"  Your copy PnL:     ${result['total_pnl']:,.2f}")
            print(f"  ROI:               {result['roi_pct']}%")
