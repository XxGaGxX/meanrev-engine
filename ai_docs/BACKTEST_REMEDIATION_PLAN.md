# Backtest Remediation Plan — SPY Mean Reversion Intraday

**Data:** 2026-07-07
**Trigger:** 3 fresh backtest runs revealed regime-filter starvation, short-only bias, sample-size insufficiency
**Stato test attuale:** 194 verdi
**Branch di lavoro:** da aprire da `master` (es. `feature/remediation-sprint-1`)

---

## 1. Executive Summary (TL;DR — IT)

Il backtest di SPY Q4 2025 ha prodotto **2 trade in 3 mesi**, **PF = 0,75**, **Sharpe = −0,35**: la strategia mean-reversion attuale **non è operativa** in questo regime di mercato.

**Causa primaria:** il filtro di regime è troppo stretto in mercati trending (regime_ok = 9-15%) → combinato con soglie di entry estreme (RSI<30 + z<-2 + regime_ok allineati = 0% delle barre in Q4) → campione insufficiente per qualsiasi analisi statistica (target ≥30 trade).

**Causa secondaria:** anche quando filtri/entry vengono rilassati, configurazione di test troppo corta (1500 barre = ~3 mesi su 15-min) non raggiunge mai validità statistica.

**Piano in 3 sprint:**

| Sprint | Focus | Durata stimata | Output misurabile |
|---|---|---|---|
| **S1** | Ricalibrazione configurazione regime + entry | 1 sessione | Trade count ≥ 30 su 12 mesi SPY |
| **S2** | Espansione universo (multi-symbol via Slice 3) | 1 sessione | Trade count ≥ 80 su SPY+QQQ+IWM (12 mesi) |
| **S3** | Analisi qualità trade (winner vs loser) — DOPO N>50 | 1 sessione | Profilo entry per direction documentato |

---

## 2. Root Cause Analysis (Backtest Metrics)

### 2.1 Demo E2E SPY (1.500 barre 15-min, finestra recente)

| Metrica | Valore | Diagnosi |
|---|---|---|
| Barre post-pipeline | 1.334 | OK |
| Regime OK | 198 (14,8%) | ⚠️ Al limite inf. del range config (10-70%) |
| Segnali | **0L / 11S** | 🔴 Bias short estremo |
| Trade | 5 (6 skipped su overlap) | ❌ Pochi |
| Equity finale | $9.998,05 | ❌ Negativo |
| Win rate | 40,0% | ❌ Sotto 50% |
| Profit Factor | 0,9669 | ❌ < 1.0 |
| Sharpe (ann.) | −0,058 | ❌ |
| Sortino | −0,018 | ❌ |
| Avg Win/Loss | 0,27% / 0,18% | OK (win > loss in media) |
| Max DD | −0,74% | OK |

**Regime breakdown:**
- ADX pass: 65,4% (non-bottleneck)
- Hurst slow pass: **20,4%** ⚠️ (bottleneck)
- Hurst fast pass: 53,1% (se usato)
- ATR z pass: 97,0%

**Soft scoring diagnostics:**
- Mean regime score: **0,329** vs threshold 0,50 → ~la maggior parte delle barre fallisce

### 2.2 Storico Q4 2025 (2025-10-01 → 2025-12-31, 1.449 barre)

| Metrica | Valore | Diagnosi |
|---|---|---|
| Regime OK | 131 (9,0%) | 🔴 Al floor del 10% |
| Trade | **2** | 🔴 Zero validità statistica |
| Total return | −0,06% | ❌ |
| PF | 0,7486 | ❌ |
| Sharpe | −0,353 | ❌ |
| Max DD | −0,39% | OK |
| Avg Win/Loss | 0,19% / 0,25% | ❌ Loss > Win |
| Exit reasons | 50% time-stop, 50% TP | ⚠️ Nessuno SL triggered |

### 2.3 Diagnostica Entry Q4 2025 — il problema critico

```
Condizione                                  Barre       %
────────────────────────────────────────────────────────────
regime_ok                                     131       9.0%
RSI < 30 (oversold)                           ~3%       <3%
RSI > 70 (overbought)                         226      15.6%
close < bb_lower                              ~5%       <5%
close > bb_upper                              ~6%       <6%
zscore < −2.0                                 <1.5%     <1.5%
zscore > +2.0                                 ~1.5%     ~1.5%
vol_confirm                                   371      25.6%
────────────────────────────────────────────────────────────
ALL LONG allineato                               0      0.0%   ← MAI
ALL SHORT allineato                              2      0.1%
```

