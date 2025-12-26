import sys
sys.path.insert(0, ".")
from src import db_cache
from src.backtest_copy import backtest_wallet
from collections import defaultdict

COPY_PCT = 0.03
MAX_BET = 500
USER_CAPITAL = 5000

client = db_cache.get_client()

def strict_bot_check(wallet):
    """VERY strict bot detection."""
    trades = client.table("trades").select("timestamp, side, size, price, condition_id").eq("wallet", wallet).limit(500).execute()
    if not trades.data or len(trades.data) < 5:
        return True, ["NoData"]
    
    buys = [t for t in trades.data if t.get("side") == "BUY" and t.get("timestamp")]
    if len(buys) < 3:
        return True, ["FewBuys"]
    
    signals = []
    timestamps = sorted([t["timestamp"] for t in buys])
    gaps = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
    avg_gap = sum(gaps) / len(gaps) if gaps else 9999
    
    # 1. Fast trading
    if avg_gap < 120:
        signals.append(f"Gap:{avg_gap:.0f}s")
    
    # 2. Same-second trades
    same_second = sum(1 for g in gaps if g == 0)
    if same_second > 2:
        signals.append(f"SameSec:{same_second}")
    
    # 3. Fast trades < 30 sec
    fast = sum(1 for g in gaps if 0 < g < 30)
    if fast > 5:
        signals.append(f"Fast:{fast}")
    
    # 4. MULTIPLE TRADES ON SAME MARKET (key fix!)
    market_counts = defaultdict(int)
    for t in buys:
        cid = t.get("condition_id")
        if cid:
            market_counts[cid] += 1
    
    max_same_market = max(market_counts.values()) if market_counts else 0
    if max_same_market >= 3:
        signals.append(f"SameMkt:{max_same_market}x")
    
    # 5. Many markets with 2+ trades (pattern of splitting)
    multi_trade_markets = sum(1 for c in market_counts.values() if c >= 2)
    if multi_trade_markets >= 3:
        signals.append(f"Split:{multi_trade_markets}mkts")
    
    return len(signals) > 0, signals

def calc_max_capital(wallet):
    trades = client.table("trades").select("condition_id, timestamp, side, size, price").eq("wallet", wallet).execute()
    closed = client.table("closed_positions").select("condition_id, timestamp").eq("wallet", wallet).execute()
    if not trades.data:
        return 0
    
    close_times = {p["condition_id"]: p["timestamp"] for p in closed.data if p.get("condition_id")}
    events = []
    for t in trades.data:
        if t.get("side") != "BUY":
            continue
        size = float(t.get("size") or 0) * float(t.get("price") or 0)
        if size <= 0:
            continue
        copy_size = min(size * COPY_PCT, MAX_BET)
        events.append((t.get("timestamp", 0), copy_size, "B"))
        close_ts = close_times.get(t.get("condition_id"), t.get("timestamp", 0) + 604800)
        events.append((close_ts, copy_size, "C"))
    
    events.sort()
    exposure = max_exp = 0
    for ts, amt, typ in events:
        exposure = exposure + amt if typ == "B" else max(0, exposure - amt)
        max_exp = max(max_exp, exposure)
    return max_exp

print("=" * 80)
print("ANALYSIS WITH STRICTER BOT DETECTION")
print("New rule: 3+ trades on same market = BOT")
print(f"Budget: ${USER_CAPITAL:,} | Strategy: {COPY_PCT*100}% copy, ${MAX_BET} max")
print("=" * 80)

wallets = client.table("wallet_stats").select("wallet, username, rank, lb_pnl, win_rate").order("rank").limit(200).execute()
print(f"Analyzing {len(wallets.data)} wallets...\n")

bots, humans = [], []

for w in wallets.data:
    wallet = w["wallet"]
    username = w.get("username") or wallet[:15]
    rank = w.get("rank", 0)
    lb_pnl = float(w.get("lb_pnl") or 0)
    
    is_bot, signals = strict_bot_check(wallet)
    max_cap = calc_max_capital(wallet)
    bt = backtest_wallet(wallet, client)
    
    result = {
        "wallet": wallet, "username": username, "rank": rank,
        "is_bot": is_bot, "signals": signals,
        "max_capital": max_cap, "fits_5k": 0 < max_cap <= USER_CAPITAL,
        "actual_pnl": lb_pnl,
        "copy_pnl": bt["total_pnl"] if bt else 0,
        "roi": bt["roi_pct"] if bt else 0,
        "win_rate": w.get("win_rate", 0)
    }
    
    (bots if is_bot else humans).append(result)

print(f"BOTS: {len(bots)} | HUMANS: {len(humans)}\n")

print("=" * 80)
print("VERIFIED HUMANS - PROFITABLE - FIT $5K:")
print("=" * 80)

good = [h for h in humans if h["fits_5k"] and h["actual_pnl"] > 0]
good.sort(key=lambda x: x["actual_pnl"], reverse=True)

if good:
    print(f"{'Rank':<6} {'Username':<20} {'Capital':<9} {'Actual PnL':<14} {'Your Copy':<12} {'ROI'}")
    print("-" * 80)
    for h in good[:20]:
        print(f"#{h['rank']:<5} {h['username'][:19]:<20} ${h['max_capital']:<8,.0f} ${h['actual_pnl']:>12,.0f} ${h['copy_pnl']:>10,.0f}  {h['roi']}%")
else:
    print("NO profitable human wallets fit $5k budget!")
    print("\nAll humans (any budget):")
    for h in sorted(humans, key=lambda x: x["actual_pnl"], reverse=True)[:10]:
        print(f"  #{h['rank']} {h['username'][:18]} - ${h['max_capital']:,.0f} cap, ${h['actual_pnl']:,.0f} PnL")

print("\n" + "=" * 80)
print("TOP BOTS (excluded):")
print("=" * 80)
bots.sort(key=lambda x: x["actual_pnl"], reverse=True)
for b in bots[:15]:
    sig = ", ".join(b["signals"][:2])
    print(f"  #{b['rank']:<4} {b['username'][:16]:<16} ${b['actual_pnl']:>12,.0f}  [{sig}]")

if good:
    print("\n" + "=" * 80)
    print("RECOMMENDATION:")
    print("=" * 80)
    best = good[0]
    print(f"\nBest HUMAN: #{best['rank']} {best['username']}")
    print(f"  Capital:     ${best['max_capital']:,.0f}")
    print(f"  Their PnL:   ${best['actual_pnl']:,.2f}")
    print(f"  Your copy:   ${best['copy_pnl']:,.2f}")
    print(f"  ROI:         {best['roi']}%")
