
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from .okx import OkxClient

# ---------------- Utilities ----------------

def _f(x):
    try:
        return float(x)
    except Exception:
        return 0.0

def ema(arr: List[float], period: int) -> List[float]:
    if not arr:
        return []
    k = 2/(period+1)
    out = [arr[0]]
    for i in range(1, len(arr)):
        out.append(arr[i]*k + out[-1]*(1-k))
    return out

def atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
    trs = []
    for i in range(len(close)):
        if i == 0:
            trs.append(high[i] - low[i])
        else:
            trs.append(max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1])))
    out = []
    s = 0.0
    for i, t in enumerate(trs):
        s += t
        if i < period:
            out.append(s/(i+1))
        else:
            s = out[-1]*(period-1)/period + t/period
            out.append(s)
    return out

# pivots (swing points)
def pivots(h: List[float], l: List[float], left: int = 2, right: int = 2) -> Tuple[List[bool], List[bool]]:
    n = len(h)
    ph = [False]*n
    pl = [False]*n
    for i in range(left, n-right):
        ph[i] = all(h[i] > h[i-k-1] for k in range(left)) and all(h[i] >= h[i+k+1] for k in range(right))
        pl[i] = all(l[i] < l[i-k-1] for k in range(left)) and all(l[i] <= l[i+k+1] for k in range(right))
    return ph, pl

def last_swing_levels(h: List[float], l: List[float]) -> Tuple[Optional[float], Optional[float]]:
    ph, pl = pivots(h, l, 2, 2)
    last_h = last_l = None
    for i in range(len(h)-1, -1, -1):
        if last_h is None and ph[i]:
            last_h = h[i]
        if last_l is None and pl[i]:
            last_l = l[i]
        if last_h is not None and last_l is not None:
            break
    return last_h, last_l

# candle patterns (minimalistic set for confirmation)
def bullish_engulf(o1, c1, o2, c2):
    return (c1 < o1) and (c2 > o2) and (o2 <= c1) and (c2 >= o1)

def bearish_engulf(o1, c1, o2, c2):
    return (c1 > o1) and (c2 < o2) and (o2 >= c1) and (c2 <= o1)

def bull_pin(o, h, l, c):
    body = abs(c - o)
    lower = (min(o, c) - l)
    rng = max(h - l, 1e-9)
    return (c > o) and (lower > 2*body) and (c > l + 0.6*rng)

def bear_pin(o, h, l, c):
    body = abs(c - o)
    upper = (h - max(o, c))
    rng = max(h - l, 1e-9)
    return (c < o) and (upper > 2*body) and (c < h - 0.6*rng)

# determine a key zone around last swing with ATR-based width
def compute_key_zones(h: List[float], l: List[float], c: List[float], atr14: float) -> Dict[str, Tuple[float,float]]:
    sh, sl = last_swing_levels(h, l)
    zones = {}
    if sl is not None:
        width = max( (h[-1]-l[-1])*0.5, atr14*0.75 )
        zones["long_zone"] = (sl - width*0.5, sl + width*0.5)
    if sh is not None:
        width = max( (h[-1]-l[-1])*0.5, atr14*0.75 )
        zones["short_zone"] = (sh - width*0.5, sh + width*0.5)
    return zones

def in_zone(price: float, zone: Tuple[float,float], tol: float = 0.25) -> bool:
    lo, hi = zone
    return (price >= lo*(1 - 1e-12) and price <= hi*(1 + 1e-12))

# ---------------- Data access ----------------

async def fetch_candles(inst_id: str, bar: str, limit: int = 150) -> Dict:
    c = OkxClient()
    try:
        return await c.candles(inst_id, bar, limit)
    finally:
        await c.close()

async def fetch_tickers(inst_type: str = "SPOT") -> Dict:
    c = OkxClient()
    try:
        return await c.tickers(inst_type)
    finally:
        await c.close()

# ---------------- Core evaluation (NEW system: EMA21/55/144; 定势-找位-信号) ----------------