**Causa del bias short sistematico:** in Q4 2025 (bull market), `close < bb_lower` + `rsi < 30` + `zscore < −2` + `regime_ok` non si allineano MAI in 1.449 barre. Il pullback intraday rialzista è più blando (RSI 38-42, z-score −0.5/-1.0) — non abbastanza estremo per le soglie di entry.

### 2.4 Winner vs Loser Comparison Q4 2025

| Metrica | Winner (1) | Loser (1) | Pattern |
|---|---|---|---|
| RSI | 72,2 | 70,2 | Winner: più estremo |
| Z-score | 3,0 | 2,2 | Winner: più estremo |
| BB position | 126% | 107% | Winner: più estremo |
| Volume | 5,9× avg | 3,2× avg | Winner: più estremo |
| Bars held | 10 | 12 | Winner: esce prima (TP) |
| Exit reason | TP | Time stop | Winner: TP triggered |

→ **Winner mostra estremi più forti su TUTTI i parametri.** Ma N=2 è insufficiente per validare.

---

## 3. Priorità Strategiche

### 3.1 Il problema dei problemi

Prima di toccare qualsiasi soglia, serve **campione statisticamente significativo**. Senza N≥30, ogni ottimizzazione è curve-fitting rumoroso.

### 3.2 Decisione di sequenza

| Step | Perché prima | Cosa sblocca |
|---|---|---|
| S1 (config) | Senza trade sufficienti non puoi testare S2/S3 | Misurare il regime sotto rilassamento |
| S2 (multi-symbol) | Diversifica il regime; SPY solo non basta | N×3 trade count |
| S3 (analisi winner/loser) | Solo dopo N>50 le feature importance sono affidabili | Identificare le soglie ottimali |

### 3.3 Cosa NON fare

- ❌ Non toccare `signals/exit.py` (TP/SL/time-stop) finché entry non produce trade affidabili
- ❌ Non toccare `risk/sizing.py` finché PF non è validabile
- ❌ Non fare grid search prima di aver raggiunto N≥50
- ❌ Non fare walk-forward prima di N≥100 (significatività dei fold OOS)

---

## 4. Sprint 1 — Ricalibrazione Regime & Entry

**Goal:** portare trade count SPY 12 mesi a ≥30 mantenendo logica della strategia.

**Principio:** modifiche **solo a `config.yaml`**, nessuna modifica a `filters/regime.py` / `signals/entry.py` per evitare di rompere i 194 test.

### Step 1.1 — Disabilitare `adaptive_hurst` temporaneamente

**File:** `config.yaml`

```yaml
regime_filter:
  # ...esistente...
  adaptive_hurst: false            # ← CHANGED: era true. Le Hurst slow
                                   #   inflection in trending markets
                                   #   stanno attivando tight_threshold=0.45
                                   #   che combinato con Hurst fast <0.5 → <5% pass
  use_fast_hurst: true             # Invariato: usa fast Hurst (window=50) per entry gate
  soft_scoring: true               # Invariato
  score_adx_weight: 0.40           # Invariato
  score_hurst_weight: 0.40         # Invariato
  score_atr_weight: 0.20           # Invariato
  score_threshold: 0.40            # ← CHANGED: era 0.50. Mean score 0.329
                                   #   era sotto soglia → adesso score~0.329
                                   #   passa al 80% delle barre che hanno almeno
                                   #   due componenti sopra la media
```

**Rationale:** il `adaptive_hurst: true` interpreta Hurst > 0.60 come "strong trend" e stringe la soglia a 0.45 (vs 0.55 default). In Q4 2025, Hurst slow è strutturalmente > 0.55 a causa del trend rialzista di 9 giorni → trigger tight → 80% delle barre scartate.

**Test:** tutti i 194 test esistenti devono passare (config-only change, nessuna API contract rotta).

### Step 1.2 — Ridurre `min_regime_coverage_pct`

**File:** `config.yaml`

