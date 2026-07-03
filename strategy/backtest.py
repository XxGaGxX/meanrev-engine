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
from statsmodels.tsa.stattools import adfuller
import statsmodels.api as sm

DATA_DIR = ROOT_DIR / "data"


# =============================================================================
# KALMAN FILTER PURO IN NUMPY (implementazione Ernie Chan / QuantStart)
# =============================================================================

class KalmanHedgeRatio:
    """
    Kalman Filter per stima dinamica di hedge ratio e intercept.
    Implementazione pura in NumPy - nessuna dipendenza esterna.

    Basato su: Chan (2013), "Algorithmic Trading" e QuantStart.

    Modello state-space:
        State:     theta_t = [hedge_ratio_t, intercept_t]
        Dynamics:  theta_t = theta_{t-1} + w_t,   w_t ~ N(0, Q)
        Measure:   y_t = F_t * theta_t + v_t,     v_t ~ N(0, R)

    dove F_t = [log(P2_t), 1] e y_t = log(P1_t)
    """
    def __init__(self, delta=1e-4, vt=1e-3):
        """
        Args:
            delta: process noise scaling (maggiore = adattamento più veloce)
            vt: measurement noise variance (maggiore = filtro più smooth)
        """
        self.delta = delta
        self.wt = delta / (1.0 - delta) * np.eye(2)  # Process noise covariance
        self.vt = vt  # Measurement noise variance

        self.theta = np.zeros(2)  # State: [hedge_ratio, intercept]
        self.C = np.zeros((2, 2))  # State covariance (posterior)
        self.R = None  # Prior covariance
        self.initialized = False

    def update(self, y, x):
        """
        Aggiorna lo stato con nuova osservazione.

        Args:
            y: prezzo asset dipendente in log (log(P1))
            x: prezzo asset indipendente in log (log(P2))

        Returns:
            hedge_ratio, intercept, spread (forecast error), spread_std (sqrt_Qt)
        """
        # Observation matrix: F = [x, 1]
        F = np.array([x, 1.0]).reshape((1, 2))

        # === PREDICT STEP ===
        if self.R is not None:
            self.R = self.C + self.wt
        else:
            self.R = np.zeros((2, 2))

        # === FORECAST ===
        yhat = F.dot(self.theta)[0]  # Predicted observation
        et = y - yhat  # Forecast error (spread)

        # Variance of prediction
        Qt = F.dot(self.R).dot(F.T) + self.vt
        sqrt_Qt = np.sqrt(Qt[0, 0])

        # === UPDATE STEP ===
        # Kalman gain
        At = self.R.dot(F.T) / Qt

        # Update state
        self.theta = self.theta + At.flatten() * et

        # Update covariance
        self.C = self.R - At * F.dot(self.R)

        self.initialized = True

        return self.theta[0], self.theta[1], et, sqrt_Qt


# =============================================================================
# FUNZIONI HELPER
# =============================================================================

def is_cointegrated(spread_series, significance=0.05):
    """Test ADF sullo spread. Ritorna True se cointegrato."""
    result = adfuller(spread_series.dropna())
    return result[1] < significance


def half_life_ou(spread):
    """Half-life della mean reversion (Ornstein-Uhlenbeck)."""
    spread = spread.dropna()
    if len(spread) < 3:
        return np.inf
    
    spread_lag = spread.shift(1).values[1:]
    spread_diff = spread.diff().values[1:]
    
    X = sm.add_constant(spread_lag)
    model = sm.OLS(spread_diff, X)
    result = model.fit()
    
    theta = -result.params[1]
    return np.log(2) / theta if theta > 0 else np.inf


