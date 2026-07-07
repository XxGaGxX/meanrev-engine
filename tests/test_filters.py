"""Unit tests for filter modules."""

import numpy as np
import pandas as pd
import pytest

from filters.regime import (
    apply_regime_filter,
    regime_component_breakdown,
    regime_coverage,
)


@pytest.fixture
def regime_df() -> pd.DataFrame:
    """Synthetic DataFrame with indicator columns ready for regime filter."""
    n = 100
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    df = pd.DataFrame(
        {
            "adx": np.linspace(15, 30, n),     # crosses threshold
            "hurst": np.full(n, 0.40),         # mean-reverting
            "atr": np.full(n, 1.0),
            "close": np.full(n, 100.0),
        },
        index=idx,
    )
    return df


class TestRegimeFilter:
    def test_adds_columns(self, regime_df):
        df = apply_regime_filter(regime_df)
        assert set(df.columns) >= {"atr_rel", "atr_rel_z", "regime_ok"}

    def test_regime_ok_is_bool(self, regime_df):
        df = apply_regime_filter(regime_df)
        assert df["regime_ok"].dropna().isin({True, False}).all()

    def test_coverage_between_0_and_100(self, regime_df):
        df = apply_regime_filter(regime_df)
        cov = regime_coverage(df)
        assert 0.0 <= cov <= 100.0

    def test_constant_atr_zscore_is_zero(self):
        """When ATR is constant, atr_rel_z should be 0 (not inf/NaN)."""
        df = pd.DataFrame(
            {
                "adx": [20.0] * 50,
                "hurst": [0.40] * 50,
                "atr": [1.0] * 50,
                "close": [100.0] * 50,
            }
        )
        df = apply_regime_filter(df)
        assert df["atr_rel_z"].iloc[20:].fillna(0).eq(0).all()