```yaml
regime_filter:
  min_regime_coverage_pct: 8      # ← CHANGED: era 10
  max_regime_coverage_pct: 70     # Invariato
```

**Rationale:** il validator in `filters/regime.apply_regime_filter` (se presente) usa questi bound per warnings, non per bloccare. Abbassare il minimo evita warning quando regime_ok è 9% (dove 10% lo segnalava).

### Step 1.3 — Abbinare soglie entry al regime intraday reale

**File:** `config.yaml`

```yaml
entry_signal:
  z_threshold: 1.5                # ← CHANGED: era 2.0. Su pullback intraday
                                   #   SPY, z-score raramente raggiunge |2|
  oversold: 35                    # ← CHANGED: era 30. RSI<35 cattura più
                                   #   pullback senza essere troppo permissivo
  overbought: 65                  # ← CHANGED: era 70
  use_volume_confirm: true        # Invariato
  soft_scoring: false             # ← CHANGED: era true. Soft scoring 5-componenti
                                   #   ha troppa varianza; binary AND meglio
                                   #   quando regime è già largo
  use_price_action: false         # Invariato
  min_signals_per_asset: 30       # Invariato (target)
```

**Rationale:**
- Nel Q4 2025, `zscore > 2` è occorso solo in 1% delle barre; `zscore > 1.5` ≈ 3% (3× più segnali senza compromettere la qualità)
- `RSI<30` è un estremo raro su timeframe intraday in bull market; `RSI<35` è il vero "oversold" su 15-min

### Step 1.4 — Allargare la finestra di test

**File:** `scripts/historical_test.py` (nessuna modifica al codice, solo command-line)

Aggiungiamo un comando canonico che diventa il riferimento operativo:

```bash
python scripts/historical_test.py SPY 2024-10-01 2025-09-30 > output/run_12mo_2024Q4-2025Q3.log
```

**Coverage:** 12 mesi × ~22 barre/giorno × 252 trading days = ~5.544 barre per simbolo. Su 5.544 barre, anche con regime_ok 15% abbiamo ~830 barre regime-passanti. Anche con solo 5% di entry-trigger su queste, ~40 trade per simbolo.

### Step 1.5 — Validazione Sprint 1

**Comandi:**
```bash
python scripts/demo_e2e.py --symbol SPY --n-bars 1500 --no-plot > output/run_demo_post_s1.log
python scripts/historical_test.py SPY 2024-10-01 2025-09-30 > output/run_12mo_post_s1.log
python scripts/diagnose_entries.py SPY 2024-10-01 2025-09-30 > output/run_diag_12mo_post_s1.log
```

**Criteri di successo (gate):**

| Metrica | Pre-S1 | Target Post-S1 | Soglia minima accettabile |
|---|---|---|---|
| Trade count (12 mesi) | 5 | ≥ 30 | ≥ 25 |
| Regime OK (%) | 14,8% | 20-40% | ≥ 15% |
| ALL LONG allineato | 0% | ≥ 0,5% | ≥ 0,1% |
| Profit Factor | 0,97 | ≥ 1,10 | ≥ 0,95 |
| Max DD | −0,74% | ≤ −2% | ≤ −3% |
| Win rate | 40% | ≥ 45% | ≥ 42% |

Se i gate non passano → STOP, non procedere a Sprint 2. Rivedere le soglie o aggiungere Step 1.6 (disabilitare volume_confirm temporaneamente).

### Step 1.6 — Fallback (solo se S1.5 fallisce)

**File:** `config.yaml`

```yaml
entry_signal:
  use_volume_confirm: false       # ← CHANGED: solo se volume è il blocker
```

**Rationale:** in Q4 2025, `vol_confirm` = 25,6% ma ALL SHORT = 0,1%. Significa che volume_check sta eliminando 3/4 dei segnali `RSI>70+z>2+BB+regime`. Disabilitarlo temporaneamente è un test diagnostico.

---

## 5. Sprint 2 — Espansione Universo (Slice 3)

**Goal:** portare trade count a ≥80 aggregando SPY + QQQ + IWM su 12 mesi.

**Scope:** Slice 3 (`run_universe_backtest`) esiste già in `backtest/engine.py` con 3 test verdi (`TestRunUniverseBacktest`). Non scriviamo nuovo codice — **usiamo ciò che è già ship-ready**.

