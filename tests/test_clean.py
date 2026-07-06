"""Unit tests for data cleaning utilities."""

import numpy as np
import pandas as pd
import pytest

from data.clean import align_data, clean_data, filter_session_hours, validate_data


class TestCleanData:
    def test_removes_duplicates(self):
        idx = pd.to_datetime(["2024-01-01 09:30", "2024-01-01 09:30", "2024-01-01 09:45"])
        df = pd.DataFrame(
            {"open": [1, 2, 3], "high": [2, 3, 4], "low": [0, 1, 2], "close": [1.5, 2.5, 3.5], "volume": [100, 200, 300]},
            index=idx,
        )
        out = clean_data(df)
        assert len(out) == 2

    def test_removes_zero_volume(self):
        idx = pd.to_datetime(["2024-01-01 09:30", "2024-01-01 09:45"])
        df = pd.DataFrame(
            {"open": [1, 2], "high": [2, 3], "low": [0, 1], "close": [1.5, 2.5], "volume": [100, 0]},
            index=idx,
        )
        out = clean_data(df)
        assert len(out) == 1

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"close": [1, 2]}, index=pd.to_datetime(["2024-01-01", "2024-01-02"]))
        with pytest.raises(ValueError, match="Missing required columns"):
            clean_data(df)


class TestAlignData:
    def test_intersection(self):
        idx1 = pd.date_range("2024-01-01", periods=3, freq="D")
        idx2 = pd.date_range("2024-01-02", periods=3, freq="D")
        d1 = {"A": pd.DataFrame({"close": [1, 2, 3]}, index=idx1)}
        d2 = {"A": pd.DataFrame({"close": [1, 2, 3]}, index=idx1), "B": pd.DataFrame({"close": [10, 20, 30]}, index=idx2)}
        aligned = align_data(d2)
        assert len(aligned["A"]) == 2
        assert len(aligned["B"]) == 2

    def test_no_common_raises(self):
        idx1 = pd.date_range("2024-01-01", periods=2, freq="D")
        idx2 = pd.date_range("2024-02-01", periods=2, freq="D")
        data = {
            "A": pd.DataFrame({"close": [1, 2]}, index=idx1),
            "B": pd.DataFrame({"close": [10, 20]}, index=idx2),
        }
        with pytest.raises(ValueError, match="No common timestamps"):
            align_data(data)


class TestFilterSessionHours:
    def test_excludes_weekends(self):
        idx = pd.date_range("2024-01-06", periods=48, freq="15min")  # Sat -> Sun
        df = pd.DataFrame({"close": range(48)}, index=idx)
        out = filter_session_hours(df)
        assert len(out) == 0

    def test_excludes_pre_market(self):
        idx = pd.date_range("2024-01-02 09:00", periods=10, freq="5min")
        df = pd.DataFrame({"close": range(10)}, index=idx)
        out = filter_session_hours(df, skip_first_minutes=0, skip_last_minutes=0)
        # 09:00-09:25 is pre-market, excluded; 09:30-09:45 = 4 bars
        assert len(out) == 4

    def test_skip_first_and_last(self):
        idx = pd.date_range("2024-01-02 09:30", periods=79, freq="5min")  # until 16:00
        df = pd.DataFrame({"close": range(79)}, index=idx)
        out = filter_session_hours(df, skip_first_minutes=30, skip_last_minutes=30)
        # 09:30-09:55 excluded (6 bars), 15:35-16:00 excluded (6 bars)
        # 10:00-15:30 inclusive = 67 bars
        assert len(out) == 67