class TestRegimeSoftScoring:
    """Tests for soft (weighted) regime scoring — Sprint 2."""

    @staticmethod
    def _make_soft_df() -> pd.DataFrame:
        """DataFrame with known values for predictable scores."""
        n = 100
        idx = pd.date_range("2024-01-01", periods=n, freq="15min")
        return pd.DataFrame(
            {
                "adx": np.full(n, 12.5),     # 50% of threshold 25 → score 0.5
                "hurst": np.full(n, 0.275),  # 50% of threshold 0.55 → score 0.5
                "atr": np.full(n, 1.0),
                "close": np.full(n, 100.0),
            },
            index=idx,
        )

    def test_soft_scoring_adds_score_columns(self):
        df = self._make_soft_df()
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55, soft_scoring=True,
        )
        for col in ("adx_score", "hurst_score", "atr_score", "regime_score"):
            assert col in df.columns, f"missing soft-scoring column: {col}"

    def test_soft_scoring_exact_half_threshold_yields_score_05(self):
        """At 50% of threshold, each score should be exactly 0.5."""
        df = self._make_soft_df()
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55,
            atr_relative_std_threshold=2.0, soft_scoring=True,
        )
        # Skip ATR warmup (first 20 bars have NaN z-scores)
        warm = df.iloc[20:]
        assert (warm["adx_score"] == 0.5).all()
        assert (warm["hurst_score"] == 0.5).all()
        # ATR z = 0 → score = 1 - 0/2 = 1.0
        assert (warm["atr_score"] >= 0.99).all()

    def test_regime_score_is_weighted_sum(self):
        """With all components at 0.5 and weights 0.4/0.4/0.2,
        regime_score should be 0.4*0.5 + 0.4*0.5 + 0.2*1.0 = 0.60."""
        df = self._make_soft_df()
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55,
            atr_relative_std_threshold=2.0, soft_scoring=True,
        )
        warm = df["regime_score"].iloc[20:]
        assert np.allclose(warm.values, 0.60, atol=0.01)

    def test_regime_ok_passes_when_score_above_threshold(self):
        """At score=0.60 with threshold=0.50, regime_ok should be True."""
        df = self._make_soft_df()
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55,
            atr_relative_std_threshold=2.0, soft_scoring=True,
            score_threshold=0.50,
        )
        # Warmup bars have NaN scores → regime_ok=False; post-warmup all True
        assert df["regime_ok"].iloc[20:].all()

    def test_regime_ok_blocked_when_score_below_threshold(self):
        """With strict threshold=0.65 > score=0.60, regime_ok should be False."""
        df = self._make_soft_df()
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55,
            atr_relative_std_threshold=2.0, soft_scoring=True,
            score_threshold=0.65,
        )
        # Warmup bars are False (NaN); post-warmup also False (score < threshold)
        assert (~df["regime_ok"].iloc[20:]).all()

    def test_compensation_adx_hurst_covers_weak_atr(self):
        """Strong ADX + Hurst should compensate for weak ATR.

        Two bars at the end carry a huge ATR spike (atr=30) that pushes
        ``atr_rel_z`` well above the 2.0 threshold.  ADX and Hurst are
        well inside their own thresholds, so the weighted score still
        crosses 0.50 — soft scoring passes where binary AND would not.
        """
        n = 100
        idx = pd.date_range("2024-01-01", periods=n, freq="15min")
        atr = np.full(n, 0.5)
        atr[-2:] = 30.0          # huge spike → z > 2.0
        df = pd.DataFrame(
            {
                "adx": [5.0] * n,         # well below threshold 25 → score 0.80
                "hurst": [0.10] * n,      # well below threshold 0.55 → score 0.82
                "atr": atr,
                "close": [100.0] * n,
            },
            index=idx,
        )
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55,
            atr_relative_std_threshold=2.0, soft_scoring=True,
        )
        last = df.iloc[-1]
        assert last["atr_rel_z"] > 2.0, (
            f"expected ATR z > 2.0, got {last['atr_rel_z']:.2f}"
        )
        assert last["atr_score"] < 0.5, (
            f"expected weak ATR score, got {last['atr_score']:.2f}"
        )
        assert last["regime_ok"], (
            f"soft scoring should pass via compensation; "
            f"regime_score={last['regime_score']:.3f}"
        )

    def test_soft_scoring_off_uses_binary_and(self):
        """With soft_scoring=False, the old AND logic applies."""
        df = self._make_soft_df()
        # With ADX=12.5 < 25 AND Hurst=0.275 < 0.55, all pass.
        # ATR warmup bars have NaN → AND rejects them; post-warmup all pass.
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55,
            soft_scoring=False,
        )
        assert df["regime_ok"].iloc[20:].all()
        # No soft scoring columns
        assert "regime_score" not in df.columns

    def test_breakdown_includes_mean_scores_when_soft_scoring(self):
        """regime_component_breakdown should include mean scores
        when regime_score column exists."""
        df = self._make_soft_df()
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55,
            soft_scoring=True,
        )
        bd = regime_component_breakdown(
            df, adx_threshold=25, hurst_threshold=0.55,
        )
        assert "mean_regime_score" in bd
        assert "mean_adx_score" in bd
        assert "mean_hurst_score" in bd
        assert "mean_atr_score" in bd
        # Mean over non-NaN bars → ~0.60
        assert bd["mean_regime_score"] == pytest.approx(0.60, abs=0.02)

    # ── Sprint 3 — Adaptive Hurst threshold ──────────────────────

    def test_adaptive_hurst_tightens_in_strong_trend(self):
        """When slow Hurst > 0.6, the effective threshold tightens to 0.45."""
        n = 100
        idx = pd.date_range("2024-01-01", periods=n, freq="15min")
        # hurst_fast = 0.50 is < 0.55 (relaxed) but > 0.45 (tight)
        # hurst slow = 0.70 is > 0.6 → adaptive tightens to 0.45
        # So hurst_fast=0.50 should FAIL the regime check
        df = pd.DataFrame({
            "adx": [20.0] * n,
            "hurst": [0.70] * n,          # slow > 0.6 → tight threshold 0.45
            "hurst_fast": [0.50] * n,     # 0.50 < 0.55 but 0.50 > 0.45 → FAIL
            "atr": [1.0] * n,
            "close": [100.0] * n,
        }, index=idx)
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55,
            use_fast_hurst=True, soft_scoring=False,
            adaptive_hurst=True,
        )
        warm = df.iloc[20:]
        # With tight threshold 0.45 and hurst_fast=0.50, regime_ok must be False
        assert (~warm["regime_ok"]).all()

    def test_adaptive_hurst_relaxes_in_range(self):
        """When slow Hurst < 0.5, threshold relaxes to 0.55.
        hurst_fast=0.52 passes because 0.52 < 0.55."""
        n = 100
        idx = pd.date_range("2024-01-01", periods=n, freq="15min")
        df = pd.DataFrame({
            "adx": [20.0] * n,
            "hurst": [0.40] * n,          # slow < 0.5 → relax threshold 0.55
            "hurst_fast": [0.52] * n,     # 0.52 < 0.55 → PASS
            "atr": [1.0] * n,
            "close": [100.0] * n,
        }, index=idx)
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55,
            use_fast_hurst=True, soft_scoring=False,
            adaptive_hurst=True,
        )
        warm = df.iloc[20:]
        assert warm["regime_ok"].all()

    def test_adaptive_hurst_off_uses_constant_threshold(self):
        """With adaptive_hurst=False, hurst_fast=0.50 should pass (0.50 < 0.55)."""
        n = 100
        idx = pd.date_range("2024-01-01", periods=n, freq="15min")
        df = pd.DataFrame({
            "adx": [20.0] * n,
            "hurst": [0.70] * n,          # slow > 0.6 but adaptive is OFF
            "hurst_fast": [0.50] * n,     # 0.50 < 0.55 → PASS
            "atr": [1.0] * n,
            "close": [100.0] * n,
        }, index=idx)
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55,
            use_fast_hurst=True, soft_scoring=False,
            adaptive_hurst=False,
        )
        warm = df.iloc[20:]
        assert warm["regime_ok"].all()

    def test_adaptive_hurst_with_soft_scoring(self):
        """Adaptive threshold works with soft scoring: tight threshold
        reduces hurst_score for the same hurst_fast value."""
        n = 100
        idx = pd.date_range("2024-01-01", periods=n, freq="15min")
        df = pd.DataFrame({
            "adx": [12.5] * n,            # score 0.5
            "hurst": [0.70] * n,          # tight threshold 0.45
            "hurst_fast": [0.30] * n,     # score = 1 - 0.30/0.45 ≈ 0.333
            "atr": [1.0] * n,
            "close": [100.0] * n,
        }, index=idx)
        df = apply_regime_filter(
            df, adx_threshold=25, hurst_threshold=0.55,
            use_fast_hurst=True, soft_scoring=True,
            adaptive_hurst=True,
        )
        warm = df.iloc[20:]
        # adx_score=0.5, hurst_score≈0.333, atr_score≈1.0
        # regime_score ≈ 0.4*0.5 + 0.4*0.333 + 0.2*1.0 = 0.20+0.133+0.20 = 0.533
        assert np.allclose(warm["regime_score"].values, 0.533, atol=0.02)


