"""Unit tests for config loader."""

import pytest

from utils.config import Config, config


class TestConfig:
    def test_get_existing_key(self):
        assert config.get("indicators.adx.period") == 14

    def test_get_nested_key(self):
        assert config.get("timeframe.primary") == "15Min"

    def test_get_with_default(self):
        assert config.get("nonexistent.key", "default") == "default"

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            Config(path="/nonexistent/config.yaml")

    def test_raw_dict(self):
        raw = config.raw
        assert isinstance(raw, dict)
        assert "indicators" in raw
