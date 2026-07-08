# Fix Plan v2 — Bug Report Remediation

**Data:** 2026-07-07
**Basato su:** `BUG_REPORT.md` (5 bug identificati)
**Stato pre-fix:** 201 test verdi, demo funzionante, realistic-fill contract attivo

---

## Executive Summary

5 bug da fixare, organizzati in 5 step sequenziali con dipendenze a cascata:

| Step | Bug | Severità | Cosa fare | File coinvolti | Stima |
|---|---|---|---|---|---|
| 1 | #5 | 🟡 LOW | Costruire curva equity MTM per-bar | `risk/sizing.py` | 2-3h |
| 2 | #1 | 🔴 CRITICAL | Usare MTM per Sharpe/Sortino | `utils/metrics.py`, `backtest/engine.py` | 15min |
| 3 | #4 | 🟡 MEDIUM | Usare MTM per drawdown | già risolto da Step 1 | 0min |
| 4 | #2 | 🟠 HIGH | Rilassare regime + diagnostica | `config.yaml`, `filters/regime.py` | 30min |
| 5 | #3 | 🟠 MEDIUM | Ridurre overlap + segnali skippati | `config.yaml`, `signals/exit.py`, `backtest/engine.py` | 45min |

**Totale stimato:** 4-5 ore

**Principio guida:** Step 1 (curva MTM) è la fondamenta — risolve automaticamente anche #1 e #4. Gli step 4 e 5 sono parametrici, indipendenti tra loro, e possono essere eseguiti in parallelo dopo lo Step 3.

---

## Step 1 — Curva Equity Mark-to-Market per-bar

**Bug:** #5 (No MTM equity curve)  
**File principale:** `risk/sizing.py`  
**File impattati:** `backtest/engine.py` (consumatore)

### Design

```python
def build_mtm_equity_curve(
    trades: pd.DataFrame,
    df: pd.DataFrame,
    initial_equity: float = 10_000.0,
) -> pd.Series:
    """
    Build a per-bar mark-to-market equity curve.

    For every bar in ``df.index``, computes the account value as:
        cash + sum(unrealized PnL of open positions)

    When no positions are open, the curve is flat at the last
    realized equity level. When a position is open, the curve
    reflects the current market value of the position.

    Parameters
    ----------
    trades : pd.DataFrame
        Sized trade log from ``apply_position_sizing``. Must contain
        columns: entry_idx, exit_idx, direction, shares, equity_after,
        pnl_dollar, commission_cost.
    df : pd.DataFrame
        Cleaned + indicators DataFrame. Must have a ``close`` column
        and a DatetimeIndex.

    Returns
    -------
    pd.Series
        Index = df.index, values = per-bar equity in dollars.
        Length = len(df), starting at initial_equity before the first
        trade and ending at the last bar's close.
    """
```

### Algoritmo

1. **Inizializzazione:**
   - `equity = np.full(len(df), np.nan)`
   - `cash = initial_equity`
   - `open_positions: dict[int, dict] = {}`  # key = trade_index
   - Per ogni barra `i` in `range(len(df))`:

2. **Check aperture posizioni (entry):**
   - Se `trades["entry_idx"].iloc[t] == i` per qualche trade `t`:
     - Calcola `entry_cost = shares * entry_price + commission_entry + slippage_entry`
     - `cash -= entry_cost`
     - Aggiungi a `open_positions[t] = {"shares": ..., "direction": ..., "entry_price": ...}`

3. **Mark-to-market per barra:**
   - `unrealized_pnl = 0.0`
   - Per ogni posizione aperta: `unrealized_pnl += pos.shares * pos.direction * (df["close"].iloc[i] - pos.entry_price)`
   - `equity[i] = cash + unrealized_pnl`

4. **Check chiusure posizioni (exit):**
   - Se `trades["exit_idx"].iloc[t] == i` per qualche trade `t`:
     - Rimuovi da `open_positions`
     - `cash += exit_proceeds` (basato su `equity_after` del trade)
     - L'`equity[i]` per la barra di exit usa il `cash` aggiornato (post-exit)

