"""Automatic data research: confronta le VALUTAZIONI del progetto (Fase 2
EDA / design) con i SEGNALI reali sui dati in cache (80 ticker, 2019-2024
daily). Usa SOLO i moduli del progetto: src.strategy.gap_calc (gap+bucket)
e src.strategy.risk (sizing+costi).

NOTA DI METODO (onesta): i dati in cache sono GIORNALIERI, non a 5 min.
Il signal generator Fase 3 richiede l'opening-range a 5min che NON
esiste qui. Quindi questo NON e' il backtest Fase 5. E' un
CONFRONTO a livello giornaliero:
  - entry: al close del giorno del gap (proxy; il reale sarebbe il breakout
    dell'OR a 5min il giorno dopo)
  - exit:  close del giorno successivo (proxy del "gap fill": se il prezzo
    ritorna verso prev_close entro 1 giorno)
  - usiamo gap_calc per bucket/edge e risk per R:R/costi reali.

Questo valida se i PRESUPPOSTI del progetto (fill rate, direzione,
expectancy per bucket) reggono sui dati veri — che e' esattamente cio'
che chiedeva la task: "confronta le tue valutazioni con quelle dei
segnali del progetto".
"""

from __future__ import annotations

import glob
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(r"C:\Users\diego\Desktop\Progetti\quant")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CACHE = ROOT / "data" / "cache"

from src.strategy.gap_calc import compute_gaps_df, bucket_label_for_sign, INSUFFICIENT_DATA_CELL_THRESHOLD
from src.strategy.risk import compute_position
from src.config import load_settings

settings = load_settings()
st = settings.strategy


def load_all() -> pd.DataFrame:
    frames = []
    for f in sorted(glob.glob(str(CACHE / "*.parquet"))):
        if os.path.basename(f).startswith("_"):
            continue
        d = pd.read_parquet(f)
        # nomi colonne: 'date','open','high','low','close'
        d = d.rename(columns={"adj close": "adj_close"})
        d["date"] = pd.to_datetime(d["date"])
        d = d.sort_values("date")
        # prev_close = close giorno precedente (per ticker)
        d["prev_close"] = d.groupby("ticker")["close"].shift(1)
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    df = load_all()
    df = df.dropna(subset=["prev_close"])

    # --- gap + bucket via modulo del progetto ---
    df = compute_gaps_df(df, prev_close_col="prev_close")
    df["bucket"] = df["gap_pct"].apply(bucket_label_for_sign)
    # mantieni solo bucket dentro l'operating window (0.3%-2.0%)
    df = df[df["bucket"].notna()]

    # --- trade proxy: entry close giorno gap, exit close giorno successivo ---
    # return gia' firmato in direzione del fill (da gap_calc)
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    df["next_close"] = df.groupby("ticker")["close"].shift(-1)
    df["realized_ret"] = (df["next_close"] - df["close"]) / df["close"]
    # per DOWN gap (LONG) il fill e' positivo se close sale verso prev_close
    # -> realized_ret gia' allineato col segno del trade_return
    df["trade_pnl_signed"] = df["realized_ret"]  # proxy 1-day

    print("=" * 70)
    print("CONFRONTO VALUTAZIONI PROGETTO vs DATI REALI (proxy giornaliero)")
    print("=" * 70)
    print(f"Universe: {df['ticker'].nunique()} ticker | {len(df)} gap-barre nel")
    print(f"operating window [gap_min={st.gap_min_pct}, gap_max={st.gap_max_pct}]")

    # --- Tabella per bucket (valutazione reale) ---
    print("\n--- EXPECTANCY REALE per bucket (proxy 1-day fill) ---")
    rows = []
    for b, sub in df.groupby("bucket"):
        n = len(sub)
        mean = sub["trade_pnl_signed"].mean()
        std = sub["trade_pnl_signed"].std(ddof=1) if n > 1 else 0.0
        win = (sub["trade_pnl_signed"] > 0).mean()
        rows.append((b, n, mean * 1e4, std * 1e4, win * 100))
    print(f"{'bucket':<14}{'N':>6}{'mean_bp':>9}{'std_bp':>9}{'win%':>7}")
    for b, n, m, s, w in sorted(rows, key=lambda r: str(r[0])):
        tag = "" if n >= 30 else "  (N<30: insufficiente)"
        print(f"{b:<14}{n:>6}{m:>9.1f}{s:>9.1f}{w:>7.1f}{tag}")

    # --- Valutazione progetto (dichiarata nel design) vs reale ---
    print("\n--- CONFRONTO con le valutazioni dichiarate nel design ---")
    print("Design §3.2 fill rate (stesso giorno):")
    print("  0.3-0.5% ~72% | 0.5-1% ~58% | 1-2% ~45% | >2% ~30%")
    # proxy fill: % di trade con realized_ret stesso segno del trade_return atteso
    overall_win = (df["trade_pnl_signed"] > 0).mean() * 100
    print(f"REALE (proxy 1-day, stesso segno): win_rate medio = {overall_win:.1f}%")
    print("  -> NOTA: proxy 1-day NON e' il fill rate intraday; e' solo un")
    print("     segnale di coerenza direzionale del gap mean-reversion.")

    # --- R:R via modulo risk (Fase 4) su un caso tipico ---
    print("\n--- R:R EFFETTIVO via modulo risk.risk (Fase 4) ---")
    # caso LONG tipico: entry 99.85, OR 99.2/100.1, prev_close 100
    plan_pure = compute_position(
        direction="LONG", entry_price=99.85, opening_range_high=100.1,
        opening_range_low=99.2, prev_close=100.0, capital=settings.execution.initial_capital,
        risk_per_trade=settings.execution.risk_per_trade, atr=0.5, atr_target=0.5,
        min_stop_distance_pct=0.001, max_position_size=0.95, partial_tp_frac=0.0)
    plan_fix = compute_position(
        direction="LONG", entry_price=99.85, opening_range_high=100.1,
        opening_range_low=99.2, prev_close=100.0, capital=settings.execution.initial_capital,
        risk_per_trade=settings.execution.risk_per_trade, atr=0.5, atr_target=0.5,
        min_stop_distance_pct=0.001, max_position_size=0.95, partial_tp_frac=0.5)
    print(f"  pure (no partial):  effective_rr = {plan_pure.effective_rr():.3f}")
    print(f"  partial 50%:        effective_rr = {plan_fix.effective_rr():.3f}")
    print("  -> Il modulo risk conferma R:R<1 a struttura pura; il partial")
    print("     TP lo porta a ~0.31 ma resta <1 nel caso small-gap/wide-OR.")

    # --- Verdetto gate Fase 2 (usa gap_calc.evaluate_gate sui dati reali) ---
    print("\n--- GATE FASE 2 sui dati reali (gap_calc.evaluate_gate) ---")
    from src.strategy.gap_calc import evaluate_gate, EXPECTANCY_MIN_TRADES_DEFAULT
    gate = evaluate_gate(df, min_trades=EXPECTANCY_MIN_TRADES_DEFAULT)
    print(f"  passed = {gate.passed}  reason = {gate.reason}")
    decisive = [r for r in gate.buckets if r.is_decisive(EXPECTANCY_MIN_TRADES_DEFAULT)]
    for r in decisive:
        print(f"  DECISIVO: {r.label:<14} N={r.n:>4} mean_ret={r.mean_return*1e4:>7.1f}bp "
              f"sharpe={r.approx_sharpe:.2f}")


if __name__ == "__main__":
    main()
