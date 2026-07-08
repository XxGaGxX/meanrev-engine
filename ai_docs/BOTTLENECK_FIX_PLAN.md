# 🔴 Bottleneck Fix Plan — Hurst Filter & Soft Regime Scoring

**Data:** 2026-07-07  
**Backtest:** SPY 15-min, 3.712 bar → 1.334 post-pipeline, 7 trade in ~3 mesi  
**Bottleneck identificato:** Filtro Hurst (20.4% pass rate vs ADX 65.4%, ATR 97.0%)  
**Trade frequency:** 7 trade in 3 mesi — statisticamente insufficiente (minimo 30 per `config.yaml`)  

---

## 1. Root Cause Analysis (Quant Perspective)

### 1.1 Il problema

```
Regime filter component breakdown (1.334 bars):
  ADX pass:     65.4%   ← OK, soglia 25 ragionevole
  Hurst pass:   20.4%   ← 🔴 BOTTLENECK: 80% delle barre respinte
  ATR z pass:   97.0%   ← OK, quasi tutte passano
  Combined:     16.0%   ← Solo 213 barre su 1.334
```

Il filtro Hurst da solo elimina l'80% delle barre. Questo accade perché:

1. **Duration mismatch:** La finestra rolling di 252 barre a 15 minuti copre ~9 giorni di trading. Lo SPY in Q2 2026 è stato in un forte trend rialzista (bull market). Su questa finestra, l'Hurst exponent legge sistematicamente H > 0.5 (persistenza), il che è corretto per il trend strutturale.

2. **Il problema:** La mean reversion intraday opera su micro-strutture (1-2 giorni, non 9). Un pullback di 30 minuti all'interno di un trend rialzista di 9 giorni È un'opportunità di mean reversion valida, ma il filtro lo blocca perché lo Hurst "lento" dice "stiamo trendando".

3. **Logica AND binaria:** `ADX < soglia AND Hurst < soglia AND ATR < soglia` è eccessivamente restrittiva. Non c'è compensazione: una barra con ADX=10 (molto buono) e ATR_rel_z=-1 (molto buono) viene comunque scartata se Hurst=0.56 (marginalmente sopra 0.55).

### 1.2 Perché 7 trade non sono sufficienti

- `config.yaml` richiede `min_signals_per_asset: 30`
- Con 7 trade, qualsiasi metrica (Sharpe, win rate, profit factor) è **statisticamente insignificante**
- Un singolo trade determina il 14% del risultato totale → Sharpe = -1.78 è rumoroso, non informativo
- Per avere validità statistica servono **almeno 30-50 trade**, idealmente 100+

### 1.3 Implicazioni per la strategia

La mean reversion intraday **funziona** catturando micro-pullback (1-2 ore) all'interno di trend più ampi. Il filtro Hurst lento sta bloccando esattamente il tipo di trade che la strategia dovrebbe catturare. Non è un problema di strategia sbagliata — è un problema di **filtro mal calibrato per il timeframe operativo**.

---

## 2. Strategia di Fix — Raccomandazione

Dopo analisi quantitativa, si raccomandano **due fix complementari** implementati in sequenza:

| # | Fix | Impatto atteso | Complessità |
|---|-----|---------------|-------------|
| **A** | Fast Hurst (window=50) per entry filter | +3-5× trade frequency | Media |
| **B** | Soft regime scoring (weighted, non AND) | +Sharpe ratio, +robustezza | Media |

### Fix A: Multi-Window Hurst (Primario)

**Cosa cambia:**
- **Hurst lento** (window=252): rimane come indicatore di "regime strutturale", usato per lo scoring ma non come bloccante hard
- **Hurst veloce** (window=50, ~2 giorni di trading a 15 min): nuovo indicatore che cattura la micro mean reversion intraday
- Il filtro di regime usa lo Hurst **veloce** per decidere se tradare, non quello lento

**Perché funziona:**
- Hurst(50) su 15 min = ~2 giorni di trading. Cattura il comportamento mean-reverting di breve termine (pullback intraday) anche quando il trend di 9 giorni è rialzista
- Aumenta la frequenza di trade del 3-5× (dal 20% al 50-60% di pass rate atteso)
- Non rimuove completamente il filtro — continua a bloccare barre con forte micro-trend