5. **Gestione costi:**
   - Usa le colonne `pnl_dollar` e `commission_cost` del trade log sized per determinare il cash flow netto
   - Alternativa più semplice: `cash = equity_after[t]` dopo ogni exit, e per l'entry deduci dal cash precedente

### Implementazione semplificata

```python
def build_mtm_equity_curve(trades, df, initial_equity=10_000.0):
    if df.empty:
        return pd.Series([float(initial_equity)], index=pd.DatetimeIndex([pd.NaT]), name="equity_mtm")

    n = len(df)
    equity = np.full(n, np.nan, dtype=float)
    cash = float(initial_equity)

    if trades is None or trades.empty:
        equity[:] = cash
        return pd.Series(equity, index=df.index, name="equity_mtm")

    # Build lookup maps: bar_index → list of trade indices
    entries = defaultdict(list)
    exits = defaultdict(list)
    for t_idx in range(len(trades)):
        entries[int(trades.iloc[t_idx]["entry_idx"])].append(t_idx)
        exits[int(trades.iloc[t_idx]["exit_idx"])].append(t_idx)

    open_positions = {}  # trade_idx → {shares, direction, entry_price}

    for i in range(n):
        close_price = float(df["close"].iloc[i])

        # Process exits FIRST so the bar's equity reflects post-exit cash
        for t_idx in exits.get(i, []):
            if t_idx in open_positions:
                del open_positions[t_idx]
            # cash snaps to equity_after for this trade
            cash = float(trades.iloc[t_idx]["equity_after"])

        # Process entries
        for t_idx in entries.get(i, []):
            row = trades.iloc[t_idx]
            entry_cost = float(row["shares"]) * float(row["entry_price"])
            # Include commission + slippage from sized trade
            if "commission_cost" in trades.columns:
                entry_cost += float(row["commission_cost"]) / 2  # half on entry
            # Approximate: cash reduction ≈ position_value (since we use equity_after on exit)
            # Actually, just track the position; cash will snap on exit
            open_positions[t_idx] = {
                "shares": float(row["shares"]),
                "direction": float(row["direction"]),
                "entry_price": float(row["entry_price"]),
            }

        # MTM
        unrealized = 0.0
        for pos in open_positions.values():
            unrealized += pos["shares"] * pos["direction"] * (close_price - pos["entry_price"])
        equity[i] = cash + unrealized

    return pd.Series(equity, index=df.index, name="equity_mtm")
```

**Attenzione:** L'ordine exit-prima-di-entry sulla stessa barra è cruciale: se un trade chiude e un altro apre sulla stessa barra, il cash post-exit finanzia l'entry successiva.

### Modifiche a `backtest/engine.py`

Dopo la riga che chiama `build_equity_curve`:

```python
# --- 7. Equity curves ---
equity = build_equity_curve(trades, df, initial_equity=initial_equity)
naive = build_pct_curve(trades, df, initial_equity=initial_equity)
equity_mtm = build_mtm_equity_curve(trades, df, initial_equity=initial_equity)  # NEW
```

Aggiungere `equity_mtm` al `BacktestResult`:

```python
@dataclass
class BacktestResult:
    df: pd.DataFrame
    trades: pd.DataFrame
    equity: pd.Series
    naive_equity: pd.Series
    equity_mtm: pd.Series           # NEW: per-bar MTM curve
    metrics: Dict[str, Any]
    config_used: Dict[str, Any]
    signals: Dict[str, int] = field(default_factory=dict)
```

Aggiornare il return statement:

```python
return BacktestResult(
    df=df,
    trades=trades,
    equity=equity,
    naive_equity=naive,
    equity_mtm=equity_mtm,   # NEW
    metrics=metrics,
    config_used=cfg_merged,
    signals=sig_counts,
)
```

### Test da scrivere

File: `tests/test_risk_sizing.py`, nuova classe `TestMtmEquityCurve`:

