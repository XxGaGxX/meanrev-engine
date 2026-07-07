# Fix Plan — Mean Reversion Intraday Code Review

**Data review:** 2026-07-06
**File revisioni:** 14 file Python/YAML
**Fasi implementate:** FASE 0 (infrastruttura) + FASE 1 (indicatori + filtro regime)
**Fasi mancanti:** FASE 2 (segnali ingresso), FASE 3 (uscite), FASE 4 (sizing), FASE 5 (backtest)

---

## Executive Summary

Sono stati identificati **19 issues** nel codice implementato finora, di cui:
- **6 CRITICAL** — causano errori a runtime o comportamento di trading scorretto
- **9 MEDIUM** — impattano robustezza, manutenibilità o correttezza concettuale
- **4 LOW** — ottimizzazione, documentazione, missing features

**Raccomandazione:** Eseguire tutti i fix CRITICAL e MEDIUM prima di procedere con FASE 2+. I fix LOW possono essere rimandati.

---

## 1. Issues CRITICAL 🔴

### C1 — `requirements.txt`: versione NumPy inesistente

**File:** `requirements.txt`  
**Problema:** `numpy==2.4.6` non esiste. L'ultima release della serie 2.x è `2.2.x` (es. 2.2.4). `pip install` fallirà con:
```
ERROR: Could not find a version that satisfies the requirement numpy==2.4.6
```

**Fix:** Cambiare in una versione valida e compatibile:
```
numpy==2.2.4
```

**Nota aggiuntiva:** Verificare compatibilità `vectorbt==1.1.0` con numpy 2.x. Se incompatibile, usare `vectorbt==0.26.2` (ultima stabile) o aggiornare numpy a versione supportata.

---

### C2 — `utils/metrics.py`: import mancante `Optional`

**File:** `utils/metrics.py`  
**Problema:** La funzione `calculate_all_metrics` dichiara `periods_per_year: Optional[int] = None` ma `Optional` non è importato da `typing`. Causerà `NameError`.

**Fix:** Aggiungere `Optional` all'import:
```python
from typing import List, Dict, Any, Optional
```

---

### C3 — `indicators/zscore.py`: divisione per zero

**File:** `indicators/zscore.py`  
**Problema:** Se i prezzi sono flat in tutta la rolling window (es. titolo sospeso, gap di dati), `rolling_std.std()` = 0. La divisione `(close - mean) / 0` produce `inf` o `NaN`, che si propagano nei segnali e nel filtro regime.

**Fix:** Aggiungere protezione divisione per zero:
```python
rolling_std_val = rolling_std.std()
df["zscore"] = np.where(
    rolling_std_val != 0,
    (df["close"] - rolling_mean.mean()) / rolling_std_val,
    0.0  # o np.nan, ma 0.0 è più sicuro per il filtro
)
```

---

### C4 — `indicators/hurst.py`: `np.log(tau)` su valori zero

**File:** `indicators/hurst.py`  
**Problema:** Se `tau` contiene zeri (prezzi flat, `np.std()` = 0 su differenze costanti), `np.log(tau)` produce `-inf`, corrompendo `np.polyfit` e restituendo Hurst nonsensical.

**Fix:** Filtrare zeri prima del log:
```python
tau = [np.std(np.subtract(ts[lag:], ts[:-lag])) for lag in lags]
tau = [t for t in tau if t > 0]  # filtra zeri
if len(tau) < 2:
    return np.nan
# oppure usare np.log con maschera
```

---

### C5 — `filters/regime.py`: divisione per zero in ATR z-score

**File:** `filters/regime.py`  
**Problema:** Se `atr_rel_std` è 0 (ATR costante per tutta la window), la divisione `(atr_rel - mean) / 0` produce `inf`/`NaN`. Il confronto `NaN < 2.0` è sempre `False`, quindi `regime_ok = False` silenziosamente per quelle barre.

**Fix:** Proteggere la divisione:
```python
atr_rel_std_safe = atr_rel_std.replace(0, np.nan)
df["atr_rel_z"] = (df["atr_rel"] - atr_rel_mean) / atr_rel_std_safe
# oppure impostare regime_ok a False esplicitamente dove atr_rel_z è NaN
```

---

### C6 — `data/fetch.py`: `TimeFrame.Minute` ambiguo per 1Min

**File:** `data/fetch.py`  
**Problema:** Nel mapping timeframe, `"1Min"` mappa a `TimeFrame.Minute`. In `alpaca-py`, `TimeFrame.Minute` è un alias per 1 minuto, ma per consistenza con gli altri timeframe (5Min, 15Min che usano `TimeFrame(N, TimeFrameUnit.Minute)`), è meglio usare la forma esplicita.

