# Fase 6 — Out-of-Sample Checkpoint: RISULTATO

**Data:** 2026-07-11 · **Workflow:** TDD + ad-hoc verify + gate OOS
**Moduli:** `src/backtest/oos.py`, `scripts/backtest_oos.py`
**OOS lock:** `assert_oos_locked("Fase 6", split)` superato (split 2023-01-01 → 2024-12-31)

## Gate Fase 6 (ROADMAP_MVP.md criterio 1)
- [ ] Sharpe out-of-sample > 0 e profit factor > 1, al netto di costi
- [ ] OOS non molto peggio dell'in-sample (no overfitting)

**RISULTATO: FAIL.**

## Dati (tre campioni indipendenti)
| Campione | Sharpe | CI 95% | p-value | n |
|----------|--------|--------|---------|-----|
| IN-SAMPLE (dev 70%) | -6.36 | [-7.22,-5.53] | 1.000 | 1094 |
| OOS daily 30% | -5.72 | [-6.45,-5.15] | 1.000 | 1312 |
| OOS 5min indip. (yfinance) | -9.60 | [-13.12,-6.99] | 1.000 | 144 |

## Interpretazione
1. **L'edge non esiste OOS.** Sharpe OOS negativo su ENTrambi i campioni
   indipendenti (daily cached 30% + 5min yfinance). p=1.000 → probabilità
   che l'edge sia reale è nulla.
2. **Coerenza, non artefatto.** Dev, OOS daily e OOS 5min convergono tutti
   su Sharpe negativo e simile. Se fosse un bug nel backtest, i tre
   campioni divergerebbero. La convergenza conferma che è la *strategia*.
3. **`overfit=True` ma la causa è "edge inesistente", non tuning.** Non
   abbiamo ottimizzato nulla sull'OOS (parametri fissi da settings.yaml).
   Il flag scatta perché OOS è più negativo dell'in-sample; entrambi negativi.
4. **Causa radice (già diagnosticata Fase 4):** R:R strutturale < 1
   (effective_rr 0.23→0.31) + edge giornaliero (+0.6-4.8 bp) SOTTO i costi
   di slippage reali (~2-3 bp). La strategia perde per pura aritmetica,
   non per regime (il regime filter era già applicato).

## Verdetto per la roadmap
**STOP.** Il criterio di successo MVP punto 1 (Sharpe OOS>0 & PF>1) NON è
soddisfatto. La roadmap stessa prescrive: "se il risultato OOS è negativo →
STOP, non si va avanti forzando i parametri sull'OOS."

L'infrastruttura di validazione (Fasi 0-6: TDD, OOS-lock, engine onesto,
significance test, report) è SOLIDA e riusabile. Il problema è la strategia,
non il processo.

## Opzioni (fuori MVP, solo se l'utente vuole continuare)
- A. **Rivedere i filtri / alzare R:R** (TP esteso a prev_close + N×ATR,
   regime filter più stretto) e RIPETERE Fase 5-6 da capo. Rischio: il
   problema è strutturale (R:R<1), non di filtro — potrebbe non bastare.
- B. **Cambiare strategia** (es. mean-reversion su timeframe diverso, o
   momentum) — fuori scope MVP.
- C. **Accettare il verdetto** e archiviare il progetto come "validazione
   onesta di un edge inesistente" — il valore è nel processo, non nel P&L.

**Raccomandazione:** C (rispetta la roadmap) o A solo se l'utente vuole
investigare il R:R prima di chiudere. Non forzare i parametri sull'OOS.