| # | Test | Cosa verifica |
|---|---|---|
| 1 | `test_mtm_flat_when_no_trades` | Senza trade, la curva è flat a initial_equity |
| 2 | `test_mtm_ramps_up_during_open_trade` | Durante un trade long vincente, l'equity MTM sale con il close |
| 3 | `test_mtm_snaps_to_cash_on_exit` | Dopo l'exit, equity_mtm[-1] == equity_after dell'ultimo trade |
| 4 | `test_mtm_handles_overlapping_trades` | Due trade sovrapposti: MTM somma i PnL di entrambi |
| 5 | `test_mtm_entry_exit_same_bar` | Trade che apre e chiude sulla stessa barra |
| 6 | `test_mtm_is_bar_aligned` | `len(equity_mtm) == len(df)` e stesso indice |

---

## Step 2 — Fix Sharpe/Sortino

**Bug:** #1 (Sharpe/Sortino broken)  
**File:** `utils/metrics.py::calculate_all_metrics`

### Modifica

La funzione `calculate_all_metrics` attualmente riceve `(trade_returns, equity, periods_per_year)`. Dopo lo Step 1, possiamo passare anche la curva MTM.

**Opzione scelta:** Aggiungere un parametro opzionale `equity_mtm` alla funzione. Se fornito, lo usa per Sharpe/Sortino. Se non fornito, usa il comportamento legacy (backward-compatible).

```python
def calculate_all_metrics(
    trade_returns: pd.Series,
    equity: pd.Series,
    periods_per_year: Optional[int] = None,
    equity_mtm: Optional[pd.Series] = None,  # NEW
) -> Dict[str, Any]:
```

E nel blocco Sharpe/Sortino:

```python
# Time-series metrics: prefer MTM curve when available,
# fall back to trade-exit equity curve for backward compatibility.
curve_for_ts = equity_mtm if (equity_mtm is not None and len(equity_mtm) > 1) else equity
if periods_per_year is not None and len(curve_for_ts) > 1:
    periodic_returns = curve_for_ts.pct_change().dropna()
    metrics["sharpe_ratio"] = sharpe_ratio(periodic_returns, periods_per_year=periods_per_year)
    metrics["sortino_ratio"] = sortino_ratio(periodic_returns, periods_per_year=periods_per_year)
```

In `run_backtest`:

```python
metrics = calculate_all_metrics(
    trade_returns, equity,
    periods_per_year=periods_per_year,
    equity_mtm=equity_mtm,    # NEW
)
```

**Risultato atteso:** Su SPY 1500 barre, Sharpe dovrebbe passare da −22.68 a un valore nell'intervallo [−2, +2], riflettendo la reale performance risk-adjusted.

### Test da aggiornare

In `tests/test_metrics.py`:
- Test esistente `test_calculate_all_metrics` deve ancora passare (backward compat — `equity_mtm=None` usa `equity`)
- Nuovo test: `test_calculate_all_metrics_with_mtm` — verifica che Sharpe/Sortino siano diversi (e più ragionevoli) quando si passa `equity_mtm`

---

## Step 3 — Drawdown corretto

**Bug:** #4 (Drawdown understated)  
**File:** `utils/metrics.py::calculate_all_metrics`

Già risolto dallo Step 1 — la curva MTM per-bar cattura il drawdown intra-trade. Nessuna modifica aggiuntiva necessaria: `max_drawdown(equity_mtm)` riflette automaticamente le perdite intra-trade.

**Verifica:** Su un trade long che perde il 20% mid-trade e chiude a −5%, la MTM curve toccherà −20% e il drawdown sarà −20%, non −5%.

---

## Step 4 — Rilassare regime filter + diagnostica

**Bug:** #2 (Regime troppo restrittivo)  
**File:** `config.yaml`, `filters/regime.py`

### 4a — Configurazione

In `config.yaml`, modificare i default:

```yaml
regime_filter:
  adx_threshold: 25              # was 22 — textbook "non-trending" threshold
  hurst_threshold: 0.55          # was 0.45 — allows slightly random-walk regimes
  atr_relative_std_threshold: 2.0  # unchanged
  min_regime_coverage_pct: 10    # was 20 — relaxed because 16% is the new normal
  max_regime_coverage_pct: 70    # unchanged
```