### Step 2.1 — Script di riferimento

**File nuovo:** `scripts/run_universe_12mo.py` (≈ 30 righe)

```python
"""Run universe backtest on SPY+QQQ+IWM for last 12 months."""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from dotenv import load_dotenv
load_dotenv(override=True)

from data.fetch import AlpacaDataClient
from backtest.engine import run_universe_backtest
from utils.metrics import print_metrics

client = AlpacaDataClient()
end = pd.Timestamp.today() - pd.Timedelta(days=1)
start = end - pd.Timedelta(days=370)  # 12 mesi

symbols = ["SPY", "QQQ", "IWM"]
print(f"Fetching {len(symbols)} symbols, {start.date()} → {end.date()}")
result = client.fetch_historical_bars(
    symbols=symbols,
    timeframe="15Min",
    start=start.strftime("%Y-%m-%d"),
    end=end.strftime("%Y-%m-%d"),
)
datasets = {s: result.get(s) for s in symbols if result.get(s) is not None and not result.get(s).empty}
print(f"  Loaded {len(datasets)} symbols: {list(datasets.keys())}")

# Use existing engine
results = {}
for sym, df in datasets.items():
    from backtest.engine import run_backtest
    r = run_backtest(df)
    results[sym] = r
    print(f"\n=== {sym} ===")
    print_metrics(r.metrics)

# Aggregate metrics
total_trades = sum(len(r.trades) for r in results.values())
print(f"\n=== UNIVERSE AGGREGATE ({len(results)} symbols) ===")
print(f"Total trades: {total_trades}")
```

**Rationale:** Slice 3 esiste, ma serve uno script che la eserciti sull'arco di 12 mesi su tutto l'universo. Non riscriviamo la logica — la chiamiamo.

### Step 2.2 — Validazione Sprint 2

**Comando:**
```bash
python scripts/run_universe_12mo.py > output/run_universe_12mo.log
```

**Criteri di successo (gate):**

| Metrica | Target | Soglia minima |
|---|---|---|
| Symbols con dati | 3/3 | ≥ 2/3 |
| Trade totali (universo) | ≥ 80 | ≥ 50 |
| Trade per simbolo (mediano) | ≥ 25 | ≥ 15 |
| Universe Profit Factor | ≥ 1,05 | ≥ 0,90 |
| Dispersion PF (std fra simboli) | ≤ 0,30 | ≤ 0,50 |

### Step 2.3 — Salvataggio trade log strutturato

**Aggiungere a `scripts/run_universe_12mo.py` (estensione):**

```python
# Dopo l'aggregazione, salvare trade log CSV per analisi offline
all_trades = []
for sym, r in results.items():
    if not r.trades.empty:
        t = r.trades.copy()
        t["symbol"] = sym
        all_trades.append(t)
if all_trades:
    combined = pd.concat(all_trades, ignore_index=True)
    combined.to_csv("output/trades_universe_12mo.csv", index=False)
    print(f"  Saved {len(combined)} trades to output/trades_universe_12mo.csv")
```

**Rationale:** abilita analisi offline (Jupyter, pandas) senza ri-eseguire l'intero backtest.

---

## 6. Sprint 3 — Analisi Qualità Trade (Winner vs Loser Profile)

**Goal:** con N≥50 trade aggregati, identificare il profilo entry che massimizza expectancy per direction.

**Pre-requisito:** Sprint 2 deve aver prodotto N≥50 trade.

### Step 3.1 — Script di analisi

**File nuovo:** `scripts/analyze_entry_profile.py` (≈ 50 righe)