**Fix:** Uniformare tutti i timeframe:
```python
mapping = {
    "1Min": TimeFrame(1, TimeFrameUnit.Minute),
    "5Min": TimeFrame(5, TimeFrameUnit.Minute),
    "15Min": TimeFrame(15, TimeFrameUnit.Minute),
    "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
    "1Day": TimeFrame(1, TimeFrameUnit.Day),
}
```

---

## 2. Issues MEDIUM 🟡

### M1 — `backtrader` compatibilità con pandas 3.x

**File:** `requirements.txt` (dipendenza)  
**Problema:** `backtrader==1.9.78.123` ha problemi noti di compatibilità con `pandas>=2.2`. Il progetto usa `pandas==3.0.3`. Durante l'import o l'esecuzione potrebbero verificarsi errori di tipo `AttributeError` su metodi pandas rimossi/deprecati.

**Fix opzioni:**
1. **Opzione A (raccomandata):** Usare `backtrader2` (fork mantenuto) oppure verificare con test rapido:
   ```bash
   python -c "import backtrader; print(backtrader.__version__)"
   ```
2. **Opzione B:** Downgrade pandas a `2.1.4` (ultima versione nota funzionante con backtrader).
3. **Opzione C:** Sostituire backtrader con `vectorbt` per tutto il backtesting (più moderno, nativo pandas).

**Azione:** Testare import backtrader nel venv. Se fallisce, applicare Opzione A o B.

---

### M2 — Manca un config loader in Python

**File:** Manca `utils/config.py`  
**Problema:** `config.yaml` è ben strutturato ma nessun modulo Python lo legge. Ogni indicatore/filtro ha i default hardcodati, creando drift tra codice e configurazione.

**Fix:** Creare `utils/config.py`:
```python
import os
import yaml
from pathlib import Path
from typing import Any, Dict

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

class Config:
    def __init__(self, path: str = None):
        path = path or os.getenv("CONFIG_PATH", _CONFIG_PATH)
        with open(path, "r") as f:
            self._cfg = yaml.safe_load(f)

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        val = self._cfg
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k, default)
            else:
                return default
        return val

    @property
    def raw(self) -> Dict:
        return self._cfg

# Singleton instance
config = Config()
```

---

### M3 — `__init__.py` vuoti in tutti i pacchetti

**File:** `data/__init__.py`, `indicators/__init__.py`, `filters/__init__.py`, ecc.  
**Problema:** I pacchetti sono vuoti. Import come `from indicators import add_adx` falliscono. Serve importare le funzioni pubbliche.

**Fix:** Popolare ogni `__init__.py` con le esportazioni pubbliche. Esempio per `indicators/__init__.py`:
```python
from .adx import add_adx
from .hurst import add_hurst
from .rsi import add_rsi
from .bollinger import add_bollinger
from .zscore import add_zscore
from .volume import add_volume_filter
from .atr import add_atr

__all__ = [
    "add_adx", "add_hurst", "add_rsi", "add_bollinger",
    "add_zscore", "add_volume_filter", "add_atr",
]
```

---

### M4 — Nessuna validazione input negli indicatori

**File:** Tutti i file in `indicators/`  
**Problema:** Ogni indicatore accede a colonne (`df["close"]`, `df["high"]`, ecc.) senza verificare che esistano. Se il DataFrame ha colonne mancanti, l'errore è un `KeyError` poco informativo.

**Fix:** Aggiungere validazione standardizzata in ogni indicatore:
```python
_REQUIRED_COLS = {"close"}

def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"add_rsi missing columns: {missing}")
    # ... resto della funzione
```

**Nota:** Si potrebbe creare un decorator o helper in `utils/` per evitare ripetizione.

---

### M5 — Manca una pipeline per concatenare indicatori

**File:** Manca `indicators/pipeline.py`  
**Problema:** Non c'è un modo standard per applicare tutti gli indicatori in sequenza. La documentazione suggerisce `build_all_indicators()` ma non è implementata.

**Fix:** Creare `indicators/pipeline.py`:
```python
from .adx import add_adx
from .hurst import add_hurst
from .rsi import add_rsi
from .bollinger import add_bollinger
from .zscore import add_zscore
from .volume import add_volume_filter
from .atr import add_atr

def build_all_indicators(df, cfg=None):
    cfg = cfg or {}
    df = add_adx(df, **cfg.get("adx", {}))
    df = add_hurst(df, **cfg.get("hurst", {}))
    df = add_rsi(df, **cfg.get("rsi", {}))
    df = add_bollinger(df, **cfg.get("bollinger", {}))
    df = add_zscore(df, **cfg.get("zscore", {}))
    df = add_volume_filter(df, **cfg.get("volume", {}))
    df = add_atr(df, **cfg.get("atr", {}))
    return df
```

