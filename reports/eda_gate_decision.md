# Phase 2 — EDA Gap Expectancy — [GATE: PASS]

- Strategy: `gap_mean_reversion_mvp`
- Universe size (declared): 80
- Operating range: |gap| ∈ [0.30%, 2.00%]
- Dev window: 2019-01-01 .. 2022-12-31
- Cache loaded: 80 tickers (skipped: 0: none)
- Total dev bars in scope: 80560
- Gate threshold (N trades per bucket): 30

## Decision

**PROCEED.** At least one bucket has N ≥ 30 and positive mean return: [-2.0%, -1.0%) (n=6142, mean=+0.0207%), [-1.0%, -0.6%) (n=6287, mean=+0.0064%), [-0.6%, -0.3%] (n=8125, mean=+0.0433%), [0.3%, 0.6%) (n=10670, mean=+0.0282%).

## Per-bucket expectancy (size)

### Size buckets — DOWN (long candidates) and UP (short candidates)

| Bucket | Direction | N | Mean Return | Std | Freq | Approx Sharpe |
|---|---|---:|---:|---:|---:|---:|
| [-2.0%, -1.0%) | DOWN | 6142 | +0.0207% | 1.9294% | 7.6241% | 0.05 |
| [-1.0%, -0.6%) | DOWN | 6287 | +0.0064% | 1.6334% | 7.8041% | 0.02 |
| [-0.6%, -0.3%] | DOWN | 8125 | +0.0433% | 1.4625% | 10.0857% | 0.15 |
| [0.3%, 0.6%) | UP | 10670 | +0.0282% | 1.4117% | 13.2448% | 0.12 |
| [0.6%, 1.0%) | UP | 7956 | -0.0098% | 1.6264% | 9.8759% | -0.03 |
| [1.0%, 2.0%) | UP | 7047 | -0.1001% | 1.9496% | 8.7475% | -0.24 |

## Sector-conditioning

### Sector x Size

