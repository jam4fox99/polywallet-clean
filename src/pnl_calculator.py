"""
Polymarket PnL Calculator - Accurate methodology based on analysis.

Key findings from comparing our calculations to Polymarket leaderboard:
1. PnL is calculated based on RESOLUTION TIMESTAMP (when market closes), not entry time
2. Uses rolling time windows (7 days = 604800 seconds)
3. Formula: realized_pnl = (shares_held × resolution_price) + sell_revenue - total_buy_cost
4. Resolution price: $1 if outcome wins, $0 if loses
"""
import time
from datetime import datetime, timezone
from typing import Optional

# Time constants in seconds
SECONDS_1D = 86400
SECONDS_7D = 604800
SECONDS_30D = 2592000


def calculate_realized_pnl(
    closed_positions: list,
    time_window_seconds: Optional[int] = None,
    reference_time: Optional[float] = None
) -> dict:
    """
    Calculate realized PnL from closed positions using resolution timestamp.
    
    Args:
        closed_positions: List of closed position dicts with 'timestamp' and 'realizedPnl'
        time_window_seconds: Only include positions resolved within this window (e.g., 604800 for 7 days)
        reference_time: Reference timestamp for window calculation (defaults to now)
    
    Returns:
        dict with:
            - total_pnl: Total realized PnL
            - positions_count: Number of positions in window
            - wins: Count of profitable positions
            - losses: Count of losing positions
            - win_rate: Win percentage
    """
    if reference_time is None:
        reference_time = time.time()
    
    cutoff_time = reference_time - time_window_seconds if time_window_seconds else 0
    
    total_pnl = 0.0
    wins = 0
    losses = 0
    positions_in_window = []
    
    for pos in closed_positions:
        resolution_ts = pos.get("timestamp", 0)
        
        # Filter by time window using resolution timestamp
        if time_window_seconds and resolution_ts < cutoff_time:
            continue
            
        pnl = float(pos.get("realizedPnl", 0) or pos.get("realized_pnl", 0))
        total_pnl += pnl
        positions_in_window.append(pos)
        
        if pnl > 0:
            wins += 1
        elif pnl < 0:
            losses += 1
    
    total_positions = wins + losses
    win_rate = round((wins / total_positions) * 100, 2) if total_positions > 0 else 0
    
    return {
        "total_pnl": round(total_pnl, 2),
        "positions_count": len(positions_in_window),
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate
    }


def calculate_time_period_pnl(closed_positions: list, reference_time: Optional[float] = None) -> dict:
    """
    Calculate PnL for all standard time periods (1d, 7d, 30d, all-time).
    
    Args:
        closed_positions: List of closed position dicts
        reference_time: Reference timestamp (defaults to now)
    
    Returns:
        dict with realized_1d, realized_7d, realized_30d, realized_all
    """
    if reference_time is None:
        reference_time = time.time()
    
    pnl_1d = calculate_realized_pnl(closed_positions, SECONDS_1D, reference_time)
    pnl_7d = calculate_realized_pnl(closed_positions, SECONDS_7D, reference_time)
    pnl_30d = calculate_realized_pnl(closed_positions, SECONDS_30D, reference_time)
    pnl_all = calculate_realized_pnl(closed_positions, None, reference_time)
    
    return {
        "realized_1d": pnl_1d["total_pnl"],
        "realized_7d": pnl_7d["total_pnl"],
        "realized_30d": pnl_30d["total_pnl"],
        "realized_all": pnl_all["total_pnl"],
        "positions_1d": pnl_1d["positions_count"],
        "positions_7d": pnl_7d["positions_count"],
        "positions_30d": pnl_30d["positions_count"],
        "positions_all": pnl_all["positions_count"],
        "wins": pnl_all["wins"],
        "losses": pnl_all["losses"],
        "win_rate": pnl_all["win_rate"]
    }


def calculate_unrealized_pnl(open_positions: list) -> dict:
    """
    Calculate unrealized PnL from open positions.
    
    Args:
        open_positions: List of open position dicts
    
    Returns:
        dict with unrealized_pnl and position details
    """
    total_unrealized = 0.0
    total_cash_pnl = 0.0
    
    for pos in open_positions:
        # cashPnl = current_value - cost_basis (paper profit/loss)
        cash_pnl = float(pos.get("cashPnl", 0) or pos.get("cash_pnl", 0))
        total_cash_pnl += cash_pnl
        
        # Some APIs use unrealizedPnl directly
        unrealized = float(pos.get("unrealizedPnl", 0) or pos.get("unrealized_pnl", 0))
        if unrealized:
            total_unrealized += unrealized
    
    # Use whichever is available
    final_unrealized = total_unrealized if total_unrealized else total_cash_pnl
    
    return {
        "unrealized_pnl": round(final_unrealized, 2),
        "open_positions_count": len(open_positions)
    }