def evaluate_custom(inst_id: str, bar: str, raw_base: Dict, raw_trend: Dict,
                    risk_percent: float = 2.0, funds_total: float = 694.0, funds_split: int = 7,
                    leverage: float = 5.0, exclude_btc_in_screen: bool = True) -> Dict:
    if exclude_btc_in_screen and inst_id.upper().startswith("BTC-"):
        return {"inst_id": inst_id, "bar": bar, "side": "flat", "reason": "excluded_by_policy (BTC)"}

    rb = list(reversed(raw_base.get("data", [])))
    rt = list(reversed(raw_trend.get("data", [])))
    if len(rb) < 50 or len(rt) < 50:
        return {"inst_id": inst_id, "bar": bar, "side": "flat", "reason": "insufficient candles"}

    # base timeframe
    ob = [_f(r[1]) for r in rb]; hb = [_f(r[2]) for r in rb]; lb = [_f(r[3]) for r in rb]; cb = [_f(r[4]) for r in rb]
    # trend timeframe
    ot = [_f(r[1]) for r in rt]; ht = [_f(r[2]) for r in rt]; lt = [_f(r[3]) for r in rt]; ct = [_f(r[4]) for r in rt]

    # indicators
    ema21_b = ema(cb, 21)[-1] if len(cb)>=21 else cb[-1]
    ema55_b = ema(cb, 55)[-1] if len(cb)>=55 else cb[-1]
    ema144_b = ema(cb,144)[-1] if len(cb)>=144 else cb[-1]

    ema21_t = ema(ct, 21)[-1] if len(ct)>=21 else ct[-1]
    ema55_t = ema(ct, 55)[-1] if len(ct)>=55 else ct[-1]
    ema144_t= ema(ct,144)[-1] if len(ct)>=144 else ct[-1]

    atr14_b = atr(hb, lb, cb, 14)[-1] if len(cb)>=14 else max(hb[-1]-lb[-1], 1e-9)
    price   = cb[-1]

    # 定势（趋势过滤）
    trend_up   = (ema21_t > ema55_t > ema144_t) and (price >= ema21_b)
    trend_down = (ema21_t < ema55_t < ema144_t) and (price <= ema21_b)
    trend_flag = "up" if trend_up else ("down" if trend_down else "neutral")

    # 找位（关键区）
    zones = compute_key_zones(hb, lb, cb, atr14_b)
    long_zone  = zones.get("long_zone")
    short_zone = zones.get("short_zone")
    near_long  = in_zone(price, long_zone) if long_zone else False
    near_short = in_zone(price, short_zone) if short_zone else False

    # 信号（形态确认）
    if len(cb) >= 2:
        o1,c1,h1,l1 = ob[-2], cb[-2], hb[-2], lb[-2]
        o2,c2,h2,l2 = ob[-1], cb[-1], hb[-1], lb[-1]
        long_sig  = bullish_engulf(o1,c1,o2,c2) or bull_pin(o2,h2,l2,c2)
        short_sig = bearish_engulf(o1,c1,o2,c2) or bear_pin(o2,h2,l2,c2)
    else:
        long_sig = short_sig = False

    # 决策：趋势 + 找位 + 信号
    side = "flat"; reason = []
    el = eh = stop = tp1 = inval = None

    if trend_up and near_long and long_sig:
        side = "long"
        # 入场区（支持“回踩 EMA21 ± 0.25*ATR14”）
        el, eh = ema21_b - 0.25*atr14_b, ema21_b + 0.25*atr14_b
        # 止损：关键区外侧 or 最近低点 或 1*ATR 取更宽
        zone_sl = long_zone[0] if long_zone else price - atr14_b
        recent_sl = min(lb[-5:])
        stop = min(zone_sl, recent_sl, price - 1.0*atr14_b)
        # 目标/无效化
        tp1 = price + 2.0*atr14_b
        inval = ema55_b
        reason += ["trend_up EMA21>55>144", "near long key zone", "bullish confirm"]

    elif trend_down and near_short and short_sig:
        side = "short"
        el, eh = ema21_b - 0.25*atr14_b, ema21_b + 0.25*atr14_b
        zone_sl = short_zone[1] if short_zone else price + atr14_b
        recent_sl = max(hb[-5:])
        stop = max(zone_sl, recent_sl, price + 1.0*atr14_b)
        tp1 = price - 2.0*atr14_b
        inval = ema55_b
        reason += ["trend_down EMA21<55<144", "near short key zone", "bearish confirm"]
    else:
        if not (trend_up or trend_down):
            reason.append("trend_neutral_or_mixed")
        if trend_up and not near_long:
            reason.append("not_in_long_zone")
        if trend_down and not near_short:
            reason.append("not_in_short_zone")
        if (trend_up and near_long and not long_sig) or (trend_down and near_short and not short_sig):
            reason.append("no_candle_confirmation")

    # 风控与仓位（2% 风险）
    margin_cap   = funds_total / max(1, funds_split)
    notional_cap = margin_cap * max(1.0, leverage)
    entry_price  = (el + eh) / 2 if (el and eh) else price
    risk_per_unit = abs(entry_price - stop) if stop is not None else max(atr14_b, 1e-9)
    qty_by_risk   = (funds_total * (risk_percent/100.0)) / max(risk_per_unit, 1e-9)
    qty_by_margin = notional_cap / max(price, 1e-9)
    position_qty  = max(0.0, min(qty_by_risk, qty_by_margin)) if side in ("long","short") else 0.0

    return {
        "inst_id": inst_id, "bar": bar, "side": side,
        "entry_zone": [round(el,6) if el else None, round(eh,6) if eh else None],
        "entry_price_est": round(entry_price,6),
        "stop_loss": round(stop,6) if stop else None,
        "take_profit1": round(tp1,6) if tp1 else None,
        "invalidation": round(inval,6) if inval else None,
        "signals": {
            "system": "intraday.v1 (EMA21/55/144 · trend-zone-signal)",
            "trend": {"trend": trend_flag, "ema21_t": round(ema21_t,6), "ema55_t": round(ema55_t,6), "ema144_t": round(ema144_t,6)},
            "zones": {"long_zone": list(long_zone) if long_zone else None, "short_zone": list(short_zone) if short_zone else None},
            "confirm": {"bullish": bool(long_sig), "bearish": bool(short_sig)}
        },
        "indicators": {
            "ema21_base": round(ema21_b,6), "ema55_base": round(ema55_b,6), "ema144_base": round(ema144_b,6),
            "atr14_base": round(atr14_b,6)
        },
        "risk": {
            "funds_total": funds_total, "funds_split": funds_split, "leverage": leverage,
            "risk_percent": risk_percent, "position_qty": round(position_qty,6)
        },
        "reasoning": ", ".join(reason) if reason else "",
        "version": "custom-intraday-ema21-55-144.v1"
    }

