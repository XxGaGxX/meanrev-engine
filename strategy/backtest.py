import backtrader as bt
import pandas as pd

mpc_df = pd.read_csv("../data/csv/xle_basket.csv",header=[0,1], index_col=0)["MPC"]
psx_df = pd.read_csv("../data/csv/xle_basket.csv",header=[0,1], index_col=0)["PSX"]

print(mpc_df.head())

cerebro = bt.Cerebro()

cerebro.broker.setcommission(commission=0.002)

data_mpc = bt.feeds.PandasData(dataname=mpc_df)
data_psx = bt.feeds.PandasData(dataname=psx_df)

cerebro.adddata(data_mpc, name="MPC")
cerebro.adddata(data_psx, name="PSX")