---

### M6 — `utils/metrics.py`: `max_drawdown_duration` conta indici non tempo

**File:** `utils/metrics.py`  
**Problema:** `max_drawdown_duration` conta il numero di posizioni consecutive nell'indice della Series, non il tempo effettivo trascorso. Se i trade sono irregolari (es. 3 trade in un giorno, poi nessuno per una settimana), la durata "3" è fuorviante.

**Fix:** Opzioni:
1. Rinominare in `max_drawdown_bars` per chiarezza (se la Series è a frequenza fissa).
2. Oppure calcolare la durata in tempo usando gli indici datetime:
   ```python
   def max_drawdown_duration(equity_curve: pd.Series) -> pd.Timedelta:
       # ... calcola inizio/fine drawdown, restituisci timedelta
   ```

---

### M7 — `utils/metrics.py`: Sharpe/Sortino su trade returns è concettualmente errato

**File:** `utils/metrics.py`  
**Problema:** La funzione `calculate_all_metrics` accetta `trade_returns` e, se `periods_per_year` è fornito, lo passa a `sharpe_ratio`/`sortino_ratio`. Ma Sharpe e Sortino richiedono **rendimenti periodici** (es. giornalieri, mensili) equispaziati nel tempo, non rendimenti per-trade che sono eventi irregolari.

**Fix:** Modificare `calculate_all_metrics` per calcolare Sharpe/Sortino dalla curva di equity:
```python
if periods_per_year is not None:
    # Calcola rendimenti periodici dalla equity curve
    periodic_returns = equity.pct_change().dropna()
    metrics["sharpe_ratio"] = sharpe_ratio(periodic_returns, periods_per_year=periods_per_year)
    metrics["sortino_ratio"] = sortino_ratio(periodic_returns, periods_per_year=periods_per_year)
```

---

### M8 — `config.yaml`: commissione non realistica per Alpaca

**File:** `config.yaml`  
**Problema:** `backtest.commission_per_side: 0.001` (0.1% per lato). Alpaca offre **$0 commissioni** su azioni USA. Con 0.1% per lato, il backtest sarà troppo pessimista per questo broker.

**Fix:** Impostare a 0 per Alpaca, con commento:
```yaml
backtest:
  commission_per_side: 0.0       # Alpaca: $0 commission on US equities
  slippage_pct: 0.0005           # 0.05% slippage (conservative)
```

---

### M9 — `data/clean.py`: `filter_session_hours` non gestisce pre/after market

**File:** `data/clean.py`  
**Problema:** Se i dati di Alpaca includono orari estesi (pre-market o after-hours, che sono disponibili con alcuni piani), la funzione `filter_session_hours` li includerebbe perché i tempi tra `10:00` e `15:30` includono anche orari pre-market se presenti.

**Fix:** Aggiungere filtro per giorno della settimana e range orario stretto:
```python
# Aggiungere dentro filter_session_hours:
# Filtra solo giorni feriali (lunedì-venerdì)
df = df[df.index.dayofweek < 5]
# Il filtro orario esistente è sufficiente se i dati sono solo regolari,
# ma aggiungere un check opzionale per escludere pre-market/after-hours:
regular_hours = (df.index.time >= pd.Timestamp("09:30").time()) & \
                (df.index.time <= pd.Timestamp("16:00").time())
df = df[regular_hours]
```

---

## 3. Issues LOW 🟢

### L1 — Performance Hurst Exponent molto lenta

**File:** `indicators/hurst.py`  
**Problema:** `rolling(window=252).apply(lambda ...)` con Python puro è estremamente lento su dataset grandi (2+ anni di dati a 15 min = ~10k+ barre). Ogni rolling window ricalcola Hurst da zero in Python.

**Fix (ottimizzazione futura):**
- Implementare versione vettorizzata con `numba` o `cython`
- Oppure calcolare Hurst solo ogni N barre (es. ogni 20 barre) e interpolare
- Oppure usare `statsmodels` o `arch` library per Hurst ottimizzato

**Nota:** Per la fase di sviluppo, la versione corrente è accettabile. Ottimizzare solo se diventa un bottleneck.

---

### L2 — Mancano unit tests per tutti i moduli