# ---------------- Batch scan (top gainers) ----------------

async def scan_top(inst_type: str = "SPOT", top: int = 5, bar: str = "15m", trend_bar: str = "1H", limit: int = 150,
                   exclude_btc_in_screen: bool = True, funds_total: float = 694.0, funds_split: int = 7,
                   leverage: float = 5.0, risk_percent: float = 2.0) -> Dict:
    ticks = await fetch_tickers(inst_type)
    rows = ticks.get("data", [])
    items = []
    for r in rows:
        inst = r.get("instId") or r.get("inst_id")
        if not inst:
            continue
        if exclude_btc_in_screen and inst.upper().startswith("BTC-"):
            continue
        last = _f(r.get("last", 0)); open24 = _f(r.get("open24h", 0))
        pct = ((last - open24)/open24*100.0) if open24 else 0.0
        items.append((inst, pct))
    items.sort(key=lambda x: x[1], reverse=True)
    selected = [x[0] for x in items[:max(1, top)]]

    table = []
    for inst_id in selected:
        raw_b = await fetch_candles(inst_id, bar, limit)
        raw_t = await fetch_candles(inst_id, trend_bar, limit)
        table.append(evaluate_custom(inst_id, bar, raw_b, raw_t, risk_percent, funds_total, funds_split, leverage, exclude_btc_in_screen))

    return {"selected": selected, "table": table}
