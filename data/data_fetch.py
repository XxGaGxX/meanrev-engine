import yfinance as yf

tickers_name = ["XOM", "CVX", "COP", "EOG", "OXY", "MPC", "VLO", "PSX"]
data = yf.download(tickers_name, start="2023-01-01")

data.to_csv("csv/xle_basket.csv")


