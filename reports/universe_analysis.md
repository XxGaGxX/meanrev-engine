# Analisi Universo — può rendere la Mean Reversion sui large-cap S&P500?

**Data:** 2026-07-11 · **Contesto:** Fase 6 OOS = FAIL (Sharpe OOS negativo).
**Domanda:** il fallimento è dell'universo (80 large-cap S&P500) o della strategia?

## Metodo
3 analisi indipendenti sul daily proxy (stesso engine Fase 5/6), periodo
completo dev+OOS combinato per avere statistica per sottogruppo:
1. **Aggregato** (Fase 6): 80 ticker, Sharpe OOS -5.72 / -9.60 → FAIL
2. **Per settore** (10 gruppi da universe.py)
3. **Per volatilità / gap-size** (7 bucket)

Significance test (bootstrap Sharpe + p-value) su ogni gruppo.

## Risultati

### Per settore
| Settore | n | Sharpe | p | PF | win% |
|---------|---|--------|---|----|------|
| Consumer | 76 | -4.23 | 0.995 | 0.44 | 34.2 |
| Healthcare | 346 | -6.05 | 1.000 | 0.25 | 29.2 |
| Utilities | 45 | -6.29 | 0.990 | 0.34 | 31.1 |
| Telecom | 173 | -6.78 | 1.000 | 0.31 | 30.6 |
| Financials | 296 | -7.11 | 1.000 | 0.22 | 30.4 |
| Energy | 98 | -7.84 | 1.000 | 0.21 | 28.6 |
| Tech | 61 | -8.29 | 1.000 | 0.19 | 29.5 |
| Materials | 20 | -8.45 | 0.995 | 0.10 | 30.0 |
| Industrials | 36 | -10.61 | 1.000 | 0.09 | 13.9 |
| RealEstate | 6 | -21.90 | 1.000 | 0.00 | 0.0 |

### Per volatilità / gap
| Vol bucket | n | Sharpe | p |
|------------|---|--------|---|
| low<0.2 | 44 | -8.91 | 1.000 |
| mid0.2-0.35 | 798 | -6.03 | 1.000 |
| hi0.35-0.5 | 311 | -6.84 | 1.000 |
| Gap 0.3-0.6% | 413 | -5.14 | 1.000 |
| Gap 0.6-1% | 281 | -7.72 | 1.000 |
| Gap 1-2% | 199 | -5.41 | 1.000 |
| Gap 2%+ | 237 | -7.91 | 1.000 |

## Verdetto
**L'universo NON è il problema, e non contiene un sottogruppo redimibile.**
Tutti i 10 settori e tutti i 7 bucket vol/gap hanno Sharpe negativo e
p=1.000. Il "migliore" (Consumer -4.23, gap 0.3-0.6% -5.14) resta negativo
e non significativo. Il BEST COMBO (low vol + small gap) ha solo 16 trade
→ statisticamente inutilizzabile.

### Perché i large-cap non fanno mean-reversion gap-fill
1. **Gap troppo piccoli / efficienti.** S&P500 large-cap hanno gap <2% e
   venono riempiti velocemente dal HFT/arb; il segnale "breakout OR" entra
   DOPO che il fill è già avvenuto → R:R strutturale <1 (Fase 4).
2. **Costi > edge.** Edge giornaliero +0.6-4.8 bp (Fase 2) < slippage ~2-3bp.
3. **La meccanica è sbagliata, non l'universo.** SPY ADX>25 in bull trend
   (Fase 5) conferma: la strategia lotta per definizione in regime trend.

## Implicazioni per il progetto
- Cambiare universo (es. small-cap, ETF, forex, crypto) NON risolve il
  problema di base: **R:R<1 + edge sotto costo** è nella meccanica
  (entry al breakout OR, TP=prev_close), non nel ticker.
- Se si volesse riprovare su un altro universo, servirebbe PRIMA
  risolvere l'R:R (TP esteso a prev_close + N×ATR, non solo prev_close)
  e usare dati 5min reali (non il proxy daily). Vedi Fase 4/5 report.

## Conclusione
L'MVP ha risposto alla domanda onestamente: **la strategia gap-mean-
reversion così definita non rende su nessun sottogruppo dell'universo
large-cap.** Il verdetto Fase 6 (STOP) è rafforzato da questa analisi.
