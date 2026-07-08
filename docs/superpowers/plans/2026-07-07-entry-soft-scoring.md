# Entry Signal Soft Scoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Required companion skills:**
> - `quant-analyst` — for indicator thresholds, z-score semantics, RSI/BB/volume weight rationale
> - `backtesting-trading-strategies` — for backtest-driven validation of each scoring variant

**Goal:** Replace the binary AND entry signal with a weighted soft scoring model, identical in pattern to the regime filter soft scoring (Sprint 2). Each of the 5 conditions contributes a score in [0,1], combined via configurable weights, with entry gated by a minimum score threshold.

**Architecture:** Modify `signals/entry.py` to add `soft_entry` mode (off by default, respects existing behavior). The function `generate_entry_signals()` gains a `soft_scoring: bool` parameter. When enabled, `entry_score` is computed per bar; `signal_long` / `signal_short` fire when `entry_score >= score_threshold` AND the bar's directional conditions (RSI oversold/overbought, z-score sign) are met. Existing `signal_long`/`signal_short` columns are preserved; `entry_score` and per-component scores are added as diagnostic columns.

**Tech Stack:** Python 3.14, pandas, numpy. No new dependencies.

## Global Constraints

- Existing AND behavior is preserved when `soft_scoring=False` (default) — backward compatible
- New columns (`entry_score`, `rsi_score`, `bb_score`, `zscore_score`, `vol_score`, `regime_score_entry`) are only added when `soft_scoring=True`
- Config keys propagate through `backtest.engine._default_cfg` → `_merge_cfg` → `generate_entry_signals`
- Must follow the same scoring formula as `filters/regime._score_component`: `(1.0 - value/threshold).clip(0.0, 1.0)` for upper-bound filters; for lower-bound (RSI oversold) and bi-directional (BB, z-score), use symmetric normalization
- `diagnose_entries.py` must correctly report the new scoring columns when present (Section 3 should show mean `entry_score` and component scores)
- 255 existing tests must continue to pass

---

### Task 1: Add `_score_component` helper to `signals/entry.py`

**Files:**
- Modify: `signals/entry.py` (add helper function after `_REQUIRED_COLS`)

**Interfaces:**
- Produces: `_score_component(value: pd.Series, threshold) -> pd.Series` — re-exported from `filters.regime` or duplicated

> **quant-analyst note:** The scoring formula is `(1.0 - |value|/threshold).clip(0,1)` for bi-directional conditions (z-score, BB position) where deviation in EITHER direction is good for entry, and `(1.0 - value/threshold).clip(0,1)` for upper-bound (RSI overbought for short signals). For lower-bound (RSI oversold for long), use `(value/threshold).clip(0,1)` — high RSI = bad for longs. Use the existing `_score_component` from `filters.regime` via import to avoid duplication.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_signals.py — add to existing TestEntrySignals class
def test_entry_scoring_columns_present_with_soft_scoring(self, sample_df):
    """When soft_scoring=True, entry_score and component scores appear."""
    from filters.regime import apply_regime_filter
    df = apply_regime_filter(sample_df, adx_threshold=30, hurst_threshold=0.6)
    df = generate_entry_signals(df, cfg={"soft_scoring": True})
    for col in ("entry_score", "rsi_score", "bb_score",
                 "zscore_score", "regime_score_entry"):
        assert col in df.columns, f"missing: {col}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_signals.py::TestEntrySignals::test_entry_scoring_columns_present_with_soft_scoring -v`
Expected: FAIL — `KeyError: 'entry_score'`

- [ ] **Step 3: Add scoring helper and minimal implementation**

In `signals/entry.py`, import from filters:
```python
from filters.regime import _score_component
```

Then add `soft_scoring` parameter and column computation inside `generate_entry_signals` (after `cfg` block, before signal logic):