**File da modificare:**
| File | Modifica |
|------|----------|
| `indicators/hurst.py` | Aggiungere `add_hurst_fast()` con window=50 |
| `indicators/pipeline.py` | Aggiungere calcolo `hurst_fast` nel pipeline |
| `filters/regime.py` | Usare `hurst_fast` invece di `hurst` nel filtro, aggiungere `hurst_slow` per breakdown |
| `config.yaml` | Aggiungere `hurst_fast_window: 50` nella sezione `indicators.hurst` |

### Fix B: Soft Regime Scoring (Secondario, dopo validazione Fix A)

**Cosa cambia:**
- Invece di `regime_ok = ADX_ok AND Hurst_ok AND ATR_ok` (binario), si calcola:
  ```
  regime_score = 0.40 × adx_score + 0.40 × hurst_score + 0.20 × atr_score
  ```
  dove ogni `_score` è un valore continuo [0, 1] normalizzato rispetto alla soglia
- `regime_ok = regime_score >= 0.50` (soglia configurabile)
- Il position sizing può scalare con `regime_score` (size = base × regime_score)

**Perché funziona:**
- Una barra con ADX eccellente (score=0.9) e ATR perfetta (score=1.0) può compensare uno Hurst marginale (score=0.4 → totale = 0.9×0.4 + 0.4×0.4 + 1.0×0.2 = 0.36+0.16+0.20 = 0.72 ≥ 0.50 → trade!)
- Riduce la fragilità: un singolo indicatore non può bloccare tutto
- Permette di modulare il rischio in base alla qualità del regime

**File da modificare:**
| File | Modifica |
|------|----------|
| `filters/regime.py` | Aggiungere `apply_regime_scoring()` con pesi configurabili |
| `filters/regime.py` | Modificare `apply_regime_filter()` per usare lo scoring al posto dell'AND |
| `config.yaml` | Aggiungere `regime_filter.soft_scoring` e pesi |
| `risk/sizing.py` | Opzionale: scalare position size con `regime_score` |

---

## 3. Piano di Implementazione Dettagliato

### Step 1: Aggiungere Fast Hurst (`indicators/hurst.py`)

```python
def add_hurst_fast(
    df: pd.DataFrame,
    window: int = 50,
    min_lag: int = 2,
    max_lag: int = 20,  # ridotto per finestra più corta
) -> pd.DataFrame:
    """
    Add fast Hurst exponent for intraday micro-structure analysis.
    
    window=50 (~2 trading days at 15-min) captures short-term
    mean-reverting behavior within broader trends.
    """
    df = df.copy()
    df["hurst_fast"] = (
        df["close"]
        .rolling(window=window, min_periods=window)
        .apply(lambda x: _hurst_single(x.values, min_lag, max_lag), raw=False)
    )
    return df
```

**Nota tecnica:** `_hurst_single` già esiste. Il nuovo wrapper è identico a `add_hurst` ma con default diversi. Si può anche unificare con un parametro `window`.

### Step 2: Aggiornare la pipeline (`indicators/pipeline.py`)

```python
# In build_all_indicators(), dopo add_hurst:
hurst_cfg = cfg.get("hurst", {})
df = add_hurst(df, **{k: v for k, v in hurst_cfg.items() 
                        if k in {"window", "min_lag", "max_lag"}})

# NUOVO: Fast Hurst
hurst_fast_window = hurst_cfg.get("fast_window", 50)
df = add_hurst_fast(df, window=hurst_fast_window)
```

### Step 3: Aggiornare il filtro di regime (`filters/regime.py`)

Opzione più conservativa — cambiare solo la colonna usata:

```python
def apply_regime_filter(
    df: pd.DataFrame,
    adx_threshold: float = 22.0,
    hurst_threshold: float = 0.45,
    atr_relative_std_threshold: float = 2.0,
    atr_window: int = 20,
    use_fast_hurst: bool = True,  # NUOVO
) -> pd.DataFrame:
    # ... existing ATR logic ...
    
    hurst_col = "hurst_fast" if use_fast_hurst and "hurst_fast" in df.columns else "hurst"
    
    df["regime_ok"] = (
        (df["adx"] < adx_threshold)
        & (df[hurst_col] < hurst_threshold)
        & (df["atr_rel_z"] < atr_relative_std_threshold)
    )
    return df
```

### Step 4: Aggiornare la configurazione (`config.yaml`)

