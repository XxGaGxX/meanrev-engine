import numpy as np
import statsmodels.tsa.stattools as stat
import pandas as pd
import json

df = pd.read_csv("../data/csv/xle_basket.csv", header=[0,1], index_col=0)

with open("../data/ticker.json", 'r', encoding='utf-8') as file:
    tickers = json.load(file)

screening_couples = []

for ticker1 in tickers:
    for ticker2 in tickers:
        if ticker1 == ticker2:
            continue

        prices1 = df[ticker1]["Close"].replace([np.inf, -np.inf], np.nan)
        prices2 = df[ticker2]["Close"].replace([np.inf, -np.inf], np.nan)
        pair = pd.concat([prices1, prices2], axis=1).dropna()

        if len(pair) < 30:
            continue

        try:
            ticker_coint = stat.coint(pair.iloc[:, 0], pair.iloc[:, 1])
        except Exception as exc:
            print(f"Skipping {ticker1} | {ticker2}: {exc}")
            continue

        if ticker_coint[1] < 0.05:
            new_element = {
                "label": f"{ticker1} | {ticker2}",
                "t-statistic": ticker_coint[0],
                "p-value": ticker_coint[1],
                "crit_values": ticker_coint[2],
            }
            screening_couples.append(new_element)

print(screening_couples)