```python
soft = cfg.get("soft_scoring", False)
if soft:
    # Entry scoring weights (configurable, with sensible defaults)
    w_regime = cfg.get("score_regime_weight", 0.30)
    w_rsi = cfg.get("score_rsi_weight", 0.15)
    w_bb = cfg.get("score_bb_weight", 0.15)
    w_z = cfg.get("score_z_weight", 0.25)
    w_vol = cfg.get("score_vol_weight", 0.15)

    # Direction-agnostic component scores [0,1]
    # regime_score_entry: 1.0 if regime_ok, 0.0 if not
    df["regime_score_entry"] = df["regime_ok"].astype(float)

    # RSI: oversold (low RSI) → high score for long; overbought → high for short
    # Use a symmetric tent: score = 1 - |RSI - 50| / max_distance
    rsi_center = 50.0
    rsi_distance = 20.0  # RSI 30-70 range
    df["rsi_score"] = (1.0 - np.abs(df["rsi"] - rsi_center) / rsi_distance).clip(0.0, 1.0)

    # BB: price at or beyond bands → high score
    bb_range = df["bb_upper"] - df["bb_lower"]
    bb_deviation = np.maximum(
        (df["bb_upper"] - df["close"]) / bb_range.replace(0, np.nan),
        (df["close"] - df["bb_lower"]) / bb_range.replace(0, np.nan),
    )
    df["bb_score"] = (bb_deviation * 2.0).clip(0.0, 1.0).fillna(0.0)

    # Z-score: |z| large → high score, 0 → low score
    z_threshold_score = cfg.get("z_threshold", 2.0)
    df["zscore_score"] = (np.abs(df["zscore"]) / z_threshold_score).clip(0.0, 1.0)

    # Volume: binary, 1.0 if confirming, 0.5 if not (always at least neutral)
    df["vol_score"] = df["vol_confirm"].astype(float).where(
        cfg.get("use_volume_confirm", True),
        pd.Series(0.5, index=df.index),  # neutral when volume disabled
    )

    # Weighted entry score
    df["entry_score"] = (
        w_regime * df["regime_score_entry"]
        + w_rsi * df["rsi_score"]
        + w_bb * df["bb_score"]
        + w_z * df["zscore_score"]
        + w_vol * df["vol_score"]
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_signals.py::TestEntrySignals::test_entry_scoring_columns_present_with_soft_scoring -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add signals/entry.py tests/test_signals.py
git commit -m "feat: add entry soft scoring columns (score components)"
```


### Task 2: Replace binary AND with score-gated signals

**Files:**
- Modify: `signals/entry.py` (replace signal_long / signal_short logic when `soft_scoring=True`)