class PairsTrading(bt.Strategy):
    """
    Strategia Pairs Trading con mean reversion su spread logaritmico.
    VERSIONE MIGLIORATA - v2.0

    MIGLIORAMENTI RISPETTO ALLA VERSIONE PRECEDENTE:

    1. Kalman Filter per hedge ratio dinamico (implementazione pura NumPy)
    2. Sizing dollar-neutral CORRETTO (notionale identico per entrambe le gambe)
    3. Allocation aumentata al 20% per miglior utilizzo del capitale
    4. Time stop allungato a 120 giorni (evita chiusure forzate premature)
    5. Filtro cointegrazione dinamico con half-life e ADF test
    6. Commissioni e slippage ridotti per simulare broker professionali
    7. Regime filter: blocco ingressi se drawdown portfolio > 10%
    8. Logging migliorato con metriche di risk management
    9. Risk management: tracking drawdown e performance
    10. Opzione per usare OLS rolling come fallback
    """
    params = (
        ('hedge_ratio', None),           # Hedge ratio iniziale (da training)
        ('intercept', 0.0),              # Intercept iniziale
        ('window', 60),                  # Finestra z-score
        ('entry_z_score', 2.0),          # Soglia ingresso
        ('exit_z_score', 0.5),           # Soglia uscita
        ('stop_z_score', 4.0),           # Stop loss sullo spread
        ('allocation_pct', 0.20),        # AUMENTATO: da 5% a 20%
        ('hedge_lookback', 252),         # Finestra OLS (fallback)
        ('commission', 0.0001),          # RIDOTTO: da 0.05% a 0.01%
        ('slippage_perc', 0.0002),      # RIDOTTO: da 0.1% a 0.02%
        ('max_trade_duration', 120),      # AUMENTATO: da 60 a 120 giorni
        ('use_kalman', True),             # NUOVO: usa Kalman Filter
        ('kalman_delta', 1e-4),          # NUOVO: process noise Kalman
        ('kalman_vt', 1e-3),             # NUOVO: measurement noise Kalman
        ('min_half_life', 5),             # NUOVO: min half-life in giorni
        ('max_half_life', 30),            # NUOVO: max half-life in giorni
        ('adf_significance', 0.05),       # NUOVO: soglia test ADF
        ('use_regime_filter', True),      # NUOVO: filtro regime drawdown
        ('max_portfolio_dd', 0.10),       # NUOVO: max drawdown portfolio 10%
        ('debug', True),
    )

    def log(self, txt):
        dt = self.datas[0].datetime.date(0)
        msg = f"{dt} | {txt}"
        logger.info(msg)
        if self.p.debug:
            print(msg)

    def __init__(self):
        self.entry_date = None
        self.ticker1 = self.datas[0]
        self.ticker2 = self.datas[1]
        self.log1 = []  # Storico log(prezzi ticker1)
        self.log2 = []  # Storico log(prezzi ticker2)

        # Sentinel per tracking ordini pendenti
        self.order_ticker1 = None
        self.order_ticker2 = None

        # Kalman Filter per hedge ratio dinamico
        if self.p.use_kalman:
            self.kf = KalmanHedgeRatio(
                delta=self.p.kalman_delta,
                vt=self.p.kalman_vt
            )
            self.current_hedge_ratio = self.p.hedge_ratio if self.p.hedge_ratio is not None else 1.0
            self.current_intercept = self.p.intercept
        else:
            self.current_hedge_ratio = self.p.hedge_ratio
            self.current_intercept = self.p.intercept
            self.kf = None

        # Tracking stato strategia
        self.trade_count = 0
        self.stop_count = 0
        self.time_stop_count = 0
        self.adf_fail_count = 0

        # Risk management tracking
        self.portfolio_peak = 0
        self.current_dd = 0.0
        self.trade_pnls = []

        # Half-life tracking
        self.half_life_history = []

    def notify_order(self, order):
        """Gestione completa degli stati ordine + reset sentinel."""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            side = "BUY" if order.isbuy() else "SELL"
            self.log(
                f"ORDINE ESEGUITO | {side} {order.data._name} size={order.executed.size:.2f} @ "
                f"{order.executed.price:.2f} | comm={order.executed.comm:.2f}"
            )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(
                f"ORDINE FALLITO | {order.data._name} status={order.status_name()} | "
                f"size={order.size}"
            )

        # Reset sentinel indipendentemente dall'esito
        if order.data == self.ticker1:
            self.order_ticker1 = None
        elif order.data == self.ticker2:
            self.order_ticker2 = None

    def notify_trade(self, trade):
        if trade.isclosed:
            pnl = trade.pnlcomm
            self.trade_pnls.append(pnl)
            self.log(f"TRADE CHIUSO | {trade.data._name} | PnL netto={pnl:.2f}")

    def _update_hedge_ratio_kalman(self):
        """Aggiorna hedge ratio usando Kalman Filter."""
        if self.kf is None:
            return None, None

        t1_close = self.ticker1.close[0]
        t2_close = self.ticker2.close[0]

        log1 = np.log(t1_close)
        log2 = np.log(t2_close)

        # Kalman Filter update: y = log1, x = log2
        # Modello: log1 = intercept + hedge_ratio * log2 + noise
        hr, intercept, spread, spread_std = self.kf.update(log1, log2)

        self.current_hedge_ratio = hr
        self.current_intercept = intercept

        return spread, spread_std

    def _update_hedge_ratio_ols(self):
        """Metodo OLS rolling originale (fallback)."""
        if len(self.log1) < self.p.hedge_lookback:
            return

        recent_log1 = np.array(self.log1[-self.p.hedge_lookback:])
        recent_log2 = np.array(self.log2[-self.p.hedge_lookback:])

        # Regressione lineare: log1 = alpha + beta * log2
        beta, alpha = np.polyfit(recent_log2, recent_log1, 1)
        self.current_hedge_ratio = beta
        self.current_intercept = alpha

    def _calculate_z_score(self):
        """Calcola z-score dello spread usando hedge ratio corrente."""
        t1_close = self.ticker1.close[0]
        t2_close = self.ticker2.close[0]

        log1 = np.log(t1_close)
        log2 = np.log(t2_close)

        self.log1.append(log1)
        self.log2.append(log2)

        # Aggiorna hedge ratio
        spread_std_kalman = None
        if self.p.use_kalman and self.kf is not None:
            spread_today, spread_std_kalman = self._update_hedge_ratio_kalman()
            if spread_today is None:
                return None, log1, log2, t1_close, t2_close, None, None
        else:
            self._update_hedge_ratio_ols()
            spread_today = log1 - self.current_intercept - self.current_hedge_ratio * log2

        if len(self.log1) < self.p.window:
            return None, log1, log2, t1_close, t2_close, None, None

        # Z-score su finestra rolling
        recent_log1 = np.array(self.log1[-self.p.window:])
        recent_log2 = np.array(self.log2[-self.p.window:])
        recent_spread = recent_log1 - self.current_intercept - self.current_hedge_ratio * recent_log2

        mean = np.mean(recent_spread)
        deviation = np.std(recent_spread)

        if deviation == 0:
            return None, log1, log2, t1_close, t2_close, None, None

        z_score = (spread_today - mean) / deviation

        # Calcola half-life per filtro
        hl = half_life_ou(pd.Series(recent_spread))
        self.half_life_history.append(hl)

        # Test ADF sulla finestra corrente
        adf_pvalue = adfuller(recent_spread)[1]

        return z_score, log1, log2, t1_close, t2_close, hl, adf_pvalue

    def _calculate_sizes(self, t1_close, t2_close):
        """
        Calcola sizing dollar-neutral CORRETTO.

        FIX CRITICO: La versione precedente aveva:
            size_ticker1 = budget / (t1_close * (1 + ratio))
            size_ticker2 = ratio * size_ticker1 * t1_close / t2_close

        Questo NON garantiva notional uguale! Con hr=0.4:
            size1 = 5000 / (150 * 1.4) = 23.8 -> $3,571
            size2 = 0.4 * 23.8 * 150 / 130 = 11.0 -> $1,429

        La versione corretta alloca lo stesso notionale per entrambe le gambe:
            notional_per_leg = budget / 2
            size1 = notional_per_leg / t1_close
            size2 = notional_per_leg / t2_close
        """
        # Budget totale per il trade
        budget = self.broker.getvalue() * self.p.allocation_pct

        # Dollar-neutral: stesso notionale per entrambe le gambe
        notional_per_leg = budget / 2.0

        size_ticker1 = notional_per_leg / t1_close
        size_ticker2 = notional_per_leg / t2_close

        return size_ticker1, size_ticker2

    def _check_regime_filter(self):
        """Filtro regime: non tradare se drawdown portfolio eccessivo."""
        current_value = self.broker.getvalue()

        # Track peak
        if current_value > self.portfolio_peak:
            self.portfolio_peak = current_value

        # Calcola drawdown
        if self.portfolio_peak > 0:
            self.current_dd = (self.portfolio_peak - current_value) / self.portfolio_peak

        # Se drawdown > soglia, blocca nuovi ingressi
        if self.current_dd > self.p.max_portfolio_dd:
            return False

        return True

    def next(self):
        result = self._calculate_z_score()
        if result[0] is None:
            return

        z_score, log1, log2, t1_close, t2_close, hl, adf_p = result

        # Controlla ordini pendenti
        if self.order_ticker1 or self.order_ticker2:
            self.log(
                f"SKIP | ordini pendenti: t1={self.order_ticker1 is not None} "
                f"t2={self.order_ticker2 is not None}"
            )
            return

        # Controlla posizione su ENTRAMBE le gambe
        pos_ticker1 = self.getposition(self.ticker1).size
        pos_ticker2 = self.getposition(self.ticker2).size

        if pos_ticker1 == 0 and pos_ticker2 == 0:
            # === LOGICA DI ENTRATA ===

            # Filtro 1: Half-life nel range ottimale
            # Half-life < 5 giorni: mean reversion troppo veloce (rumore)
            # Half-life > 30 giorni: mean reversion troppo lenta (rischio)
            if hl is not None and not (self.p.min_half_life <= hl <= self.p.max_half_life):
                self.log(f"SKIP | half-life={hl:.1f}d fuori range [{self.p.min_half_life}-{self.p.max_half_life}]")
                return

            # Filtro 2: Cointegrazione attiva
            if adf_p > self.p.adf_significance:
                self.adf_fail_count += 1
                self.log(f"SKIP | ADF p-value={adf_p:.4f} > {self.p.adf_significance} (no cointegrazione)")
                return

            # Filtro 3: Regime (drawdown)
            if self.p.use_regime_filter and not self._check_regime_filter():
                self.log(f"SKIP | regime filter attivo (dd={self.current_dd:.2%})")
                return

            size_ticker1, size_ticker2 = self._calculate_sizes(t1_close, t2_close)

            if z_score > self.p.entry_z_score:
                self.entry_date = len(self)  # bar corrente
                self.trade_count += 1
                self.log(
                    f"APERTURA #{self.trade_count} | z={z_score:.3f} | hl={hl:.1f}d | "
                    f"hr={self.current_hedge_ratio:.4f} | adf_p={adf_p:.4f} | "
                    f"cash={self.broker.getcash():.2f} | value={self.broker.getvalue():.2f}"
                )
                self.log(
                    f"  -> SHORT {self.ticker1._name} size={size_ticker1:.2f} @ {t1_close:.2f} | "
                    f"LONG {self.ticker2._name} size={size_ticker2:.2f} @ {t2_close:.2f}"
                )

                self.order_ticker1 = self.sell(data=self.ticker1, size=size_ticker1)
                self.order_ticker2 = self.buy(data=self.ticker2, size=size_ticker2)

            elif z_score < -self.p.entry_z_score:
                self.entry_date = len(self)  # bar corrente
                self.trade_count += 1
                self.log(
                    f"APERTURA #{self.trade_count} | z={z_score:.3f} | hl={hl:.1f}d | "
                    f"hr={self.current_hedge_ratio:.4f} | adf_p={adf_p:.4f} | "
                    f"cash={self.broker.getcash():.2f} | value={self.broker.getvalue():.2f}"
                )
                self.log(
                    f"  -> LONG {self.ticker1._name} size={size_ticker1:.2f} @ {t1_close:.2f} | "
                    f"SHORT {self.ticker2._name} size={size_ticker2:.2f} @ {t2_close:.2f}"
                )

                self.order_ticker1 = self.buy(data=self.ticker1, size=size_ticker1)
                self.order_ticker2 = self.sell(data=self.ticker2, size=size_ticker2)

        else:
            # === LOGICA DI USCITA ===
            trade_duration = len(self) - self.entry_date if self.entry_date else 0

            # Time stop (allungato a 120 giorni)
            if trade_duration > self.p.max_trade_duration:
                self.time_stop_count += 1
                self.log(
                    f"TIME STOP #{self.time_stop_count} | durata={trade_duration} giorni | "
                    f"z={z_score:.3f} | hl={hl:.1f}d | value={self.broker.getvalue():.2f}"
                )
                self.close(data=self.ticker1)
                self.close(data=self.ticker2)
                self.log("  -> chiuse entrambe le gambe (TIME STOP)")
                self.entry_date = None
                return

            # Stop loss sullo spread
            if abs(z_score) > self.p.stop_z_score:
                self.stop_count += 1
                self.log(
                    f"STOP LOSS #{self.stop_count} | z={z_score:.3f} | "
                    f"pos_{self.ticker1._name}={pos_ticker1} | "
                    f"pos_{self.ticker2._name}={pos_ticker2} | "
                    f"value={self.broker.getvalue():.2f}"
                )
                self.close(data=self.ticker1)
                self.close(data=self.ticker2)
                self.log("  -> chiuse entrambe le gambe (STOP)")
                self.entry_date = None
                return

            # Chiusura per mean reversion
            elif abs(z_score) < self.p.exit_z_score:
                self.log(
                    f"CHIUSURA | z={z_score:.3f} | "
                    f"pos_{self.ticker1._name}={pos_ticker1} | "
                    f"pos_{self.ticker2._name}={pos_ticker2} | "
                    f"value={self.broker.getvalue():.2f}"
                )
                self.close(data=self.ticker1)
                self.close(data=self.ticker2)
                self.log("  -> chiuse entrambe le gambe")
                self.entry_date = None