class TestRegimeComponentBreakdown:
    def test_breakdown_sums_correctly(self):
        """The three pass rates should be internally consistent."""
        df = pd.DataFrame({
            "adx": [20.0] * 50 + [30.0] * 50,
            "hurst": [0.40] * 50 + [0.60] * 50,
            "atr_rel_z": [1.0] * 50 + [3.0] * 50,
            "close": [100.0] * 100,
            "atr": [1.0] * 100,
        })
        df = apply_regime_filter(df, adx_threshold=25, hurst_threshold=0.50)
        bd = regime_component_breakdown(
            df, adx_threshold=25, hurst_threshold=0.50,
            atr_relative_std_threshold=2.0,
        )
        assert bd["n_bars"] == 100
        # Half bars pass each component
        assert 45 <= bd["adx_pass_pct"] <= 55
        assert 45 <= bd["hurst_pass_pct"] <= 55
        # Combined (AND of all three) must be ≤ each component
        assert bd["all_pass_pct"] <= bd["adx_pass_pct"]
        assert bd["all_pass_pct"] <= bd["hurst_pass_pct"]
        assert bd["all_pass_pct"] <= bd["atr_rel_z_pass_pct"]

    def test_breakdown_raises_on_missing_columns(self):
        """ValueError if required columns are missing."""
        df = pd.DataFrame({"close": [100.0]})
        with pytest.raises(ValueError, match="Missing columns"):
            regime_component_breakdown(df)

    def test_breakdown_empty_df(self):
        """Empty DataFrame returns zeros."""
        df = pd.DataFrame(columns=["adx", "hurst", "atr_rel_z", "regime_ok"])
        bd = regime_component_breakdown(df)
        assert bd["n_bars"] == 0
        assert bd["all_pass_pct"] == 0.0