**Razionale:**
- ADX < 25: soglia standard per "assenza di trend" in letteratura
- Hurst < 0.55: su barre a 15 minuti, l'esponente di Hurst fluttua intorno a 0.5; 0.45 era irraggiungibile nella pratica
- min_regime_coverage_pct: abbassato a 10% per riflettere che su timeframe intraday la copertura è fisiologicamente più bassa

### 4b — Diagnostica per-componente

In `filters/regime.py`, aggiungere helper:

```python
def regime_component_breakdown(df: pd.DataFrame) -> Dict[str, float]:
    """
    Return the pass rate of each regime filter component.

    Returns
    -------
    dict
        {
            "adx_pass_pct": float,       # % bars where ADX < threshold
            "hurst_pass_pct": float,     # % bars where Hurst < threshold
            "atr_rel_z_pass_pct": float, # % bars where ATR z-score < threshold
            "all_pass_pct": float,       # % bars where ALL three pass (= regime_ok)
            "n_bars": int,               # total bars evaluated
        }
    """
    needed = {"adx", "hurst", "atr_rel_z", "regime_ok"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns for regime breakdown: {missing}")

    n = len(df)
    return {
        "adx_pass_pct": float((df["adx"] < adx_threshold).mean() * 100) if "adx" in df.columns else ... wait, the function doesn't have the thresholds. Let me reconsider...

# Better design: the function needs the same thresholds used to produce regime_ok.
# Option A: read from config.yaml
# Option B: accept thresholds as parameters
# Option C: recompute component masks independently

# Option B is cleanest:
def regime_component_breakdown(
    df: pd.DataFrame,
    adx_threshold: float = 22.0,
    hurst_threshold: float = 0.45,
    atr_relative_std_threshold: float = 2.0,
) -> Dict[str, float]:
```

L'helper viene chiamato nel demo per stampare la diagnostica:

```python
# In scripts/demo_e2e.py, dopo il backtest:
from filters.regime import regime_component_breakdown
breakdown = regime_component_breakdown(result.df, **result.config_used["regime_filter"])
print(f"  ADX pass: {breakdown['adx_pass_pct']:.1f}%")
print(f"  Hurst pass: {breakdown['hurst_pass_pct']:.1f}%")
print(f"  ATR z-score pass: {breakdown['atr_rel_z_pass_pct']:.1f}%")
print(f"  Combined (regime_ok): {breakdown['all_pass_pct']:.1f}%")
```

### Test da scrivere

File: `tests/test_filters.py` (esistente), nuovi test:

| # | Test | Cosa verifica |
|---|---|---|
| 1 | `test_regime_component_breakdown_sums_correctly` | I tre pass rate sono coerenti con regime_ok |
| 2 | `test_regime_component_breakdown_raises_on_missing_columns` | ValueError se mancano colonne |

---

## Step 5 — Ridurre signal overlap + segnali skippati

**Bug:** #3 (56% signal loss)  
**File:** `config.yaml`, `signals/exit.py`, `backtest/engine.py`

### 5a — Configurazione

In `config.yaml`:

```yaml
exit:
  atr_multiplier: 1.5
  max_bars: 12                     # was 25 — 3 ore max hold (12 × 15min)
  adx_stop_threshold: 25
```

**Razionale:** Su timeframe 15-min, 25 barre = 6.25 ore = quasi l'intera sessione. Un trade che non ha revertito entro 3 ore probabilmente non revertirà. Ridurre a 12 barre (3 ore) dimezza la finestra di overlap e forza uscite più rapide.

### 5b — Contatore segnali skippati

In `signals/exit.py::simulate_all_trades`:

