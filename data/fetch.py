"""
Data Fetch Module — Mean Reversion Intraday
===========================================
Fetches historical and real-time OHLCV data from Alpaca Markets.
Uses the modern `alpaca-py` SDK (alpaca-trade-api is deprecated).

Credentials are read from environment variables (see .env.example).
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv

# Alpaca-py imports
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed
from alpaca.data.live import StockDataStream

DEFAULT_FEED = DataFeed.SIP  # US equities consolidated SIP feed

load_dotenv()


def _to_ny_tz(ts: str) -> pd.Timestamp:
    """Safely convert a date string to America/New_York timezone."""
    t = pd.Timestamp(ts)
    if t.tz is None:
        return t.tz_localize("America/New_York")
    return t.tz_convert("America/New_York")


class AlpacaDataClient:
    """Client for fetching stock data from Alpaca Markets."""

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca API credentials not found. "
                "Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables "
                "or create a .env file (see .env.example)."
            )

        self.client = StockHistoricalDataClient(self.api_key, self.secret_key)

    def fetch_historical_bars(
        self,
        symbols: List[str],
        timeframe: str = "15Min",
        start: str = "2022-01-01",
        end: Optional[str] = None,
        feed: DataFeed = DEFAULT_FEED,
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical OHLCV bars for a list of symbols.

        Parameters
        ----------
        symbols : list of str
            Ticker symbols (e.g., ["SPY", "QQQ"]).
        timeframe : str
            Bar timeframe. Options: "1Min", "5Min", "15Min", "1Hour", "1Day".
        start : str
            Start date in ISO format (YYYY-MM-DD).
        end : str, optional
            End date. Defaults to yesterday.
        feed : DataFeed
            Data feed source.

        Returns
        -------
        dict[str, pd.DataFrame]
            Mapping symbol -> DataFrame with columns [open, high, low, close, volume].
        """
        if end is None:
            end = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        tf = self._parse_timeframe(timeframe)

        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=tf,
            start=_to_ny_tz(start),
            end=_to_ny_tz(end),
            feed=feed,
        )

        bars = self.client.get_stock_bars(request)
        data = {}
        for symbol in symbols:
            df = bars.df.xs(symbol, level="symbol") if len(symbols) > 1 else bars.df
            df = df[["open", "high", "low", "close", "volume"]]
            df.index.name = "timestamp"
            data[symbol] = df

        return data

    def fetch_historical_single(
        self,
        symbol: str,
        timeframe: str = "15Min",
        start: str = "2022-01-01",
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Convenience method to fetch a single symbol."""
        return self.fetch_historical_bars([symbol], timeframe, start, end)[symbol]

    def create_live_stream(self, symbols: List[str]):
        """
        Create a live WebSocket data stream.

        Parameters
        ----------
        symbols : list of str
            Ticker symbols to subscribe to (used for documentation only;
            actual subscription happens via stream.subscribe_bars()).

        Returns
        -------
        StockDataStream
            Unstarted stream instance. Use it as:

            stream = client.create_live_stream(["SPY"])
            stream.subscribe_bars(my_handler, "SPY")
            stream.run()
        """
        return StockDataStream(self.api_key, self.secret_key, feed=DEFAULT_FEED)

    @staticmethod
    def _parse_timeframe(tf_str: str) -> TimeFrame:
        """Parse a timeframe string into an Alpaca TimeFrame object."""
        mapping = {
            "1Min": TimeFrame(1, TimeFrameUnit.Minute),
            "5Min": TimeFrame(5, TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
            "1Day": TimeFrame(1, TimeFrameUnit.Day),
        }
        if tf_str in mapping:
            return mapping[tf_str]
        raise ValueError(f"Unsupported timeframe: {tf_str}")


# ── Standalone convenience functions ──────────────────────────────────────────

def fetch_all_historical(
    symbols: List[str],
    timeframe: str = "15Min",
    start: str = "2022-01-01",
    end: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """Fetch historical data for all symbols using default credentials."""
    client = AlpacaDataClient()
    return client.fetch_historical_bars(symbols, timeframe, start, end)


def fetch_single_historical(
    symbol: str,
    timeframe: str = "15Min",
    start: str = "2022-01-01",
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch historical data for a single symbol."""
    client = AlpacaDataClient()
    return client.fetch_historical_single(symbol, timeframe, start, end)