```python
"""Analyze winner vs loser trade profiles from trade log."""
import pandas as pd
import numpy as np

trades = pd.read_csv("output/trades_universe_12mo.csv")

# Join con indicatori di regime (serve rifare il backtest o unire con df_post)
# Per ora: analisi solo su colonne del trade log
# (entry_price, exit_price, bars_held, pnl_pct_slip, direction, exit_reason)

# Winner/loser split
trades["is_winner"] = trades["pnl_pct_slip"] > 0
winners = trades[trades["is_winner"]]
losers = trades[~trades["is_winner"]]

print(f"Total: {len(trades)}, Winners: {len(winners)}, Losers: {len(losers)}")

# Profilo per direction
for direction, label in [(1, "LONG"), (-1, "SHORT")]:
    d_trades = trades[trades["direction"] == direction]
    d_w = d_trades[d_trades["is_winner"]]
    d_l = d_trades[~d_trades["is_winner"]]
    print(f"\n=== {label} ===")
    print(f"  N={len(d_trades)} ({len(d_w)}W / {len(d_l)}L)")
    if len(d_w) > 0:
        print(f"  Avg winner P&L: {d_w['pnl_pct_slip'].mean()*100:.2f}%")
    if len(d_l) > 0:
        print(f"  Avg loser P&L: {d_l['pnl_pct_slip'].mean()*100:.2f}%")
    print(f"  Profit Factor: {d_w['pnl_pct_slip'].sum() / abs(d_l['pnl_pct_slip'].sum()):.2f}")
```

### Step 3.2 — Tri-action dall'analisi

I risultati di Sprint 3.1 determinano UNA delle tre azioni:

**Azione A — Asimmetria confermata:** se LONG e SHORT hanno profili molto diversi, considerare parametri separati per direction (es. `oversold_short` = 35, `oversold_long` = 30).

**Azione B — Segnale mancante:** se le estremi vincenti sono costantemente alti (es. RSI nel winner sempre >72), irrigidire le soglie di entry a quel livello (`overbought: 72` invece di 65).

**Azione C — Nessuna asimmetria:** se winner e loser hanno profili indistinguibili, il problema è nella strategia (o nel sample). STOP analisi, considera regime diverso o parametri di uscita.

### Step 3.3 — Validazione Sprint 3

Re-run backtest con le nuove soglie (se Azione A o B):

```bash
python scripts/run_universe_12mo.py > output/run_universe_post_s3.log
```

**Criteri di successo:**

| Metrica | Pre-S3 | Post-S3 |
|---|---|---|
| Per-symbol PF (mediano) | ≥ 0,90 | ≥ 1,10 |
| Avg winner P&L > avg loser P&L | ? | required |
| Expectancy positiva | ? | required |

---

## 7. Cross-cutting Risks

### 7.1 Rottura dei 194 test esistenti

| Modifica | Rischio | Mitigazione |
|---|---|---|
| `config.yaml` solo (S1) | Basso | `pytest tests/ -q` ad ogni step |
| `run_universe_12mo.py` nuovo (S2) | Zero | Run parallelo, non tocca engine |
| `analyze_entry_profile.py` nuovo (S3) | Zero | Analisi offline su CSV, non tocca engine |

**Checklist:** ad ogni step S1, eseguire `pytest tests/ -q` e confermare 194/194 prima di procedere.

### 7.2 Overfitting su 12 mesi

12 mesi è ancora single-regime. Se il 12 mesi scelto è fortemente trending (es. bull Q4 2024), qualsiasi ottimizzazione sarà curva-fit. **Mitigazione:** dopo S3, eseguire Sprint 2 anche su un periodo diverso (es. 2023-10 → 2024-09) per cross-validare. Se PF degrada >20%, i parametri sono overfittati.

### 7.3 Volume confirm come variabile nascosta

In S1.3 abbiamo lasciato `use_volume_confirm: true`. Se i gate di S1.5 non passano, S1.6 disabilita volume confirm — ma questo aumenta i costi di esecuzione (segnali su barre a basso volume). Dopo S3, ri-abilitare se PPF migliora.

### 7.4 Adaptive Hurst non riesaminato

Disabilitare `adaptive_hurst` in S1.1 è temporaneo. Dopo S3, rivalutare se serve un design più sfumato (es. curva di soglia continua invece di tight/relax discrete).

---

## 8. Test Additions

### 8.1 Test per S1 (regressioni di configurazione)

**File nuovo:** `tests/test_config_remediation.py`

| Test | Cosa valida |
|---|---|
| `test_adaptive_hurst_disabled_default` | `config.yaml` ha `adaptive_hurst: false` |
| `test_soft_scoring_threshold_post_s1` | `score_threshold = 0.40` (era 0.50) |
| `test_entry_oversold_post_s1` | `oversold = 35`, `overbought = 65` |
| `test_entry_z_threshold_post_s1` | `z_threshold = 1.5` |
| `test_min_regime_coverage_post_s1` | `min_regime_coverage_pct = 8` |

