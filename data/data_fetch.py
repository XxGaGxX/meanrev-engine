import json
from pathlib import Path

import yfinance as yf

# fetch OHLCV dei ticker

tickers_name = ["XOM", "CVX", "COP", "EOG", "OXY", "MPC", "VLO", "PSX",
                 "DVN", "FANG",
                 "PBF", "DK",
                 "KMI", "WMB", "OKE", "CTRA", "APA"]

base_dir = Path(__file__).resolve().parent
csv_dir = base_dir / "csv"
csv_dir.mkdir(parents=True, exist_ok=True)

with open(base_dir / "ticker.json", "w", encoding="utf-8") as file:
    json.dump(tickers_name, file, indent=4)

output_path = csv_dir / "xle_basket.csv"
data = yf.download(tickers_name, start="2020-01-01", group_by="ticker", auto_adjust=True)

data.to_csv(output_path)