**File:** Manca `tests/`  
**Problema:** Zero test coverage. Nessuna validazione automatica che gli indicatori producano output corretti.

**Fix:** Creare struttura test minima:
```
tests/
  test_indicators.py
  test_filters.py
  test_metrics.py
  test_fetch.py
```

Esempio test indicatore:
```python
def test_add_rsi():
    df = pd.DataFrame({"close": [100]*14 + [110]})
    df = add_rsi(df)
    assert "rsi" in df.columns
    assert df["rsi"].iloc[-1] > 50  # dovrebbe essere ipercomprato
```

---

### L3 — `data/fetch.py`: `create_live_stream` non sottoscrive simboli

**File:** `data/fetch.py`  
**Problema:** Il parametro `symbols` in `create_live_stream` è accettato ma non usato. Lo stream viene creato ma non sottoscrive automaticamente ai simboli.

**Fix:** Documentare chiaramente che la sottoscrizione è manuale, oppure creare metodo helper:
```python
def create_live_stream(self, symbols: List[str]):
    stream = StockDataStream(self.api_key, self.secret_key, feed=DataFeed.US_EQUITIES)
    # Nota: la sottoscrizione è manuale
    # stream.subscribe_bars(handler, *symbols)
    return stream
```

---

### L4 — `config.yaml`: `historical_end` nel passato ma lontano

**File:** `config.yaml`  
**Problema:** `historical_end: "2024-12-31"` è nel passato (siamo a luglio 2026). I dati fino a oggi non verranno mai fetchati automaticamente.

**Fix:** Lasciare `end=None` nel codice di fetch (che defaulta a ieri) oppure aggiornare la data, ma meglio rimuovere `historical_end` dal config o impostarlo a `null`:
```yaml
data:
  historical_start: "2022-01-01"
  historical_end: null  # null = fino a ieri
```

---

## 4. Azioni Consigliate per Priorità

### Sprint 1 — Fix CRITICAL (bloccanti) ✅ COMPLETATO

| # | Task | File | Stima | Stato |
|---|------|------|-------|-------|
| C1 | Fix versione numpy in requirements.txt | `requirements.txt` | 2 min | ✅ `numpy==2.2.4`, stack verificato |
| C2 | Aggiungere `Optional` all'import | `utils/metrics.py` | 2 min | ✅ Import aggiunto |
| C3 | Proteggere divisione per zero in zscore | `indicators/zscore.py` | 5 min | ✅ `np.where(rolling_std != 0, ...)` |
| C4 | Filtrare zeri in hurst `np.log(tau)` | `indicators/hurst.py` | 5 min | ✅ Lista valid filtrata, check `len < 2` |
| C5 | Proteggere divisione per zero in regime ATR z | `filters/regime.py` | 5 min | ✅ `np.where(atr_rel_std != 0, ...)` |
| C6 | Uniformare timeframe mapping a forma esplicita | `data/fetch.py` | 3 min | ✅ `TimeFrame(N, TimeFrameUnit.Unit)` |
| — | Fix `DataFeed.SIP` | `data/fetch.py` | — | ✅ `US_EQUITIES` → `SIP` |

**Totale Sprint 1:** ~20 min — **COMPLETATO**

### Sprint 2 — Fix MEDIUM (robustezza) ✅ COMPLETATO

| # | Task | File | Stima | Stato |
|---|------|------|-------|-------|
| M1 | Testare compatibilità backtrader + pandas 3.x | `requirements.txt` | 10 min | ✅ backtrader, vectorbt, talib, pandas OK |
| M2 | Creare config loader Python | `utils/config.py` (nuovo) | 15 min | ✅ Dot-notation, singleton, FNF check |
| M3 | Popolare `__init__.py` con exports | 8 file `__init__.py` | 10 min | ✅ Tutti popolati |
| M4 | Aggiungere validazione colonne negli indicatori | 7 file in `indicators/` | 15 min | ✅ `_REQUIRED_COLS` in tutti |
| M5 | Creare pipeline indicatori | `indicators/pipeline.py` (nuovo) | 10 min | ✅ `build_all_indicators()` con kwargs filter |
| M6 | Rinominare/fix `max_drawdown_duration` | `utils/metrics.py` | 5 min | ✅ `max_drawdown_bars`, alias deprecato |
| M7 | Fix Sharpe/Sortino per usare equity curve | `utils/metrics.py` | 10 min | ✅ `equity.pct_change()` per rendimenti periodici |
| M8 | Aggiornare commissione Alpaca | `config.yaml` | 2 min | ✅ `0.0` |
| M9 | Aggiungere filtro pre-market/after-hours | `data/clean.py` | 5 min | ✅ Weekend + regular hours filter |

