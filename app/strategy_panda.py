from __future__ import annotations
from typing import List, Dict
from .okx import OkxClient

# -------- 工具 --------
def _to_f(v):
    try: return float(v)
    except: return 0.0

def ema(arr: List[float], period: int) -> List[float]:
    if not arr: return []
    k = 2/(period+1)
    out = [arr[0]]
    for i in range(1,len(arr)):
        out.append(arr[i]*k + out[-1]*(1-k))
    return out

def atr(high: List[float], low: List[float], close: List[float], period: int=14) -> List[float]:
    trs=[]
    for i in range(len(close)):
        if i==0: trs.append(high[i]-low[i])
        else:
            trs.append(max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1])))
    out=[]; s=0.0
    for i,t in enumerate(trs):
        s+=t
        if i<period: out.append(s/(i+1))
        else:
            s = out[-1]*(period-1)/period + t/period
            out.append(s)
    return out

def pivots(h: List[float], l: List[float], left: int=2, right: int=2):
    n=len(h); ph=[False]*n; pl=[False]*n
    for i in range(left, n-right):
        ph[i] = all(h[i] > h[i-k-1] for k in range(left)) and all(h[i] >= h[i+k+1] for k in range(right))
        pl[i] = all(l[i] < l[i-k-1] for k in range(left)) and all(l[i] <= l[i+k+1] for k in range(right))
    return ph, pl

def last_swing_levels(h: List[float], l: List[float]):
    ph, pl = pivots(h,l)
    last_h=last_l=None
    for i in range(len(h)-1,-1,-1):
        if last_h is None and ph[i]: last_h=h[i]
        if last_l is None and pl[i]: last_l=l[i]
        if last_h is not None and last_l is not None: break
    return last_h, last_l

# -------- 12 金K（常用子集） --------
def is_bull_engulf(o1,c1,o2,c2): return (c1<o1) and (c2>o2) and (o2<=c1) and (c2>=o1)
def is_bear_engulf(o1,c1,o2,c2): return (c1>o1) and (c2<o2) and (o2>=c1) and (c2<=o1)
def is_inside_bar(h1,l1,h2,l2):  return (h2<=h1) and (l2>=l1)
def is_outside_bar(h1,l1,h2,l2): return (h2>=h1) and (l2<=l1)

def is_bull_pin(o,h,l,c):
    body=abs(c-o); lower=(o if c>=o else c)-l; rng=max(h-l,1e-8)
    return (lower>2*body) and (c>o) and (c>l+0.6*rng)

def is_bear_pin(o,h,l,c):
    body=abs(c-o); upper=h-(c if c>=o else o); rng=max(h-l,1e-8)
    return (upper>2*body) and (c<o) and (c<h-0.6*rng)

def is_piercing(o1,c1,o2,c2,h2,l2):
    return (c1<o1) and (c2>o2) and (o2<l2+0.2*(h2-l2)) and (c2>(o1+c1)/2)

def is_dark_cloud(o1,c1,o2,c2,h2,l2):
    return (c1>o1) and (c2<o2) and (o2>l2+0.8*(h2-l2)) and (c2<(o1+c1)/2)

def three_white_soldiers(c,o):
    return len(c)>=3 and (c[-3]>o[-3] and c[-2]>o[-2] and c[-1]>o[-1]) and (c[-1]>c[-2]>c[-3])

def three_black_crows(c,o):
    return len(c)>=3 and (c[-3]<o[-3] and c[-2]<o[-2] and c[-1]<o[-1]) and (c[-1]<c[-2]<c[-3])

# -------- 数据获取 --------
async def fetch_candles(inst_id: str, bar: str, limit: int=150) -> Dict:
    client=OkxClient()
    try:
        return await client.candles(inst_id, bar, limit)
    finally:
        await client.close()

async def fetch_tickers(inst_type: str="SPOT") -> Dict:
    client=OkxClient()
    try:
        return await client.tickers(inst_type)
    finally:
        await client.close()

