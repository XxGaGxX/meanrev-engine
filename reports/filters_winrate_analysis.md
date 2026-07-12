# Fase A.2 — Tentativi di filtro per alzare la winrate (verdetto onesto)

**Data:** 2026-07-12 · **Contesto:** dopo Fase A (TP esteso → dev Sharpe +1.06),
l'OOS è rumoroso. Obiettivo: alzare la winrate con filtri a basso rischio
di overfit (200EMA + gap-band stretta + VIX/ADX).

## Cosa è stato implementato (TDD, no hardcode)
- `filters.ema_filter_allows()` (gap vs 200EMA) + 3 test.
- `config.FiltersConfig` + sezione `filters:` in settings.yaml.
- `backtest_dev.py` cabla gap-band + ADX + EMA filter da settings.

## Risultati (DEV set, daily proxy, TP esteso attivo)

| Config | n | win% | PF | Sharpe | DD |
|--------|---|------|----|--------|-----|
| BASE (gap 0.3-2%, no EMA) | 1094 | 50.3 | 1.25 | **+1.06** | 4.3 |
| + EMA200 (daily) | 30 | 53.3 | 1.18 | +0.75 | 1.5 |
| + gap stretta 0.3-0.8% | 121 | 45.5 | 0.79 | **-1.13** | 5.3 |

## Verdetto
1. **EMA200 sui DAILY è inadatto**: in un mercato rialzista 2019-2024 i
   large-cap stanno quasi sempre sopra la EMA200 → taglia il 97% dei trade
   (30 da 1094). Nessun potere statistico. La 200EMA ha senso su 5min,
   non su daily per questo universo.
2. **Gap-band stretta peggiora**: i gap PICCOLI (0.3-0.8%) revertiono
   PEGGIO dei gap medi (0.8-2%) nel nostro proxy. Ipotesi "small gap =
   better mean-reversion" **falsa sui dati**.
3. **La winrate NON è il collo di bottiglia**: con R:R 2:1 servirebbe solo
   ~33% di winrate per essere profittevoli, e siamo a 50%. Il limite reale
   è la **validazione OOS**, non la winrate dev.

## Conclusione per il workflow
Non esiste un filtro banale che alzi la winrate senza distruggere il
campione o peggiorare l'economia. La strategia con TP esteso funziona sul
dev *perché usa tutti i gap* (1094 trade). La strada onesta è la **Fase 7
walk-forward su 5min REALI** (Alpaca/Polygon), dove il TP esteso è
rispettato intraday e l'OOS acquista potere statistico. Il daily proxy è
il vero limite, non la winrate.

**Raccomandazione:** non restringere oltre il dev. Usare le API Alpaca
(già in `.env.example`, git-ignored) per scaricare 5min 2019-2024 e fare
Fase 7 walk-forward. Solo lì si potrà confermare o rifiutare l'edge.