def calculate_total_pnl(
    closed_positions: list,
    open_positions: list,
    time_window_seconds: Optional[int] = None,
    reference_time: Optional[float] = None
) -> dict:
    """
    Calculate total PnL (realized + unrealized).
    
    This matches Polymarket's leaderboard calculation methodology.
    
    Args:
        closed_positions: List of closed position dicts
        open_positions: List of open position dicts
        time_window_seconds: Time window for realized PnL calculation
        reference_time: Reference timestamp
    
    Returns:
        Comprehensive PnL breakdown
    """
    realized = calculate_realized_pnl(closed_positions, time_window_seconds, reference_time)
    unrealized = calculate_unrealized_pnl(open_positions)
    
    total_pnl = realized["total_pnl"] + unrealized["unrealized_pnl"]
    
    return {
        "total_pnl": round(total_pnl, 2),
        "realized_pnl": realized["total_pnl"],
        "unrealized_pnl": unrealized["unrealized_pnl"],
        "positions_count": realized["positions_count"],
        "open_positions_count": unrealized["open_positions_count"],
        "wins": realized["wins"],
        "losses": realized["losses"],
        "win_rate": realized["win_rate"]
    }


def calculate_daily_breakdown(closed_positions: list) -> list:
    """
    Calculate PnL broken down by day (based on resolution date).
    
    Args:
        closed_positions: List of closed position dicts
    
    Returns:
        List of dicts with date, positions, pnl sorted by date descending
    """
    daily_pnl = {}
    
    for pos in closed_positions:
        resolution_ts = pos.get("timestamp", 0)
        if not resolution_ts:
            continue
            
        # Convert to date string
        date_str = datetime.fromtimestamp(resolution_ts, tz=timezone.utc).strftime("%Y-%m-%d")
        pnl = float(pos.get("realizedPnl", 0) or pos.get("realized_pnl", 0))
        
        if date_str not in daily_pnl:
            daily_pnl[date_str] = {"date": date_str, "positions": 0, "pnl": 0.0}
        
        daily_pnl[date_str]["positions"] += 1
        daily_pnl[date_str]["pnl"] += pnl
    
    # Sort by date descending
    result = sorted(daily_pnl.values(), key=lambda x: x["date"], reverse=True)
    
    # Round PnL values
    for day in result:
        day["pnl"] = round(day["pnl"], 2)
    
    return result


def estimate_position_pnl(
    avg_price: float,
    total_bought: float,
    resolution_price: float = 1.0,
    shares_sold_early: float = 0.0,
    sell_revenue: float = 0.0
) -> float:
    """
    Estimate PnL for a position given entry details and outcome.
    
    Formula:
        shares = total_bought / avg_price
        shares_held = shares - shares_sold_early
        payout = shares_held × resolution_price
        pnl = payout + sell_revenue - total_bought
    
    Args:
        avg_price: Average entry price (0-1)
        total_bought: Total USD invested
        resolution_price: 1.0 if won, 0.0 if lost
        shares_sold_early: Number of shares sold before resolution
        sell_revenue: Revenue from early sales
    
    Returns:
        Estimated PnL
    """
    if avg_price <= 0 or total_bought <= 0:
        return 0.0
    
    shares = total_bought / avg_price
    shares_held = shares - shares_sold_early
    payout = shares_held * resolution_price
    pnl = payout + sell_revenue - total_bought
    
    return round(pnl, 2)


# SQL queries for Supabase to calculate PnL correctly
SQL_QUERIES = {
    "weekly_pnl": """
        SELECT 
            wallet,
            SUM(realized_pnl::numeric) as realized_7d,
            COUNT(*) as positions_count
        FROM closed_positions
        WHERE wallet = :wallet
          AND to_timestamp(timestamp) >= NOW() - INTERVAL '7 days'
        GROUP BY wallet
    """,
    
    "daily_breakdown": """
        SELECT 
            DATE(to_timestamp(timestamp)) as date,
            COUNT(*) as positions,
            SUM(realized_pnl::numeric) as daily_pnl
        FROM closed_positions
        WHERE wallet = :wallet
        GROUP BY DATE(to_timestamp(timestamp))
        ORDER BY date DESC
    """,
    
    "time_period_pnl": """
        SELECT 
            wallet,
            SUM(CASE WHEN to_timestamp(timestamp) >= NOW() - INTERVAL '1 day' 
                THEN realized_pnl::numeric ELSE 0 END) as realized_1d,
            SUM(CASE WHEN to_timestamp(timestamp) >= NOW() - INTERVAL '7 days' 
                THEN realized_pnl::numeric ELSE 0 END) as realized_7d,
            SUM(CASE WHEN to_timestamp(timestamp) >= NOW() - INTERVAL '30 days' 
                THEN realized_pnl::numeric ELSE 0 END) as realized_30d,
            SUM(realized_pnl::numeric) as realized_all
        FROM closed_positions
        WHERE wallet = :wallet
        GROUP BY wallet
    """
}