# -------- 评估核心 --------
def evaluate_panda(inst_id: str, bar: str, raw_base: Dict, raw_trend: Dict,
                   risk_percent: float=2.0, funds_total: float=694.0, funds_split: int=7,
                   leverage: float=5.0, exclude_btc_in_screen: bool=True) -> Dict:
    if exclude_btc_in_screen and inst_id.upper().startswith("BTC-"):
        return {"inst_id":inst_id,"bar":bar,"side":"flat","reason":"excluded_by_policy (BTC)","policy":{"exclude_btc_in_screen":True}}

    rb=list(reversed(raw_base.get("data",[])))
    rt=list(reversed(raw_trend.get("data",[])))
    if len(rb)<50 or len(rt)<50:
        return {"inst_id":inst_id,"bar":bar,"side":"flat","reason":"insufficient candles"}

    ob=[_to_f(r[1]) for r in rb]; hb=[_to_f(r[2]) for r in rb]; lb=[_to_f(r[3]) for r in rb]; cb=[_to_f(r[4]) for r in rb]
    ot=[_to_f(r[1]) for r in rt]; ht=[_to_f(r[2]) for r in rt]; lt=[_to_f(r[3]) for r in rt]; ct=[_to_f(r[4]) for r in rt]

    ema20_b,ema50_b=ema(cb,20),ema(cb,50); ema20_t,ema50_t=ema(ct,20),ema(ct,50)
    atr14_b=atr(hb,lb,cb,14)

    price=cb[-1]; e20b, e50b, a14b=ema20_b[-1], ema50_b[-1], max(atr14_b[-1],1e-8)
    trend_up  = ema20_t[-1]>ema50_t[-1]
    trend_down= ema20_t[-1]<ema50_t[-1]

    sh, sl = last_swing_levels(hb,lb)
    sig={"gold12":[],"structure":{}}

    if len(cb)>=2:
        o1,c1,h1,l1=ob[-2],cb[-2],hb[-2],lb[-2]
        o2,c2,h2,l2=ob[-1],cb[-1],hb[-1],lb[-1]
        if is_bull_engulf(o1,c1,o2,c2): sig["gold12"].append("Bullish Engulfing")
        if is_bear_engulf(o1,c1,o2,c2): sig["gold12"].append("Bearish Engulfing")
        if is_inside_bar(h1,l1,h2,l2):   sig["gold12"].append("Inside Bar")
        if is_outside_bar(h1,l1,h2,l2):  sig["gold12"].append("Outside Bar")
        if is_piercing(o1,c1,o2,c2,h2,l2):   sig["gold12"].append("Piercing")
        if is_dark_cloud(o1,c1,o2,c2,h2,l2): sig["gold12"].append("Dark Cloud Cover")

    o,h,l,c=ob[-1],hb[-1],lb[-1],cb[-1]
    if is_bull_pin(o,h,l,c): sig["gold12"].append("Bullish PinBar")
    if is_bear_pin(o,h,l,c): sig["gold12"].append("Bearish PinBar")
    if three_white_soldiers(cb,ob): sig["gold12"].append("Three White Soldiers")
    if three_black_crows(cb,ob):   sig["gold12"].append("Three Black Crows")

    bos_high = (c>(sh or c)) if sh else False
    bos_low  = (c<(sl or c)) if sl else False
    sig["structure"]={"break_prev_high":bos_high, "break_prev_low":bos_low, "last_swing_high":sh, "last_swing_low":sl}

    side="flat"; reason=[]; el=eh=stop=tp1=inval=None
    if trend_up:
        if ({"Bullish Engulfing","Bullish PinBar","Piercing","Three White Soldiers"} & set(sig["gold12"])) or bos_high:
            side="long"; el,eh=e20b-0.25*a14b, e20b+0.25*a14b
            stop=min(lb[-5:]); stop=min(stop, c-1.0*a14b)
            tp1=c+2.0*a14b; inval=e50b
            reason+=["trend_up(EMA20>EMA50)","bullish_signals_or_bos"]
    elif trend_down:
        if ({"Bearish Engulfing","Bearish PinBar","Dark Cloud Cover","Three Black Crows"} & set(sig["gold12"])) or bos_low:
            side="short"; el,eh=e20b-0.25*a14b, e20b+0.25*a14b
            stop=max(hb[-5:]); stop=max(stop, c+1.0*a14b)
            tp1=c-2.0*a14b; inval=e50b
            reason+=["trend_down(EMA20<EMA50)","bearish_signals_or_bos"]
    else:
        reason.append("trend_unclear(EMA20≈EMA50)")

    margin_cap=funds_total/max(1, funds_split); notional_cap=margin_cap*max(1.0, leverage)
    entry_price=(el+eh)/2 if (el and eh) else c
    risk_per_unit=abs(entry_price - stop) if (stop is not None) else a14b
    qty_by_risk=(funds_total*(risk_percent/100.0))/max(risk_per_unit,1e-8)
    qty_by_margin=notional_cap/max(c,1e-8)
    position_qty= max(0.0, min(qty_by_risk, qty_by_margin)) if side in ("long","short") else 0.0

    return {
        "inst_id":inst_id, "bar":bar, "side":side,
        "entry_zone":[round(el,6) if el else None, round(eh,6) if eh else None],
        "entry_price_est": round(entry_price,6),
        "stop_loss": round(stop,6) if stop else None,
        "take_profit1": round(tp1,6) if tp1 else None,
        "invalidation": round(inval,6) if inval else None,
        "signals": sig,
        "indicators": {"ema20_base":round(e20b,6),"ema50_base":round(e50b,6),"atr14_base":round(a14b,6),"trend_up":bool(trend_up),"trend_down":bool(trend_down)},
        "risk": {"funds_total":funds_total, "funds_split":funds_split, "leverage":leverage, "risk_percent":risk_percent,
                 "margin_cap":round(margin_cap,6), "notional_cap":round(notional_cap,6), "risk_per_unit":round(risk_per_unit,6), "position_qty":round(position_qty,6)},
        "policy": {"exclude_btc_in_screen": bool(exclude_btc_in_screen)},
        "reasoning": ", ".join(reason) if reason else "",
        "version": "panda-164-165.v2"
    }

# -------- 批量扫描（涨幅前 N） --------
async def scan_top(inst_type: str="SPOT", top: int=5, bar: str="15m", trend_bar: str="1H", limit: int=150,
                   exclude_btc_in_screen: bool=True, funds_total: float=694.0, funds_split: int=7, leverage: float=5.0,
                   risk_percent: float=2.0) -> Dict:
    tickers = await fetch_tickers(inst_type)
    rows = tickers.get("data", [])
    items=[]
    for r in rows:
        inst_id = r.get("instId") or r.get("inst_id")
        if not inst_id: continue
        if exclude_btc_in_screen and inst_id.upper().startswith("BTC-"): continue
        last=_to_f(r.get("last",0)); open24=_to_f(r.get("open24h",0))
        pct=((last-open24)/open24*100.0) if open24 else 0.0
        items.append((inst_id, pct, last))
    items.sort(key=lambda x:x[1], reverse=True)
    selected=[it[0] for it in items[:max(1,top)]]

    table=[]
    for inst_id in selected:
        raw_b = await fetch_candles(inst_id, bar, limit)
        raw_t = await fetch_candles(inst_id, trend_bar, limit)
        table.append(evaluate_panda(inst_id, bar, raw_b, raw_t, risk_percent, funds_total, funds_split, leverage, exclude_btc_in_screen))

    return {"selected": selected, "table": table}
