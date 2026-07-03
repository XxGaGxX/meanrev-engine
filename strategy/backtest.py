import sys
from pathlib import Path
import logging

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR))

LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

import backtrader as bt
import pandas as pd
import numpy as np
from analysis import hedge_ratio as hr

DATA_DIR = ROOT_DIR / "data"


class PairsTrading(bt.Strategy):
    params = (
        ('hedge_ratio', None),
        ('intercept', 0.0),
        ('window', 60),
        ('entry_z_score', 2.0),
        ('exit_z_score', 0.5),
        ('allocation_pct', 0.05),
        ('debug', True),
    )

    def log(self, txt):
        dt = self.datas[0].datetime.date(0)
        msg = f"{dt} | {txt}"
        logger.info(msg)
        if self.p.debug:
            print(msg)

    def __init__(self):
        self.mpc = self.datas[0]
        self.psx = self.datas[1]
        self.log1 = []  # storico log(prezzi)
        self.log2 = []  # storico log(prezzi)

    def next(self):
        mpc_close = self.mpc.close[0]
        psx_close = self.psx.close[0]

        log1 = np.log(mpc_close)
        log2 = np.log(psx_close)
        self.log1.append(log1)
        self.log2.append(log2)

        # Spread = log(P1) - α - β * log(P2) — con α dall'OLS
        spread_today = log1 - self.p.intercept - self.p.hedge_ratio * np.log(psx_close)

        if len(self.log1) < self.p.window:
            return

        # Calcola Z-score su finestra con β E α costanti (ricalcolando tutto con gli stessi coefficienti)
        recent_log1 = np.array(self.log1[-self.p.window:])
        recent_log2 = np.array(self.log2[-self.p.window:])
        recent_spread = recent_log1 - self.p.intercept - self.p.hedge_ratio * recent_log2

        mean = np.mean(recent_spread)
        deviation = np.std(recent_spread)
        z_score = (spread_today - mean) / deviation

        open_pos = self.getposition(self.mpc).size

        if open_pos == 0:
            budget = self.broker.getvalue() * self.p.allocation_pct
            ratio = abs(self.p.hedge_ratio)

            # sizing dollar-neutral: esposizione short:long = 1:β
            size_mpc = budget / (mpc_close * (1 + ratio))
            size_psx = ratio * size_mpc * mpc_close / psx_close

            if z_score > self.p.entry_z_score:
                self.log(
                    f"PRIMA APERTURA | z_score={z_score:.3f} | cash={self.broker.getcash():.2f} | "
                    f"value={self.broker.getvalue():.2f}"
                )
                self.log(
                    f"  → SHORT {self.mpc._name} size={size_mpc:.2f} @ {mpc_close:.2f} | "
                    f"LONG {self.psx._name} size={size_psx:.2f} @ {psx_close:.2f}"
                )

                self.sell(data=self.mpc, size=size_mpc)
                self.buy(data=self.psx, size=size_psx)

            elif z_score < -self.p.entry_z_score:
                self.log(
                    f"PRIMA APERTURA | z_score={z_score:.3f} | cash={self.broker.getcash():.2f} | "
                    f"value={self.broker.getvalue():.2f}"
                )
                self.log(
                    f"  → LONG {self.mpc._name} size={size_mpc:.2f} @ {mpc_close:.2f} | "
                    f"SHORT {self.psx._name} size={size_psx:.2f} @ {psx_close:.2f}"
                )

                self.buy(data=self.mpc, size=size_mpc)
                self.sell(data=self.psx, size=size_psx)

        else:
            if abs(z_score) < self.p.exit_z_score:
                self.log(
                    f"PRIMA CHIUSURA | z_score={z_score:.3f} | pos_mpc={open_pos} | "
                    f"value={self.broker.getvalue():.2f}"
                )
                self.close(data=self.mpc)
                self.close(data=self.psx)
                self.log("  → chiuse entrambe le gambe")

    def notify_order(self, order):
        if order.status == order.Completed:
            side = "BUY" if order.isbuy() else "SELL"
            self.log(
                f"ORDINE ESEGUITO | {side} {order.data._name} size={order.executed.size:.2f} @ "
                f"{order.executed.price:.2f}"
            )

    def notify_trade(self, trade):
        if trade.isclosed:
            self.log(f"TRADE CHIUSO | {trade.data._name} | PnL netto={trade.pnlcomm:.2f}")