**Interfaces:**
- Consumes: `entry_score`, `rsi_score`, `bb_score`, `zscore_score`, `vol_score`, `regime_score_entry` (Task 1)
- Produces: `signal_long`, `signal_short` (same columns, populated via scoring when `soft_scoring=True`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_signals.py
def test_soft_scoring_produces_signals_when_binary_and_would_not(self, sample_df):
    """A bar with excellent RSI+BB+z-score but regime_ok=False
    can fire with soft scoring (compensation) but never with binary AND."""
    from filters.regime import apply_regime_filter
    df = apply_regime_filter(sample_df, adx_threshold=30, hurst_threshold=0.6)
    # Force regime_ok=False for ALL bars
    df["regime_ok"] = False
    # But set strong entry conditions
    df["rsi"] = 25.0        # oversold
    df["zscore"] = -2.5     # extreme
    df["close"] = df["bb_lower"] - 1.0  # below lower
    df["vol_confirm"] = True
    # Binary AND: 0 signals (regime_ok=False blocks everything)
    df_bin = generate_entry_signals(df.copy(), cfg={"soft_scoring": False})
    assert df_bin["signal_long"].sum() == 0
    # Soft scoring with low entry_threshold: should fire
    df_soft = generate_entry_signals(df.copy(), cfg={
        "soft_scoring": True,
        "entry_score_threshold": 0.40,
        "score_regime_weight": 0.10,  # downweight regime so others compensate
    })
    assert df_soft["signal_long"].sum() > 0, (
        "soft scoring should fire when RSI/BB/z score compensate for regime"
    )

def test_soft_scoring_respects_direction(self):
    """A bar with strong RSI oversold fires LONG, not SHORT."""
    df = _make_entry_df(n=30)
    from filters.regime import apply_regime_filter
    df = apply_regime_filter(df, adx_threshold=30, hurst_threshold=0.6)
    df["rsi"] = 25.0       # oversold → long signal
    df["zscore"] = -2.5    # negative → long
    df_soft = generate_entry_signals(df, cfg={
        "soft_scoring": True,
        "entry_score_threshold": 0.40,
    })
    assert df_soft["signal_long"].iloc[-1], "long should fire on oversold + negative z"
    assert not df_soft["signal_short"].iloc[-1], "short should NOT fire on oversold"

def test_binary_and_still_works_when_soft_scoring_false(self, sample_df):
    """Backward compat: soft_scoring=False uses original AND logic."""
    from filters.regime import apply_regime_filter
    df = apply_regime_filter(sample_df, adx_threshold=30, hurst_threshold=0.6)
    df_bin = generate_entry_signals(df.copy(), cfg={"soft_scoring": False})
    df_def = generate_entry_signals(df.copy())
    # Default (None) should match explicit False
    assert (df_bin["signal_long"] == df_def["signal_long"]).all()
    assert (df_bin["signal_short"] == df_def["signal_short"]).all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_signals.py::TestEntrySignals::test_soft_scoring_produces_signals_when_binary_and_would_not tests/test_signals.py::TestEntrySignals::test_soft_scoring_respects_direction tests/test_signals.py::TestEntrySignals::test_binary_and_still_works_when_soft_scoring_false -v`
Expected: First two FAIL, third passes (binary AND is default)

- [ ] **Step 3: Implement score-gated signals**

In `signals/entry.py`, after the scoring columns block (from Task 1), add:

```python
    if soft:
        entry_threshold = cfg.get("entry_score_threshold", 0.50)

        # Directional checks: long needs oversold bias, short needs overbought
        long_dir = (df["rsi"] < oversold) & (df["zscore"] < 0)
        short_dir = (df["rsi"] > overbought) & (df["zscore"] > 0)

        # Signal fires when score passes threshold AND direction is correct
        df["signal_long"] = (df["entry_score"] >= entry_threshold) & long_dir
        df["signal_short"] = (df["entry_score"] >= entry_threshold) & short_dir
    else:
        # ── Original binary AND logic (unchanged) ───────────────
        long_cond = (
            df["regime_ok"]
            & (df["rsi"] < oversold)
            & (df["close"] < df["bb_lower"])
            & (df["zscore"] < -z_threshold)
        )
        if use_volume:
            long_cond = long_cond & df["vol_confirm"]
        df["signal_long"] = long_cond.fillna(False)

        short_cond = (
            df["regime_ok"]
            & (df["rsi"] > overbought)
            & (df["close"] > df["bb_upper"])
            & (df["zscore"] > z_threshold)
        )
        if use_volume:
            short_cond = short_cond & df["vol_confirm"]
        df["signal_short"] = short_cond.fillna(False)
```

Move the original binary AND logic inside the `else` block (remove the old top-level code).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_signals.py -q --tb=short -v`
Expected: All signal tests PASS (including the 3 new ones + all existing)

- [ ] **Step 5: Commit**

```bash
git add signals/entry.py tests/test_signals.py
git commit -m "feat: add score-gated entry signals with soft scoring mode"
```


### Task 3: Wire config propagation and update `diagnose_entries.py`

**Files:**
- Modify: `config.yaml` (add `entry_signal.soft_scoring` block)
- Modify: `backtest/engine.py` (no changes needed — `entry_signal` dict is already passed through)
- Modify: `scripts/diagnose_entries.py` (Section 3: show `entry_score` when present)

**Interfaces:**
- Consumes: `entry_score`, `regime_score_entry`, `rsi_score`, `bb_score`, `zscore_score`, `vol_score` columns from Task 1
- Produces: updated Section 3 output

- [ ] **Step 1: Update `config.yaml`**

Add to the `entry_signal` block:

```yaml
entry_signal:
  z_threshold: 2.0
  use_volume_confirm: true
  use_price_action: false
  min_signals_per_asset: 30
  # ── Soft scoring (Sprint 4) ──────────────────────────────
  soft_scoring: true
  entry_score_threshold: 0.50
  score_regime_weight: 0.30     # regime_ok: 30%
  score_rsi_weight: 0.15        # RSI extreme: 15%
  score_bb_weight: 0.15         # BB band touch: 15%
  score_z_weight: 0.25          # z-score extreme: 25%
  score_vol_weight: 0.15        # volume confirm: 15%
```

- [ ] **Step 2: Verify config propagation works**

`generate_entry_signals` reads `cfg` dict directly — no `_default_cfg` filtering needed for `entry_signal` (unlike `regime_filter`). Verify:

Run: `python -c "from backtest.engine import _default_cfg; print('entry_signal' in _default_cfg()); exit(0 if 'entry_signal' in _default_cfg() else 1)"`
Expected: exit code 0

- [ ] **Step 3: Update `diagnose_entries.py` Section 3**

In `_print_win_loss_comparison`, add detection for soft entry scoring:

```python
    # After existing metrics block, add:
    if "entry_score" in df.columns:
        w_entry = [
            float(df["entry_score"].iloc[int(t["entry_idx"])])
            for _, t in winners.iterrows()
            if int(t["entry_idx"]) < len(df) and not pd.isna(df["entry_score"].iloc[int(t["entry_idx"])])
        ]
        l_entry = [
            float(df["entry_score"].iloc[int(t["entry_idx"])])
            for _, t in losers.iterrows()
            if int(t["entry_idx"]) < len(df) and not pd.isna(df["entry_score"].iloc[int(t["entry_idx"])])
        ]
        print(f"{'Entry score':<18} {_fmt(w_entry, '.3f'):<22} {_fmt(l_entry, '.3f'):<22}")
```

Update `main()` to also read and display the entry soft scoring config:

```python
    if entry_cfg.get("soft_scoring", False):
        print(f"  Entry scoring: enabled, threshold={entry_cfg.get('entry_score_threshold', 0.50)}")
```

- [ ] **Step 4: Commit**

```bash
git add config.yaml scripts/diagnose_entries.py
git commit -m "feat: wire entry soft scoring config and diagnose_entries integration"
```


### Task 4: Validation — backtest-driven comparison

> **Use `backtesting-trading-strategies` skill for this task.**

**Files:**
- None modified (validation only)

**Interfaces:**
- Consumes: complete `signals/entry.py` with soft scoring, `config.yaml`, `diagnose_entries.py`

- [ ] **Step 1: Diagnose with default config (soft scoring ON, threshold 0.50)**

Run: `python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01"`
Expected: Entry scoring shows "enabled". Section 1 still shows frequency of individual conditions. Section 3 includes "Entry score" row.

- [ ] **Step 2: Diagnose with permissive threshold (0.40)**

Run: `python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01" --cfg '{"entry_signal":{"entry_score_threshold":0.40}}'`
Expected: More signals than default. Compare with default run.

- [ ] **Step 3: Diagnose with strict threshold (0.60)**

Run: `python scripts/diagnose_entries.py SPY "2026-04-01" "2026-07-01" --cfg '{"entry_signal":{"entry_score_threshold":0.60}}'`
Expected: Fewer signals than default (may be 0).

- [ ] **Step 4: Run full demo with soft scoring active**

Run: `python scripts/demo_e2e.py --symbol SPY --n-bars 1500`
Expected: Demo runs successfully. Compare win rate, profit factor, Sharpe with Sprint 3 baseline.

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -q --tb=short`
Expected: All tests pass (≥255 + new signal tests)

- [ ] **Step 6: Commit validation results**

```bash
git add -A
git commit -m "chore: validation results for entry soft scoring (Sprint 4)"
```


### Task 5: Code review and cleanup

**Files:**
- Review: `signals/entry.py` (entire file)
- Review: `tests/test_signals.py` (new tests)
- Review: `config.yaml` (new keys)
- Review: `scripts/diagnose_entries.py` (Section 3 update)

- [ ] **Step 1: Spawn `code-reviewer-deepseek` on the complete diff**

```bash
git diff mean_reversion...feature/entry-soft-scoring > /tmp/sprint4.diff
```

Review focus:
- Scoring formula correctness (RSI tent, BB deviation, z-score normalization)
- Weight defaults rationale (quant-analyst perspective)
- NaN handling during indicator warmup
- Backward compat: `soft_scoring=False` path untouched
- `diagnose_entries.py` gracefully handles missing scoring columns

- [ ] **Step 2: Address any Critical/Important findings**

- [ ] **Step 3: Final commit after review fixes**

```bash
git commit -m "chore: code review fixes for entry soft scoring"
```