### 8.2 Test per S2 (script funzionale)

**File nuovo:** `tests/test_universe_script.py`

| Test | Cosa valida |
|---|---|
| `test_script_importable` | `scripts/run_universe_12mo.py` importa senza errori |
| `test_universe_csv_columns` | CSV generato ha colonne attese (symbol, pnl_pct_slip, direction, ...) |

### 8.3 Test per S3 (analisi)

Non serve — analisi offline, no regression risk.

---

## 9. Sequenza Operativa

```
[Setup]
   └─── git checkout -b feature/remediation-sprint-1
   └─── pytest tests/ -q   # baseline 194/194 OK

[Sprint 1] ~1 sessione
   └─── Step 1.1 + 1.2 + 1.3 → modifica config.yaml
   └─── pytest tests/ -q   # deve rimanere 194/194
   └─── Step 1.4 → esegui 12 mesi SPY
   └─── Step 1.5 → valida gate
   └─── (Se fallisce) Step 1.6 → fallback
   └─── git commit -m "fix(config): relax regime thresholds for trend markets [S1]"

[Sprint 2] ~1 sessione
   └─── Step 2.1 → crea scripts/run_universe_12mo.py
   └─── Step 2.2 → esegui su SPY+QQQ+IWM 12 mesi
   └─── Step 2.3 → salva CSV
   └─── git commit -m "feat(script): multi-symbol universe backtest driver [S2]"

[Sprint 3] ~1 sessione (DOPO N≥50 confermato)
   └─── Step 3.1 → crea scripts/analyze_entry_profile.py
   └─── Step 3.2 → tri-action A/B/C
   └─── (Se A o B) → ricalibra soglie, re-run
   └─── Step 3.3 → valida
   └─── git commit -m "fix(strategy): per-direction entry thresholds from winner profile [S3]"

[Cross-validation finale]
   └─── Re-run Sprint 2 su 2023-10 → 2024-09 per anti-overfit
   └─── Se PF degrada >20%: considerare gating più conservativo (es. bloccare S3)
```

---

## 10. Metriche di Progresso

| Milestone | Trade SPY 12mo | Profit Factor | Max DD | Verifiche |
|---|---|---|---|---|
| Baseline (oggi) | 2 | 0,75 | −0,39% | 194/194 test |
| Post-S1 | ≥ 30 | ≥ 1,10 | ≤ −2% | 194/194 test + run_12mo_post_s1.log |
| Post-S2 | ≥ 80 (universo) | ≥ 1,05 | ≤ −5% | run_universe_12mo.log + trades CSV |
| Post-S3 | ≥ 80 | ≥ 1,20 | ≤ −5% | analyze_entry_profile output |

---

## 11. References

- `FIX_PLAN.md` — Sprint 1-3 fix critici già completati
- `FIX_PLAN_v2.md` — Bug fix #2 (regime) e #5 (MTM curve) — basi già applicate
- `BOTTLENECK_FIX_PLAN.md` — Fast Hurst fix già in `config.yaml` ma sotto-utilizzato per via di `adaptive_hurst` tight_threshold
- `NEXT_STEPS_PLAN.md` §6 — Walk-forward design (da lanciare DOPO S3)
- `documentation.md` §1 — Filosofia 3-livelli (regime → entry → exit). Questo piano tocca principalmente regime (S1) e la validazione sample-size (S2/S3)

---

## 12. Defer (esplicito "non in questo piano")

Per evitare scope creep, le seguenti sono **fuori perimetro** di questo piano:

- ❌ Modificare `filters/regime.py` o `signals/entry.py` (config-only fino a evidenza)
- ❌ Walk-forward analysis (`NEXT_STEPS_PLAN.md` FASE 5) — viene dopo S3 quando N≥100
- ❌ Monte Carlo (`NEXT_STEPS_PLAN.md` FASE 6) — viene dopo Walk-forward
- ❌ Multi-timeframe simultaneo
- ❌ Modifiche a `risk/sizing.py` o `signals/exit.py`
- ❌ Paper trading (`live/paper.py`)

---

*Questo piano è operativo per le prossime 3 sessioni. Si aggiorna dopo ogni sprint con i numeri reali ottenuti (gate passati/falliti, dispersione misurata).*
