"""DIAGNOSIS: why does the 5-min backtest fail? Break down exit reasons
and compare WITH vs WITHOUT time-stop. Pure analysis, no new logic."""
import sys
from pathlib import Path
from collections import Counter
ROOT = Path(r"C:\Users\diego\Desktop\Progetti\quant")
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from src.config import load_settings
from src.strategy.signals import generate_entry_signal
from src.strategy.risk import compute_position, alpaca_round_trip_cost
from src.backtest.engine import simulate_trade, TradeResult
import yfinance as yf
import pandas as pd

def fetch_5min(ticker, days=59):
    df = yf.download(ticker, period=f"{days}d", interval="5m", progress=False, auto_adjust=False)
    if df.empty: return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df.reset_index(); df.columns=[str(c).lower() for c in df.columns]
    out=df[["datetime","open","high","low","close"]].copy()
    out["datetime"]=pd.to_datetime(out["datetime"]); out["day"]=out["datetime"].dt.date
    return out

settings=load_settings(); st=settings.strategy; ex=settings.execution
tickers=["AAPL","MSFT","NVDA","AMD","TSLA","AMZN","META","GOOGL"]
for ts in (None, 30):
    reasons=Counter(); pnls=[]
    for t in tickers:
        df=fetch_5min(t)
        if df.empty: continue
        days=sorted(df["day"].unique()); pc={}; last=None
        for d in days:
            g=df[df["day"]==d].sort_values("datetime")
            if last is not None: pc[d]=last
            last=float(g["close"].iloc[-1])
        for d,g in df.groupby("day"):
            g=g.sort_values("datetime").reset_index(drop=True)
            if d not in pc or len(g)<3: continue
            sig=generate_entry_signal(g,prev_close=pc[d],gap_min_pct=st.gap_min_pct,
                gap_max_pct=st.gap_max_pct,opening_range_bars=st.opening_range_bars,
                confirmation_bars=st.confirmation_bars)
            if sig.action.value=="FLAT" or sig.bar_index is None: continue
            ei=sig.bar_index+1
            if ei>=len(g): continue
            ep=float(g.iloc[ei]["open"])
            oh=float(g.iloc[:st.opening_range_bars]["high"].max())
            ol=float(g.iloc[:st.opening_range_bars]["low"].min())
            plan=compute_position(direction=sig.action.value,entry_price=ep,
                opening_range_high=oh,opening_range_low=ol,prev_close=pc[d],
                capital=ex.initial_capital,risk_per_trade=ex.risk_per_trade,atr=0.5,
                atr_target=0.5,min_stop_distance_pct=0.001,max_position_size=0.95,
                partial_tp_frac=0.5,time_stop_bars=ts)
            after=g.iloc[ei+1:].reset_index(drop=True)
            if len(after)==0: continue
            res=simulate_trade(plan,after[["close"]])
            gross=res.pnl*plan.size; cost=alpaca_round_trip_cost(plan.size,ep)
            pnls.append(gross-cost); reasons[res.exit_reason.value]+=1
    tot=sum(pnls)
    print(f"\ntime_stop={ts}: n={len(pnls)} total_pnl={tot:.0f} reasons={dict(reasons)}")
