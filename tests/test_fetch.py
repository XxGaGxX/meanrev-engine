"""Unit tests for data fetch module (static / non-network parts)."""

import pandas as pd
import pytest

from data.fetch import AlpacaDataClient, _to_ny_tz


class TestToNYTz:
    def test_naive_string(self):
        t = _to_ny_tz("2024-01-01")
        assert str(t.tz) == "America/New_York"

    def test_already_tz_aware(self):
        t = pd.Timestamp("2024-01-01", tz="UTC")
        result = _to_ny_tz(str(t))
        assert str(result.tz) == "America/New_York"


class TestParseTimeframe:
    def test_known_timeframes(self):
        from alpaca.data.timeframe import TimeFrameUnit
        tf1 = AlpacaDataClient._parse_timeframe("1Min")
        assert tf1.amount == 1 and tf1.unit == TimeFrameUnit.Minute
        tf5 = AlpacaDataClient._parse_timeframe("5Min")
        assert tf5.amount == 5 and tf5.unit == TimeFrameUnit.Minute
        tf15 = AlpacaDataClient._parse_timeframe("15Min")
        assert tf15.amount == 15 and tf15.unit == TimeFrameUnit.Minute
        tf_h = AlpacaDataClient._parse_timeframe("1Hour")
        assert tf_h.amount == 1 and tf_h.unit == TimeFrameUnit.Hour
        tf_d = AlpacaDataClient._parse_timeframe("1Day")
        assert tf_d.amount == 1 and tf_d.unit == TimeFrameUnit.Day

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            AlpacaDataClient._parse_timeframe("10Min")
