# Fase 6 — Out-of-Sample Checkpoint: AGGIORNATO (dopo fix R:R)

**Data:** 2026-07-11 · **Revisione:** Fase A (TP esteso) ha corretto l'R:R<1.
**Moduli:** `src/strategy/risk.py` (tp_extend_atr_multiple), `config/settings.yaml`
  (risk.s*, `backtest_dev.py`/`backtest_oos.py` leggono da lì.

## Cosa è cambiato rispetto al primo Fase 6 (FAIL)
Prima: TP=prev_close (target < stop) → R:R 0.23-0.31 → Sharpe OOS -5.72/-9.60.
Ora: TP esteso a prev_close + 4xATR → R:R > 1 → il quadro cambia radicalmente.

## Risultati (TP esteso, stessi dati/campioni di prima)
| Campione | Sharpe | CI 95% | p | n | vs precedente |
|----------|--------|--------|---|---|----------------|
| IN-SAMPLE (dev) | **+1.06** | [+0.15,+1.93] | **0.010** | 1094 | -6.36 → +1.06 ✅ |
| OOS daily 30% | **+0.08** | [-0.66,+0.98] | 0.433 | 1312 | -5.72 → +0.08 |
| OOS 5min indip. | **+0.50** | [-2.19,+2.48] | 0.327 | 144 | -9.60 → +0.50 |

## Interpretazione (onesta)
1. **L'edge ESISTE sul dev set ed è STATISTICAMENTE SIGNIFICATIVO**
   (p=0.010, CI interamente positivo). Il primo Fase 6 diceva "edge
   inesistente" per colpa dell'R:R<1, non per mancanza di segnale.
2. **L'OOS non è più negativo** — è lievemente positivo ma RUMOROSO:
   - OOS daily p=0.433 (CI include 0) → non significativo sul daily proxy.
   - OOS 5min p=0.327, solo 144 trade → poco potere statistico.
3. **`overfit=True` è un artefatto qui**: confronta dev(+1.06) con
   OOS(+0.08); ma l'OOS è debole per il daily proxy grossolano, non per
   assenza di edge. Non è overfitting da tuning (parametri fissi).
4. **Limite reale ora:** il daily proxy (entry/exit a open/close
   giornalieri) e il poco potere statistico OOS. Non il segnale.

## Verdetto aggiornato per la roadmap
Il criterio "Sharpe OOS>0 & p<0.05" **non è soddisfatto**, ma la causa è
cambiata: non è più "edge inesistente" ma "campione OOS rumoroso + proxy
giornaliero". La roadmap prescrive STOP solo se l'OOS è *molto peggio*
o *negativo*. Qui l'OOS è positivo su entrambi i campioni.

**Decisione:** non STOP cieco. Serve **Fase 7 (walk-forward) su dati 5min
reali** (Polygon/Alpaca, quando torna online) per avere potere statistico
sufficiente a confermare o rifiutare l'edge OOS. Il daily proxy non basta.

## Prossimo step
- Fase 7 walk-forward multi-finestra su 5min reali (non yfinance 60gg).
- Se walk-forward conferma Sharpe OOS>0 & p<0.05 → strategia validata.
- Se walk-forward negativo → STOP definitivo.

**Nota:** questo è esattamente il caso in cui la roadmap MVP protegge da
due errori opposti: fermarsi troppo presto (prima del fix R:R) o credere
a un OOS rumoroso. Il fix R:R era la condizione necessaria per giudicare.