def run_backtest(ticker1, ticker2, initial_cash=100000, commission=0.0001, 
                 slippage_perc=0.0002, use_kalman=True, allocation_pct=0.20):
    """
    Esegue backtest per una coppia di ticker con parametri migliorati.

    Args:
        ticker1, ticker2: simboli da tradare
        initial_cash: capitale iniziale (default $100k)
        commission: commissioni per trade (default 0.01%)
        slippage_perc: slippage percentuale (default 0.02%)
        use_kalman: usa Kalman Filter per hedge ratio
        allocation_pct: percentuale capitale allocata per trade (default 20%)
    """
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

    # Allinea le due serie e rimuove righe con dati mancanti
    valid_index = pd.concat(
        [ticker1_df['Close'], ticker2_df['Close']],
        axis=1,
        join='inner'
    ).dropna().index
    ticker1_df = ticker1_df.loc[valid_index]
    ticker2_df = ticker2_df.loc[valid_index]

    # Calcola hedge ratio iniziale su primi 252 giorni
    train_size = min(252, len(ticker1_df) // 2)
    train_df1 = ticker1_df.iloc[:train_size]
    train_df2 = ticker2_df.iloc[:train_size]

    hedge_r, intercept = hr.hedge(train_df1, train_df2)

    # Calcola half-life iniziale
    log1_train = np.log(train_df1['Close'])
    log2_train = np.log(train_df2['Close'])
    spread_train = log1_train - intercept - hedge_r * log2_train
    hl_train = half_life_ou(spread_train)
    adf_p = adfuller(spread_train.dropna())[1]

    print(f"\n>>> Coppia: {ticker1}-{ticker2}")
    print(f"    Hedge ratio (train): {hedge_r:.4f} | Intercept: {intercept:.4f}")
    print(f"    Half-life: {hl_train:.1f} giorni | ADF p-value: {adf_p:.4f}")
    print(f"    Train period: {train_df1.index[0]} to {train_df1.index[-1]} ({train_size} bars)")
    print(f"    Test period:  {ticker1_df.index[train_size]} to {ticker1_df.index[-1]}")
    print(f"    Commission: {commission*100:.3f}% | Slippage: {slippage_perc*100:.3f}%")
    print(f"    Allocation: {allocation_pct*100:.1f}% | Kalman: {use_kalman}")

    cerebro = bt.Cerebro()

    # Commissioni e slippage ridotti
    cerebro.broker.setcommission(commission=commission)
    cerebro.broker.set_slippage_perc(perc=slippage_perc)

    data1 = bt.feeds.PandasData(dataname=ticker1_df)
    data2 = bt.feeds.PandasData(dataname=ticker2_df)

    cerebro.adddata(data1, name=ticker1)
    cerebro.adddata(data2, name=ticker2)
    cerebro.broker.setcash(initial_cash)

    cerebro.addstrategy(
        PairsTrading, 
        hedge_ratio=hedge_r, 
        intercept=intercept,
        commission=commission,
        slippage_perc=slippage_perc,
        use_kalman=use_kalman,
        allocation_pct=allocation_pct
    )

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn', timeframe=bt.TimeFrame.Days)

    results = cerebro.run()
    strat = results[0]

    final_value = cerebro.broker.getvalue()
    final_cash = cerebro.broker.getcash()
    pnl_totale = final_value - initial_cash

    sharpe = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    trades = strat.analyzers.trades.get_analysis()
    returns = strat.analyzers.returns.get_analysis()

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

    total_return = returns.get('rtot', 0.0) if hasattr(returns, 'get') else 0.0
    annual_return = returns.get('rnorm100', 0.0) if hasattr(returns, 'get') else 0.0

    summary_lines = [
        "",
        "=" * 60,
        f"RISULTATI FINALI BACKTEST - {ticker1}-{ticker2}",
        "=" * 60,
        f"Parametri: entry_z={strat.p.entry_z_score} | exit_z={strat.p.exit_z_score} | "
        f"stop_z={strat.p.stop_z_score} | alloc={strat.p.allocation_pct*100:.1f}%",
        f"Commissioni: {commission*100:.3f}% | Slippage: {slippage_perc*100:.3f}%",
        f"Kalman Filter: {strat.p.use_kalman} | Max Trade Duration: {strat.p.max_trade_duration}d",
        "-" * 60,
        f"Cash finale:        {final_cash:.2f}",
        f"Value finale:       {final_value:.2f}",
        f"PnL totale:         {pnl_totale:.2f}",
        f"Return %:           {(pnl_totale / initial_cash * 100):.2f}%",
        f"Return annuo %:     {annual_return:.2f}%",
        "-" * 60,
        f"Numero trade totali: {total_trades}",
        f"Trade vincenti:      {won_trades}",
        f"Trade perdenti:      {lost_trades}",
        f"Win rate:            {win_rate:.2f}%",
        f"PnL medio (win):     {avg_win:.2f}",
        f"PnL medio (loss):    {avg_loss:.2f}",
        f"Profit factor:       {profit_factor:.2f}",
        "-" * 60,
        f"Max drawdown %:      {max_dd_pct:.2f}%",
        f"Max drawdown EUR:    {max_dd_money:.2f}",
        f"Max drawdown durata: {max_dd_len} barre",
        "-" * 60,
        f"Sharpe ratio:        {sharpe_ratio}",
        f"Stop loss attivati:  {strat.stop_count}",
        f"Time stop attivati:  {strat.time_stop_count}",
        f"ADF fail (ingressi bloccati): {strat.adf_fail_count}",
        f"Half-life medio:     {np.mean(strat.half_life_history):.1f} giorni" if strat.half_life_history else "N/A",
        "=" * 60,
    ]

    for line in summary_lines:
        logger.info(line)
        print(line)

    return {
        "pair": f"{ticker1}-{ticker2}",
        "final_value": round(final_value, 2),
        "pnl_totale": round(pnl_totale, 2),
        "return_pct": round(pnl_totale / initial_cash * 100, 2),
        "annual_return_pct": round(annual_return, 2),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else None,
        "max_drawdown_pct": round(max_dd_pct, 2),
        "sharpe": round(sharpe_ratio, 4) if sharpe_ratio is not None else None,
        "commission_pct": round(commission * 100, 3),
        "slippage_pct": round(slippage_perc * 100, 3),
        "stop_loss_count": strat.stop_count,
        "time_stop_count": strat.time_stop_count,
        "adf_fail_count": strat.adf_fail_count,
        "use_kalman": use_kalman,
        "allocation_pct": round(allocation_pct * 100, 1),
    }


def run_sensitivity_analysis(ticker1, ticker2, initial_cash=100000):
    """
    Esegue analisi di sensitivita su commissioni, slippage, allocation e Kalman.
    """
    print("\n" + "=" * 70)
    print("ANALISI DI SENSITIVITA - PARAMETRI CHIAVE")
    print("=" * 70)

    scenarios = [
        ("Conservativo", 0.0001, 0.0002, 0.10, True),
        ("Moderato", 0.0001, 0.0002, 0.20, True),
        ("Aggressivo", 0.0001, 0.0002, 0.30, True),
        ("Senza Kalman", 0.0001, 0.0002, 0.20, False),
        ("Costi alti", 0.0005, 0.001, 0.20, True),
        ("Zero costi", 0.0, 0.0, 0.20, True),
    ]

    results = []
    for name, comm, slip, alloc, kalman in scenarios:
        print(f"\n--- Scenario: {name} ---")
        result = run_backtest(
            ticker1, ticker2, 
            initial_cash=initial_cash,
            commission=comm,
            slippage_perc=slip,
            allocation_pct=alloc,
            use_kalman=kalman
        )
        result["scenario"] = name
        results.append(result)

    df = pd.DataFrame(results)
    cols = ["scenario", "allocation_pct", "commission_pct", "slippage_pct", 
            "return_pct", "profit_factor", "sharpe", "total_trades", "win_rate"]
    print("\n=== RIEPILOGO SENSITIVITA ===")
    print(df[cols].to_string(index=False))

    df.to_csv(LOG_DIR / f"sensitivity_{ticker1}_{ticker2}.csv", index=False)
    print(f"\nSalvato in {LOG_DIR / f'sensitivity_{ticker1}_{ticker2}.csv'}")

    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Pairs Trading Backtest - Versione Migliorata v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
MIGLIORAMENTI RISPETTO ALLA VERSIONE PRECEDENTE:
  1. Kalman Filter per hedge ratio dinamico (implementazione pura NumPy)
  2. Sizing dollar-neutral corretto (notionale identico per entrambe le gambe)
  3. Allocation aumentata al 20%%
  4. Time stop allungato a 120 giorni
  5. Filtro cointegrazione dinamico (half-life + ADF test)
  6. Commissioni/slippage ridotti (0.01%% / 0.02%%)
  7. Regime filter per drawdown portfolio
  8. Nessuna dipendenza esterna per Kalman Filter

ESEMPI:
  python backtest_improved.py --pair MPC-PSX
  python backtest_improved.py --pair MPC-PSX --sensitivity
  python backtest_improved.py --all --commission 0.0002 --slippage 0.0005
  python backtest_improved.py --pair KMI-WMB --no-kalman --allocation 0.15
        """
    )
    parser.add_argument("--sensitivity", action="store_true", 
                        help="Esegui analisi di sensitivita")
    parser.add_argument("--pair", type=str, default="all",
                        help="Coppia da testare: MPC-PSX, KMI-WMB, CVX-CTRA, o 'all'")
    parser.add_argument("--cash", type=float, default=100000,
                        help="Capitale iniziale")
    parser.add_argument("--commission", type=float, default=0.0001,
                        help="Commissioni per trade (default 0.0001 = 0.01%%)")
    parser.add_argument("--slippage", type=float, default=0.0002,
                        help="Slippage percentuale (default 0.0002 = 0.02%%)")
    parser.add_argument("--allocation", type=float, default=0.20,
                        help="Allocation per trade (default 0.20 = 20%%)")
    parser.add_argument("--no-kalman", action="store_true",
                        help="Disabilita Kalman Filter (usa OLS rolling)")
    args = parser.parse_args()

    pairs = [
        ("MPC", "PSX"),
        ("KMI", "WMB"),
        ("CVX", "CTRA"),
    ]

    if args.pair != "all":
        t1, t2 = args.pair.split("-")
        pairs = [(t1, t2)]

    if args.sensitivity and len(pairs) == 1:
        run_sensitivity_analysis(pairs[0][0], pairs[0][1], initial_cash=args.cash)
    else:
        all_results = []
        for t1, t2 in pairs:
            try:
                result = run_backtest(
                    t1, t2, 
                    initial_cash=args.cash,
                    commission=args.commission,
                    slippage_perc=args.slippage,
                    allocation_pct=args.allocation,
                    use_kalman=not args.no_kalman
                )
                all_results.append(result)
            except Exception as e:
                print(f"Errore su {t1}-{t2}: {e}")
                import traceback
                traceback.print_exc()

        comparison_df = pd.DataFrame(all_results)
        print("\n\n=== CONFRONTO TRA COPPIE ===")
        print(comparison_df.to_string(index=False))

        comparison_df.to_csv(LOG_DIR / "comparison_results_improved.csv", index=False)
        print(f"\nRisultati salvati in {LOG_DIR / 'comparison_results_improved.csv'}")
