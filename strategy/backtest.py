import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR))

import backtrader as bt
import pandas as pd
from analysis import hedge_ratio as hr
import numpy as np

DATA_DIR = ROOT_DIR / "data"
ANALYSIS_DIR = ROOT_DIR / "analysis"

class PairsTrading(bt.Strategy):
    params = (
        ('hedge_ratio', None),
        ('window', 20),
        ('entry_z_score', 2.0),
        ('exit_z_score', 0.0),
    )
    
    def __init__(self):
        self.mpc = self.datas[0]
        self.psx = self.datas[1]
        self.spread_history = []
    
    def next(self):
        
        # 1. calcola lo spread di oggi
        spread_today = np.log(self.mpc.close[0]) - (self.p.hedge_ratio * np.log(self.psx.close[0]))
        self.spread_history.append(spread_today)

        # 2. se non hai abbastanza storico, esci (non puoi calcolare rolling stats)
        if len(self.spread_history) < self.p.window:
            return

        # 3. prendi solo gli ultimi 'window' valori
        recent_spread = self.spread_history[-self.p.window:]
        
        mean = np.mean(recent_spread)
        
        deviation = np.std(recent_spread)
        
        z_score = (spread_today - mean) / deviation
        
        print(z_score)


mpc_df = pd.read_csv(DATA_DIR / "csv" / "xle_basket.csv",header=[0,1], index_col=0, parse_dates=True)["MPC"]
psx_df = pd.read_csv(DATA_DIR / "csv" / "xle_basket.csv",header=[0,1], index_col=0, parse_dates=True)["PSX"]

hedge_r = hr.hedge(mpc_df, psx_df)

print(hedge_r)
#print(mpc_df.head())

cerebro = bt.Cerebro()

cerebro.broker.setcommission(commission=0.002)

data_mpc = bt.feeds.PandasData(dataname=mpc_df)
data_psx = bt.feeds.PandasData(dataname=psx_df)

cerebro.adddata(data_mpc, name="MPC")
cerebro.adddata(data_psx, name="PSX")

cerebro.addstrategy(PairsTrading, hedge_ratio = hedge_r)
cerebro.run()

