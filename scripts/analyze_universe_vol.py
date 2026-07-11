"""Universe analysis 2: does the edge live in a VOLATILITY or GAP-SIZE
sub-group (not just sector)? Mean-reversion theory says small gaps in
low-vol names revert best. Isolate the best bucket. Same daily proxy."""
from __future__ import annotations
import glob, os, sys
from pathlib import Path
import pandas as pd, numpy as np
ROOT=Path(r"C:\Users\diego\Desktop\Progetti\quant")
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.config import load_settings
from src.strategy.signals import generate_entry_signal
from src.strategy.risk import compute_position, alpaca_round_trip_cost
from src.strategy.filters import compute_adx
from src.backtest.engine import simulate_trade, TradeResult, ExitReason
from src.backtest.oos import significance
CACHE=ROOT/"data"/"cache"

def _load(p):
    df=pd.read_parquet(p)
    if isinstance(df.columns,pd.MultiIndex): df.columns=[c[0] for c in df.columns]
    df=df.rename(columns={"Date":"date"}); df["date"]=pd.to_datetime(df["date"]).dt.date
    return df.sort_values("date").reset_index(drop=True)[["date","open","high","low","close"]]

def vol_ann(df):
    r=np.log(df["close"]/df["close"].shift()).dropna()
    return r.std()*np.sqrt(252)

def trades_for_file(path,st,ex):
    df=_load(path)
    if len(df)<60: return []
    out=[]; adx=compute_adx(df,period=14); adx_i={i:(float(v) if pd.notna(v) else None) for i,v in enumerate(adx)}
    for i in range(1,len(df)):
        pc=float(df.iloc[i-1]["close"]); gap=(df.iloc[i]["open"]-pc)/pc
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
        out.append((gap,r.pnl*plan.size-alpaca_round_trip_cost(plan.size,ep)))
    return out

def main():
    s=load_settings(); st,ex=s.strategy,s.execution
    files={os.path.basename(f).replace(".parquet","").upper():f for f in glob.glob(str(CACHE/"*.parquet")) if not os.path.basename(f).startswith("_")}
    allrows=[]
    for t,f in files.items():
        df=_load(f); v=vol_ann(df)
        for gap,pnl in trades_for_file(f,st,ex):
            allrows.append((t,v,gap,pnl))
    dfb=pd.DataFrame(allrows,columns=["ticker","vol","gap","pnl"])
    # bucket by volatility
    dfb["volbucket"]=pd.cut(dfb["vol"],[0,0.2,0.35,0.5,2.0],labels=["low<0.2","mid0.2-0.35","hi0.35-0.5","vhi>0.5"])
    dfb["gapbucket"]=pd.cut(dfb["gap"].abs(),[0,0.003,0.006,0.01,1.0],labels=["0.3-0.6%","0.6-1%","1-2%","2%+"])
    print("=== by VOLATILITY bucket ===")
    for b,sub in dfb.groupby("volbucket",observed=True):
        if len(sub)<20: print(f"  {b:<12} n={len(sub):<5} (too few)"); continue
        sig=significance([TradeResult(p,ExitReason.TP_FULL,100,3) for p in sub["pnl"]],n_bootstrap=200,seed=9)
        print(f"  {b:<12} n={len(sub):<5} Sharpe={sig.sharpe:>+.2f} p={sig.p_value:.3f}")
    print("=== by GAP bucket ===")
    for b,sub in dfb.groupby("gapbucket",observed=True):
        if len(sub)<20: print(f"  {b:<10} n={len(sub):<5} (too few)"); continue
        sig=significance([TradeResult(p,ExitReason.TP_FULL,100,3) for p in sub["pnl"]],n_bootstrap=200,seed=9)
        print(f"  {b:<10} n={len(sub):<5} Sharpe={sig.sharpe:>+.2f} p={sig.p_value:.3f}")
    # best combo: low vol + small gap
    combo=dfb[(dfb["volbucket"]=="low<0.2")&(dfb["gapbucket"]=="0.3-0.6%")]
    if len(combo)>=20:
        sig=significance([TradeResult(p,ExitReason.TP_FULL,100,3) for p in combo["pnl"]],n_bootstrap=200,seed=9)
        print(f"\n  BEST COMBO (low vol + 0.3-0.6% gap): n={len(combo)} Sharpe={sig.sharpe:>+.2f} p={sig.p_value:.3f}")
    else:
        print(f"\n  BEST COMBO too few trades: {len(combo)}")

if __name__=="__main__":
    main()