**Totale Sprint 2:** ~80 min — **COMPLETATO**

### Sprint 3 — Fix LOW (qualità) ✅ COMPLETATO

| # | Task | File | Stima | Stato |
|---|------|------|-------|-------|
| L1 | Nota performance Hurst | `indicators/hurst.py` | 5 min | ✅ Docstring aggiunta |
| L2 | Creare test suite minima | `tests/` (nuovo) | 30 min | ✅ 59 test in 7 file, tutti pass |
| L3 | Documentare `create_live_stream` | `data/fetch.py` | 2 min | ✅ Docstring con esempio |
| L4 | Aggiornare `historical_end` | `config.yaml` | 2 min | ✅ `null` |
| — | Integration test E2E | `tests/test_integration.py` | — | ✅ fetch→clean→indicators→filter→metrics |

**Totale Sprint 3:** ~60 min — **COMPLETATO**

---

## 5. Issues di Design / Fasi Mancanti

### ✅ FASE 0 — Infrastruttura COMPLETATA
- `data/fetch.py`, `data/clean.py`, `utils/metrics.py`, `utils/config.py`
- Config loader, `__init__.py` exports, test suite (87 test)

### ✅ FASE 1 — Indicatori + Filtro Regime COMPLETATA
- 7 indicatori (`adx`, `hurst`, `rsi`, `bollinger`, `zscore`, `volume`, `atr`)
- `filters/regime.py` con filtro combinato
- `indicators/pipeline.py` per concatenazione

### ✅ FASE 2 — Segnali di Ingresso/Uscita COMPLETATA
- `signals/entry.py` — segnali long/short con tripla conferma
- `signals/exit.py` — simulazione uscite (SL, TP, regime, time, nan_data)
- 25 test in `tests/test_signals.py`, tutti passanti

### ⏳ Fasi rimanenti

| Fase | Modulo Mancante | Impatto |
|------|-----------------|---------|
| ~~FASE 3~~ | ~~`risk/sizing.py` — Position sizing + Kelly~~ | ✅ COMPLETATA |
| FASE 4 | `backtest/engine.py` — Motore Backtrader | Nessun backtest |
| FASE 5 | `backtest/walk_forward.py` — Walk-Forward Analysis | Validazione anti-overfitting |
| FASE 6 | `backtest/monte_carlo.py` — Monte Carlo Simulation | Stima drawdown realistica |
| FASE 7 | `live/paper.py` — Paper Trading | Validazione live |

**Raccomandazione:** Procedere con FASE 4 (Backtest Engine).

### ✅ FASE 3 — Position Sizing COMPLETATA
- `risk/sizing.py` con `calculate_shares`, `kelly_risk_pct`, `apply_position_sizing`, `build_equity_curve`
- Formula volatility-targeted: `shares = (equity × risk% / 100) / (ATR × atr_multiplier)`
- Kelly frazionato opzionale cappato a `risk_cap_pct` (2%)
- Guard rail: zero size su input non finiti / equity ≤ 0 / ATR ≤ 0
- Slippage e commissioni applicate in `apply_position_sizing` (sustituiscono la curva equal-weight del demo)
- `signals/exit.py` resta puro e backward-compatible con i 25 test esistenti
- `scripts/demo_e2e.py::build_equity_curve` ora delega a `risk.sizing.build_equity_curve`
- 25 nuovi test in `tests/test_risk_sizing.py` (formula, cap, share rounding, Kelly, slippage, commission)

---

## 6. Checklist Post-Fix

Dopo aver applicato tutti i fix CRITICAL e MEDIUM, verificare:

- [ ] `pip install -r requirements.txt` completa senza errori
- [ ] `python -c "import backtrader; print('OK')"` funziona
- [ ] `python -m py_compile data/fetch.py data/clean.py utils/metrics.py indicators/*.py filters/regime.py` passa
- [ ] Ogni indicatore lancia `ValueError` con messaggio chiaro se manca una colonna
- [ ] `utils/config.py` legge `config.yaml` e restituisce i valori corretti
- [ ] `from indicators import add_rsi` funziona (non `from indicators.rsi import add_rsi`)
- [ ] Z-score su prezzi flat restituisce 0.0 (non inf/NaN)
- [ ] Hurst su prezzi flat restituisce np.nan (non crash)
- [ ] Regime filter su ATR costante gestisce il caso gracefully

---

*Questo fix plan è stato generato dalla code review del 2026-07-06. Da aggiornare man mano che i fix vengono applicati.*
