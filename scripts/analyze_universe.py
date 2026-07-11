"""Universe analysis: does mean-reversion work on SUB-GROUPS of the 80
large-cap universe? The aggregate OOS failed, but the edge may live in
specific sectors / volatility buckets. This isolates WHERE (if anywhere)
the strategy has positive expectancy.

Uses the daily proxy backtest (same engine) over the FULL cached period
(dev+OOS combined) so each sector has enough trades for a significance
test. Pure analysis, no new strategy logic.
"""
from __future__ import annotations
import glob, os, sys
from pathlib import Path
import pandas as pd, numpy as np
ROOT = Path(r"C:\Users\diego\Desktop\Progetti\quant")
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from src.config import load_settings
from src.strategy.signals import generate_entry_signal
from src.strategy.risk import compute_position, alpaca_round_trip_cost
from src.strategy.filters import compute_adx
from src.backtest.engine import simulate_trade, TradeResult, ExitReason
from src.backtest.oos import significance

CACHE = ROOT / "data" / "cache"

# sector map from universe.py ordering
SECTORS = {
 "Tech":["AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","ORCL","CRM","ADBE","CSCO","IBM","INTC","AMD","QCOM","AVGO","TXN","MU","NOW","PANW"],
 "Financials":["JPM","BAC","WFC","C","GS","MS","BLK","SCHW","AXP","USB","PNC","TFC","COF","SPGI","ICE"],
 "Healthcare":["JNJ","UNH","PFE","ABBV","MRK","LLY","TMO","DHR","ABT","BMY","AMGN","GILD","CVS","CI","ELV"],
 "Consumer":["WMT","PG","KO","PEP","MCD","NKE","SBUX","COST","HD","LOW"],
 "Energy":["XOM","CVX","COP","SLB","EOG"],
 "Industrials":["BA","CAT","HON","RTX","DE"],
 "Materials":["LIN","APD","FCX"],
 "Utilities":["NEE","DUK","SO"],
 "RealEstate":["PLD","AMT"],
 "Telecom":["VZ","T"],
}

def _load(p):
    df=pd.read_parquet(p)
    if isinstance(df.columns,pd.MultiIndex): df.columns=[c[0] for c in df.columns]
    df=df.rename(columns={"Date":"date"}); df["date"]=pd.to_datetime(df["date"]).dt.date
    return df.sort_values("date").reset_index(drop=True)[["date","open","high","low","close"]]

def trades_for_file(path, st, ex):
    df=_load(path)
    if len(df)<60: return []
    out=[]; adx=compute_adx(df,period=14)
    adx_i={i:(float(v) if pd.notna(v) else None) for i,v in enumerate(adx)}
    for i in range(1,len(df)):
        pc=float(df.iloc[i-1]["close"])
        sig=generate_entry_signal(df.iloc[:i+1],prev_close=pc,gap_min_pct=st.gap_min_pct,
            gap_max_pct=st.gap_max_pct,opening_range_bars=1,confirmation_bars=1)
        if sig.action.value=="FLAT" or sig.bar_index is None: continue
        if i+1>=len(df): continue
        ep=float(df.iloc[i+1]["open"])
        if (adx_i.get(i) or 0)>25.0: continue
        oh=float(df.iloc[i]["high"]); ol=float(df.iloc[i]["low"]); atr=max(oh-ol,0.01)
        plan=compute_position(direction=sig.action.value,entry_price=ep,opening_range_high=oh,
            opening_range_low=ol,prev_close=pc,capital=ex.initial_capital,risk_per_trade=ex.risk_per_trade,
            atr=atr,atr_target=0.5,min_stop_distance_pct=0.001,max_position_size=0.95,
            partial_tp_frac=0.5,time_stop_bars=None,sl_atr_multiple=2.0)
        xc=float(df.iloc[i+1]["close"])
        r=simulate_trade(plan,pd.DataFrame({"close":[xc]}),entry_bar_index=i+1,signal_bar_index=i)
        out.append(TradeResult(r.pnl*plan.size-alpaca_round_trip_cost(plan.size,ep),r.exit_reason,r.exit_price,r.bars_held,r.entry_bar_index,r.signal_bar_index))
    return out

def main():
    s=load_settings(); st,ex=s.strategy,s.execution
    files={os.path.basename(f).replace(".parquet","").upper():f for f in glob.glob(str(CACHE/"*.parquet")) if not os.path.basename(f).startswith("_")}
    by_sector={}
    for sec,tickers in SECTORS.items():
        tr=[]
        for t in tickers:
            if t in files: tr.extend(trades_for_file(files[t],st,ex))
        if tr: by_sector[sec]=tr
    print(f"{'SECTOR':<12}{'n':>6}{'Sharpe':>9}{'p':>7}{'PF':>7}{'win%':>7}")
    for sec,tr in sorted(by_sector.items(), key=lambda kv: -significance(kv[1],n_bootstrap=200,seed=5).sharpe):
        sig=significance(tr,n_bootstrap=200,seed=5)
        pnls=np.array([t.pnl for t in tr])
        pf=(pnls[pnls>0].sum())/(-pnls[pnls<0].sum()) if (pnls<0).any() else float('nan')
        win=(pnls>0).mean()*100
        flag=" <-- POSITIVE" if (sig.sharpe>0 and sig.p_value<0.05) else ""
        print(f"{sec:<12}{len(tr):>6}{sig.sharpe:>+9.2f}{sig.p_value:>7.3f}{pf:>7.2f}{win:>7.1f}{flag}")

if __name__=="__main__":
    main()