| Sector | N | Bucket | Direction | Mean Return |
|---|---:|---|---|---:|
| Consumer | 1504 | [0.3%, 0.6%) | UP | +0.0573% |
| Consumer | 1097 | [-0.6%, -0.3%] | DOWN | +0.0768% |
| Consumer | 850 | [0.6%, 1.0%) | UP | +0.0429% |
| Consumer | 668 | [-1.0%, -0.6%) | DOWN | +0.0318% |
| Consumer | 536 | [1.0%, 2.0%) | UP | -0.0627% |
| Consumer | 495 | [-2.0%, -1.0%) | DOWN | +0.2180% |
| Energy | 750 | [1.0%, 2.0%) | UP | -0.1291% |
| Energy | 541 | [-2.0%, -1.0%) | DOWN | +0.0139% |
| Energy | 524 | [0.6%, 1.0%) | UP | -0.0659% |
| Energy | 474 | [0.3%, 0.6%) | UP | +0.0094% |
| Energy | 451 | [-1.0%, -0.6%) | DOWN | +0.0139% |
| Energy | 419 | [-0.6%, -0.3%] | DOWN | -0.1684% |
| Financials | 1852 | [0.3%, 0.6%) | UP | +0.0252% |
| Financials | 1606 | [0.6%, 1.0%) | UP | +0.1155% |
| Financials | 1605 | [1.0%, 2.0%) | UP | -0.1135% |
| Financials | 1539 | [-0.6%, -0.3%] | DOWN | +0.0355% |
| Financials | 1403 | [-1.0%, -0.6%) | DOWN | -0.0513% |
| Financials | 1393 | [-2.0%, -1.0%) | DOWN | +0.0615% |
| Healthcare | 2300 | [0.3%, 0.6%) | UP | +0.0587% |
| Healthcare | 1657 | [-0.6%, -0.3%] | DOWN | +0.0813% |
| Healthcare | 1459 | [0.6%, 1.0%) | UP | -0.0375% |
| Healthcare | 1158 | [-1.0%, -0.6%) | DOWN | +0.0100% |
| Healthcare | 809 | [1.0%, 2.0%) | UP | -0.1013% |
| Healthcare | 770 | [-2.0%, -1.0%) | DOWN | +0.1126% |
| Industrials | 646 | [0.3%, 0.6%) | UP | -0.0103% |
| Industrials | 558 | [0.6%, 1.0%) | UP | -0.1666% |
| Industrials | 503 | [1.0%, 2.0%) | UP | -0.1571% |
| Industrials | 489 | [-0.6%, -0.3%] | DOWN | +0.0438% |
| Industrials | 441 | [-1.0%, -0.6%) | DOWN | +0.1120% |
| Industrials | 419 | [-2.0%, -1.0%) | DOWN | -0.0309% |
| Materials | 349 | [0.3%, 0.6%) | UP | +0.0123% |
| Materials | 347 | [1.0%, 2.0%) | UP | -0.0690% |
| Materials | 321 | [0.6%, 1.0%) | UP | -0.1479% |
| Materials | 295 | [-2.0%, -1.0%) | DOWN | +0.0009% |
| Materials | 284 | [-0.6%, -0.3%] | DOWN | +0.1405% |
| Materials | 229 | [-1.0%, -0.6%) | DOWN | -0.1662% |
| RealEstate | 332 | [0.3%, 0.6%) | UP | -0.0541% |
| RealEstate | 192 | [-0.6%, -0.3%] | DOWN | +0.1330% |
| RealEstate | 174 | [0.6%, 1.0%) | UP | -0.0589% |
| RealEstate | 146 | [-1.0%, -0.6%) | DOWN | -0.2314% |
| RealEstate | 104 | [1.0%, 2.0%) | UP | +0.1391% |
| RealEstate | 101 | [-2.0%, -1.0%) | DOWN | -0.2171% |
| Tech | 2521 | [0.3%, 0.6%) | UP | +0.0340% |
| Tech | 2195 | [1.0%, 2.0%) | UP | -0.0962% |
| Tech | 2164 | [0.6%, 1.0%) | UP | -0.0291% |
| Tech | 1952 | [-2.0%, -1.0%) | DOWN | -0.0514% |
| Tech | 1898 | [-0.6%, -0.3%] | DOWN | +0.0320% |
| Tech | 1476 | [-1.0%, -0.6%) | DOWN | +0.0653% |
| Telecom | 269 | [0.3%, 0.6%) | UP | -0.0005% |
| Telecom | 225 | [-0.6%, -0.3%] | DOWN | +0.0756% |
| Telecom | 129 | [-1.0%, -0.6%) | DOWN | +0.0580% |
| Telecom | 129 | [0.6%, 1.0%) | UP | -0.0163% |
| Telecom | 76 | [-2.0%, -1.0%) | DOWN | -0.2062% |
| Telecom | 75 | [1.0%, 2.0%) | UP | -0.1645% |
| Utilities | 423 | [0.3%, 0.6%) | UP | -0.0869% |
| Utilities | 325 | [-0.6%, -0.3%] | DOWN | -0.0479% |
| Utilities | 186 | [-1.0%, -0.6%) | DOWN | -0.0451% |
| Utilities | 171 | [0.6%, 1.0%) | UP | +0.0290% |
| Utilities | 123 | [1.0%, 2.0%) | UP | +0.0095% |
| Utilities | 100 | [-2.0%, -1.0%) | DOWN | -0.1000% |

## Notes

- Cells with N<20 are labelled *Insufficient Data* and excluded from the decision.
- Gate threshold of **30** comes from `config/settings.yaml` -> `gates.eda_min_trades_per_cell`.
- `Mean Return` is signed in the direction of fill (DOWN→long, UP→short). Positive = reversion happened.
- This script runs on the development set ONLY. The 30% OOS window is locked until Fase 6.

## COST-SENSITIVITY CAVEAT (read before proceeding to Fase 3)

- Best-bucket mean return ≈ **+4.33 bp/trade** (best of `['[-2.0%, -1.0%)', '[-1.0%, -0.6%)', '[-0.6%, -0.3%]', '[0.3%, 0.6%)', '[0.6%, 1.0%)', '[1.0%, 2.0%)']`).
- If realistic round-trip cost is ~10 bps (5bps commission + 5bps slippage), `mean/cost` ratio = **0.43×** → verdict: **FRAGILE — mean return does not exceed estimated costs**.
- Phase 3 should NOT be built without a cost-aware per-trade threshold (`settings.gates.backtest_oos_min_mean_return_bps_above_cost` or similar). Reading the chart above as 'edge exists' without weighting costs will produce a strategy that loses money live.