```yaml
indicators:
  hurst:
    window: 252        # Slow Hurst (structural regime, ~9 days)
    fast_window: 50    # Fast Hurst (intraday micro, ~2 days) — USED for regime filter
    min_lag: 2
    max_lag: 100

regime_filter:
  adx_threshold: 25
  hurst_threshold: 0.55
  use_fast_hurst: true           # Use fast Hurst for entry gate
  atr_relative_std_threshold: 2.0
  min_regime_coverage_pct: 10
  max_regime_coverage_pct: 70
  # Soft scoring (Fix B — defer to Sprint 2)
  # soft_scoring: false
  # weights: {adx: 0.40, hurst: 0.40, atr: 0.20}
  # score_threshold: 0.50
```

### Step 5: Aggiornare `regime_component_breakdown()` 

Aggiungere il breakdown del fast Hurst per confronto:

```python
def regime_component_breakdown(df, ...):
    # ... existing code ...
    result = {
        "adx_pass_pct": ...,
        "hurst_pass_pct": ...,       # Slow Hurst
        "hurst_fast_pass_pct": ...,  # NUOVO: Fast Hurst
        "atr_rel_z_pass_pct": ...,
        "all_pass_pct": ...,
    }
```

### Step 6: Aggiornare `demo_e2e.py`

Mostrare il breakdown completo nel report:

```python
if "hurst_fast" in df.columns:
    hurst_fast_pass = (df["hurst_fast"] < hurst_threshold).mean() * 100
    print(f"  Hurst fast pass: {hurst_fast_pass:5.1f}% (window=50)")
```

### Step 7: Test e validazione

| Cosa testare | Come |
|-------------|------|
| `tests/test_indicators.py` | Test esistente — aggiungere test per `add_hurst_fast` |
| `tests/test_filters.py` | Test esistente — aggiungere test con `use_fast_hurst=True` |
| `tests/test_pipeline.py` | Verificare che `hurst_fast` appaia nelle colonne |
| Demo run | `python scripts/demo_e2e.py --symbol SPY --n-bars 1500` |
| Confronto pre/post | Confrontare regime_ok%, numero trade, metriche |

---

## 4. Criteri di Successo

| Metrica | Pre-Fix (baseline) | Post-Fix (target) |
|---------|-------------------|-------------------|
| Regime pass rate | 16.0% | 30-50% |
| Hurst pass rate | 20.4% | 45-65% |
| Trade in 3 mesi | 7 | 20-40 |
| Win rate | 42.86% | ≥ 40% (accettabile calo) |
| Profit factor | 0.51 | ≥ 0.80 |
| Max drawdown | -0.73% | < -3% |

**Nota:** Ci si aspetta un calo del win rate (più trade = più falsi positivi), ma il profit factor dovrebbe salire perché si catturano più opportunità vere. Lo stop loss (ATR-based) e il time stop sono la rete di sicurezza.

---

## 5. Rischi e Mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|------------|---------|-------------|
| Più trade ma tutti perdenti | Media | Alto | Monitorare profit factor. Se scende sotto 0.5, tornare indietro |
| Overfitting su Q2 2026 | Alta | Medio | Validare su QQQ e IWM (diversi regimi). Aggiungere walk-forward in Sprint 3 |
| Hurst fast troppo rumoroso | Media | Basso | `min_periods=window` già usato. Se troppo noise, aumentare window a 75 |
| Performance computazionale | Bassa | Basso | `_hurst_single` è O(n²) ma window=50 è 5× più veloce di window=252 |

---

## 6. Timeline

| Sprint | Durata | Contenuto |
|--------|--------|-----------|
| **Sprint 1** (questo) | 1 sessione | Fix A: Fast Hurst + aggiornamento regime filter + test + demo run |
| **Sprint 2** | 1 sessione | Fix B: Soft regime scoring + position size scaling |
| **Sprint 3** | 1 sessione | Walk-forward validation su SPY/QQQ/IWM |

---

## 7. Riferimenti

- Backtest output: conversazione 2026-07-07, `python scripts/demo_e2e.py --symbol SPY --n-bars 1500`
- `documentation.md` — Documentazione tecnica della strategia
- `FIX_PLAN.md` — Fix plan precedenti (TA-Lib reconciliation, etc.)
- `IMPLEMENTATION_PLAN.md` — Piano generale FASE 0-9