```python
def simulate_all_trades(
    df: pd.DataFrame,
    cfg: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    # ... existing code ...

    trades: List[ExitResult] = []
    last_exit_pos = -1

    # --- Modificato: conta i segnali skippati
    total_signals = len(signals)
    skipped = 0

    for pos, direction in signals:
        if pos <= last_exit_pos:
            skipped += 1
            continue

        result = simulate_exit(...)
        trades.append(result)
        last_exit_pos = result["exit_idx"]

    # Attacca il contatore come attributo del DataFrame
    result_df = pd.DataFrame(trades) if trades else pd.DataFrame(columns=TRADE_LOG_COLUMNS)
    result_df.attrs["signals_total"] = total_signals
    result_df.attrs["signals_skipped"] = skipped
    result_df.attrs["signals_executed"] = total_signals - skipped

    return result_df
```

### 5c — Aggiungere `signals_skipped` a `BacktestResult`

```python
@dataclass
class BacktestResult:
    df: pd.DataFrame
    trades: pd.DataFrame
    equity: pd.Series
    naive_equity: pd.Series
    equity_mtm: pd.Series
    metrics: Dict[str, Any]
    config_used: Dict[str, Any]
    signals: Dict[str, int] = field(default_factory=dict)
    signals_skipped: int = 0     # NEW
```

In `run_backtest`, dopo `simulate_all_trades`:

```python
trades = simulate_all_trades(df, cfg=cfg_merged["exit"])
signals_skipped = trades.attrs.get("signals_skipped", 0)  # NEW
```

E nel return:

```python
return BacktestResult(
    ...
    signals=sig_counts,
    signals_skipped=signals_skipped,  # NEW
)
```

### Test da aggiornare/scrivere

Nel nuovo test o in `test_signals.py`:

| # | Test | Cosa verifica |
|---|---|---|
| 1 | `test_signals_skipped_counted` | Due segnali overlappati: il secondo viene skippato e il contatore è 1 |
| 2 | `test_signals_skipped_zero_when_no_overlap` | Segnali distanziati: skipped=0 |

---

## Riepilogo modifiche per file

| File | Step | Tipo modifica |
|---|---|---|
| `risk/sizing.py` | 1 | Nuova funzione `build_mtm_equity_curve` |
| `utils/metrics.py` | 2 | Nuovo parametro `equity_mtm` in `calculate_all_metrics` |
| `backtest/engine.py` | 1, 2, 5 | Chiama `build_mtm_equity_curve`, passa `equity_mtm`, nuovo field `signals_skipped` |
| `config.yaml` | 4, 5 | `adx_threshold: 25`, `hurst_threshold: 0.55`, `min_regime_coverage_pct: 10`, `max_bars: 12` |
| `filters/regime.py` | 4 | Nuova funzione `regime_component_breakdown` |
| `signals/exit.py` | 5 | Contatore `skipped` in `simulate_all_trades`, attributi `.attrs` |
| `scripts/demo_e2e.py` | 4 | Stampa diagnostica regime per-componente |
| `tests/test_risk_sizing.py` | 1 | Nuovi test MTM curve (6 test) |
| `tests/test_metrics.py` | 2 | Test Sharpe/Sortino con MTM |
| `tests/test_filters.py` | 4 | Test diagnostica regime |
| `tests/test_signals.py` | 5 | Test contatore segnali skippati |

**Test target post-fix:** ~215 test (201 baseline + 6 MTM + 2 metrics + 2 regime + 2 signals + ~2 integration)

---

## Checklist post-implementazione

- [ ] `python -m pytest tests/ -q` — tutti i test passano
- [ ] `python scripts/demo_e2e.py --symbol SPY --n-bars 1500` — demo funzionante
- [ ] Sharpe ratio non è più negativo a doppia cifra (deve essere tra −3 e +3)
- [ ] Sortino ratio non è più negativo a tripla cifra
- [ ] Regime coverage > 10% con i nuovi default (verificare con breakdown)
- [ ] Signal overlap < 30% (max_bars=12 riduce la finestra)
- [ ] `signals_skipped` visibile nell'output del demo
- [ ] Curva MTM ha `len(df)` punti (verificabile con assert nel demo)
- [ ] `python scripts/visual_check_sizing.py` — FASE 3 invariata