def run_backtest(ticker1, ticker2, initial_cash=10000):
    log_filename = LOG_DIR / f"backtest_{ticker1}_{ticker2}.log"

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_filename, mode="w")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)

    df = pd.read_csv(
        DATA_DIR / "csv" / "xle_basket.csv",
        header=[0, 1],
        index_col=0,
        parse_dates=True,
    )
    ticker1_df = df[ticker1]
    ticker2_df = df[ticker2]

    # Allinea le due serie e rimuove righe con dati mancanti; evita NaN nella strategia.
    valid_index = pd.concat(
        [ticker1_df['Close'], ticker2_df['Close']],
        axis=1,
        join='inner'
    ).dropna().index
    ticker1_df = ticker1_df.loc[valid_index]
    ticker2_df = ticker2_df.loc[valid_index]

    hedge_r, intercept = hr.hedge(ticker1_df, ticker2_df)
    print(f"\n>>> Coppia: {ticker1}-{ticker2} | Hedge ratio: {hedge_r:.4f} | Intercept: {intercept:.4f}")

    cerebro = bt.Cerebro()
    cerebro.broker.setcommission(commission=0.002)

    data1 = bt.feeds.PandasData(dataname=ticker1_df)
    data2 = bt.feeds.PandasData(dataname=ticker2_df)

    cerebro.adddata(data1, name=ticker1)
    cerebro.adddata(data2, name=ticker2)
    cerebro.broker.setcash(initial_cash)

    cerebro.addstrategy(PairsTrading, hedge_ratio=hedge_r, intercept=intercept)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    results = cerebro.run()
    strat = results[0]

    final_value = cerebro.broker.getvalue()
    final_cash = cerebro.broker.getcash()
    pnl_totale = final_value - initial_cash

    sharpe = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    trades = strat.analyzers.trades.get_analysis()

    total_trades = trades.total.total if hasattr(trades, 'total') and hasattr(trades.total, 'total') else 0
    won_trades = trades.won.total if hasattr(trades, 'won') and hasattr(trades.won, 'total') else 0
    lost_trades = trades.lost.total if hasattr(trades, 'lost') and hasattr(trades.lost, 'total') else 0

    win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0.0
    avg_win = trades.won.pnl.average if won_trades > 0 else 0.0
    avg_loss = trades.lost.pnl.average if lost_trades > 0 else 0.0

    total_won_pnl = trades.won.pnl.total if won_trades > 0 else 0.0
    total_lost_pnl = abs(trades.lost.pnl.total) if lost_trades > 0 else 0.0
    profit_factor = (total_won_pnl / total_lost_pnl) if total_lost_pnl > 0 else float('inf')

    max_dd_pct = drawdown.max.drawdown if hasattr(drawdown, 'max') else 0.0
    max_dd_money = drawdown.max.moneydown if hasattr(drawdown, 'max') else 0.0
    max_dd_len = drawdown.max.len if hasattr(drawdown, 'max') else 0
    sharpe_ratio = sharpe.get('sharperatio', None)

    summary_lines = [
        "",
        "=" * 50,
        f"RISULTATI FINALI BACKTEST — {ticker1}-{ticker2}",
        "=" * 50,
        f"Cash finale:        {final_cash:.2f}",
        f"Value finale:       {final_value:.2f}",
        f"PnL totale:         {pnl_totale:.2f}",
        f"Return %:           {(pnl_totale / initial_cash * 100):.2f}%",
        "-" * 50,
        f"Numero trade totali: {total_trades}",
        f"Trade vincenti:      {won_trades}",
        f"Trade perdenti:      {lost_trades}",
        f"Win rate:            {win_rate:.2f}%",
        f"PnL medio (win):     {avg_win:.2f}",
        f"PnL medio (loss):    {avg_loss:.2f}",
        f"Profit factor:       {profit_factor:.2f}",
        "-" * 50,
        f"Max drawdown %:      {max_dd_pct:.2f}%",
        f"Max drawdown €:      {max_dd_money:.2f}",
        f"Max drawdown durata: {max_dd_len} barre",
        "-" * 50,
        f"Sharpe ratio:        {sharpe_ratio}",
        "=" * 50,
    ]

    for line in summary_lines:
        logger.info(line)
        print(line)

    return {
        "pair": f"{ticker1}-{ticker2}",
        "final_value": round(final_value, 2),
        "pnl_totale": round(pnl_totale, 2),
        "return_pct": round(pnl_totale / initial_cash * 100, 2),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else None,
        "max_drawdown_pct": round(max_dd_pct, 2),
        "sharpe": round(sharpe_ratio, 4) if sharpe_ratio is not None else None,
    }


if __name__ == "__main__":
    pairs = [
        ("MPC", "PSX"),
        ("KMI", "WMB"),
        ("CVX", "CTRA"),
    ]

    all_results = []
    for t1, t2 in pairs:
        try:
            result = run_backtest(t1, t2)
            all_results.append(result)
        except Exception as e:
            print(f"Errore su {t1}-{t2}: {e}")

    comparison_df = pd.DataFrame(all_results)
    print("\n\n=== CONFRONTO TRA COPPIE ===")
    print(comparison_df.to_string(index=False))

    comparison_df.to_csv(LOG_DIR / "comparison_results.csv", index=False)
    print(f"\nRisultati salvati in {LOG_DIR / 'comparison_results.csv'}")
