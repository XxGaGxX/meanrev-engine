# Mean Reversion Intraday — Documentazione Tecnica

**Versione:** 1.0
**Autore progetto:** Gagio
**Stack di riferimento:** Python 3.11+, Backtrader / vectorbt, pandas, TA-Lib

---

## 1. Introduzione e Obiettivo

Questo documento descrive in dettaglio la strategia **Mean Reversion Intraday**, la logica statistica che la sottende, l'implementazione tecnica, e — soprattutto — le tecniche di **ottimizzazione progressiva** per massimizzare il win rate mantenendo un risk/reward sostenibile.

L'obiettivo non è solo "avere ragione spesso" (alto win rate), ma avere ragione spesso **con un edge netto dopo costi**, evitando il problema classico: tanti piccoli trade vinti che vengono spazzati via da pochi trade grossi persi durante un trend forte.

---

## 2. Logica Teorica della Strategia

### 2.1 Il principio statistico

La mean reversion si basa sull'ipotesi che il prezzo di un asset, dopo una deviazione anomala rispetto alla sua media recente, tenda a tornare verso quella media nel breve termine. Questo accade per motivi di **microstruttura di mercato**:

- **Overreaction**: i trader retail e gli algoritmi di momentum a breve termine spingono il prezzo oltre il "fair value" temporaneo in risposta a flussi di ordini, non a nuova informazione fondamentale.
- **Liquidity provision**: i market maker e gli arbitraggisti intervengono per "correggere" la deviazione, fornendo liquidità nella direzione opposta al movimento estremo.
- **Mean-reverting noise**: su timeframe intraday, gran parte della varianza di prezzo è rumore microstrutturale (bid-ask bounce, ordini di grandi dimensioni eseguiti a tranche), non vero trend.

### 2.2 Quando NON funziona (condizione critica)

La mean reversion **fallisce sistematicamente** in presenza di:
- Trend direzionale forte (news reali, cambio di regime)
- Bassa liquidità (lo spread bid-ask "mangia" il piccolo edge)
- Eventi macro/earnings (la deviazione non è rumore, è repricing reale)

**Questo è il punto più importante dell'intero documento**: la strategia non deve mai operare "a prescindere". Deve operare solo quando esiste evidenza statistica che il regime di mercato attuale è mean-reverting. Questo si misura, non si assume.

---

## 3. Framework a 3 Livelli

Per ottimizzare il win rate in modo robusto (non overfittato), la strategia va strutturata su tre livelli indipendenti:

```
LIVELLO 1: Filtro di Regime (decide SE tradare)
    ↓
LIVELLO 2: Segnale di Ingresso (decide QUANDO entrare)
    ↓
LIVELLO 3: Gestione dell'Uscita (decide QUANDO uscire)
```

Il vero win rate elevato non nasce dal segnale di ingresso, ma dal **Livello 1**. Un buon filtro di regime elimina l'80% dei trade "cattivi" prima ancora che il segnale scatti.

---

## 4. Livello 1 — Filtro di Regime (il più importante)

### 4.1 Indicatori di regime

| Indicatore | Funzione | Soglia tipica |
|---|---|---|
| **ADX (Average Directional Index)** | Misura la forza del trend | Operare mean reversion solo se ADX < 20–25 |
| **Hurst Exponent** | Misura se la serie è mean-reverting (H<0.5), random walk (H=0.5) o trending (H>0.5) | Operare solo se H < 0.45 |
| **ATR relativo (ATR / prezzo)** | Filtra condizioni di volatilità anomala | Escludere se ATR% > 2 deviazioni standard dalla media |
| **Variance Ratio Test** | Test statistico di mean reversion vs random walk | p-value < 0.05 conferma mean reversion |

### 4.2 Implementazione del filtro ADX + Hurst

```python
import numpy as np
import pandas as pd

def hurst_exponent(price_series, max_lag=100):
    """Calcola l'esponente di Hurst per determinare il regime."""
    lags = range(2, max_lag)
    tau = [np.std(np.subtract(price_series[lag:], price_series[:-lag]))
           for lag in lags]
    poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
    return poly[0] * 2.0

def is_mean_reverting_regime(df, adx_threshold=22, hurst_threshold=0.45):
    """
    df deve contenere colonne: 'high', 'low', 'close'
    Ritorna una serie booleana: True = regime adatto a mean reversion
    """
    adx = calculate_adx(df, period=14)  # usare TA-Lib: talib.ADX
    hurst = hurst_exponent(df['close'].values[-252:])  # ultimi ~252 periodi

    regime_ok = (adx < adx_threshold) and (hurst < hurst_threshold)
    return regime_ok
```

> **Nota tecnica:** l'Hurst Exponent va ricalcolato periodicamente (es. ogni 20-50 barre), non ad ogni tick — è un indicatore di regime, non di ingresso.

### 4.3 Filtro aggiuntivo: esclusione eventi

Escludere sempre:
- Giorni di earnings/report trimestrali (per equities)
- Orari di rilascio dati macro (per FX/futures — NFP, CPI, FOMC)
- Le prime/ultime 15-30 minuti di sessione (volatilità anomala di apertura/chiusura)

---

## 5. Livello 2 — Segnale di Ingresso

### 5.1 Indicatori combinati (non uno solo)

Usare un **singolo oscillatore non basta** per un win rate elevato: genera troppi falsi segnali. La combinazione di 2-3 conferme indipendenti aumenta drasticamente la qualità del segnale.

| Indicatore | Parametro base | Ruolo |
|---|---|---|
| **RSI** | Periodo 14, soglie 30/70 | Identifica ipercomprato/ipervenduto |
| **Bollinger Bands** | 20 periodi, 2 deviazioni standard | Identifica deviazione statistica dal prezzo medio |
| **Z-score del prezzo** | Rolling window 20-50 periodi | Quantifica la deviazione in termini standardizzati |
| **Volume spike** | Volume > 1.5x media mobile volume | Conferma che la deviazione è "reale" (non rumore a basso volume) |

### 5.2 Regola di ingresso ottimizzata (esempio long)

```python
def entry_signal_long(df, rsi_period=14, bb_period=20, bb_std=2, z_threshold=-2):
    rsi = talib.RSI(df['close'], timeperiod=rsi_period)
    upper, middle, lower = talib.BBANDS(df['close'], timeperiod=bb_period, 
                                          nbdevup=bb_std, nbdevdn=bb_std)
    rolling_mean = df['close'].rolling(bb_period).mean()
    rolling_std = df['close'].rolling(bb_period).std()
    z_score = (df['close'] - rolling_mean) / rolling_std

    volume_confirm = df['volume'] > (df['volume'].rolling(20).mean() * 1.5)

    # Tripla conferma: RSI + Bollinger + Z-score, con volume come filtro extra
    condition = (
        (rsi < 30) &
        (df['close'] < lower) &
        (z_score < z_threshold) &
        volume_confirm
    )
    return condition
```

**Perché la tripla conferma aumenta il win rate:** ogni indicatore da solo genera falsi positivi in scenari diversi (RSI soffre di divergenze in trend, Bollinger Bands si allargano in alta volatilità, lo z-score da solo ignora il contesto di volume). Richiedendo l'allineamento di più segnali indipendenti, si filtrano statisticamente i casi ambigui — al costo di una minore frequenza di trade (trade-off accettabile: **meglio meno trade con edge reale che tanti trade mediocri**).

### 5.3 Micro-conferma di prezzo (price action)

Aggiungere una conferma di price action riduce ulteriormente i falsi segnali:
- **Candela di rigetto** (pin bar / hammer) alla banda inferiore
- **Divergenza RSI positiva** (prezzo fa un minimo più basso, RSI fa un minimo più alto)

Questo è opzionale ma aumenta tipicamente il win rate del 5-10% a scapito della frequenza.

---

## 6. Livello 3 — Gestione dell'Uscita (dove si vince o si perde davvero)

### 6.1 Il principio chiave

Il win rate elevato della mean reversion (60-80%) è **strutturalmente legato** a come si gestisce l'uscita. Un target di profitto piccolo e uno stop loss stretto ma non troppo generano molte piccole vincite — ma se lo stop è troppo stretto, si viene bruciati dal rumore prima del reversal.

### 6.2 Regole di uscita ottimizzate

| Componente | Regola | Razionale |
|---|---|---|
| **Take Profit** | Ritorno alla media mobile (banda centrale Bollinger) o z-score → 0 | Non fissare un target percentuale arbitrario: uscire quando la mean reversion è "completata" statisticamente |
| **Stop Loss** | 1.5–2× ATR dal prezzo di ingresso | Adattivo alla volatilità corrente, non un valore fisso in % |
| **Time Stop** | Uscita forzata dopo N barre (es. 20-30 barre a 5 min) se il target non è raggiunto | Evita di restare intrappolati se il regime cambia durante il trade |
| **Stop di regime** | Se ADX supera la soglia durante il trade → uscita immediata | Il mercato è passato da mean-reverting a trending: l'edge non esiste più |

### 6.3 Implementazione dello stop di regime (fondamentale)

```python
def check_regime_stop(current_adx, adx_threshold=25):
    """Uscita di emergenza se il regime cambia durante il trade aperto."""
    return current_adx > adx_threshold
```

Questo singolo controllo è spesso la differenza tra una strategia mean reversion profittevole e una che perde tutto in un trend improvviso — è il meccanismo che protegge dal fallimento strutturale descritto al punto 2.2.

---

## 7. Position Sizing e Risk Management

### 7.1 Sizing adattivo alla volatilità

```python
def position_size(account_equity, risk_per_trade_pct, atr, stop_multiplier=1.5):
    """
    Calcola la size in base al rischio fisso per trade e alla volatilità corrente.
    """
    risk_amount = account_equity * (risk_per_trade_pct / 100)
    stop_distance = atr * stop_multiplier
    size = risk_amount / stop_distance
    return size
```

- **Rischio per trade consigliato:** 0.5–1% del capitale (mai oltre il 2%)
- **Correlazione tra posizioni:** se si opera su più asset contemporaneamente, limitare l'esposizione aggregata a settori/asset correlati (es. non aprire 5 posizioni mean reversion su titoli energy nello stesso momento — è lo stesso bet ripetuto 5 volte, non 5 bet indipendenti)

### 7.2 Kelly frazionato per lo scaling

Una volta che la strategia ha uno storico di almeno 100+ trade fuori-sample:

```python
def fractional_kelly(win_rate, avg_win, avg_loss, fraction=0.25):
    """
    Kelly Criterion frazionato (usare 1/4 o 1/2 Kelly, mai Kelly pieno).
    """
    b = avg_win / avg_loss
    kelly_pct = win_rate - ((1 - win_rate) / b)
    return max(0, kelly_pct * fraction)
```

**Importante:** Kelly pieno è troppo aggressivo e genera drawdown insostenibili emotivamente e finanziariamente. Usare sempre una frazione (1/4 – 1/2 Kelly).

---

## 8. Processo di Ottimizzazione (senza cadere nell'overfitting)

Questo è il punto dove la maggior parte dei trader retail — incluse esperienze pregresse su pairs trading — fallisce: backtest ottimo, live negativo. Ecco il processo corretto.

### 8.1 Walk-Forward Analysis (obbligatorio)

```
[Dati Storici Totali]
   |
   ├── Finestra 1: Train (6 mesi) → Test (1 mese)
   ├── Finestra 2: Train (6 mesi, shiftata) → Test (1 mese)
   ├── Finestra 3: ...
   └── Finestra N: ...

Media risultati SOLO sulle finestre di TEST (mai sul train)
```

Mai ottimizzare i parametri (RSI period, soglie Bollinger, ATR multiplier) su tutto il dataset e poi testare sullo stesso periodo: è il motivo #1 per cui un backtest "bello" diventa PNL negativo live.

### 8.2 Monte Carlo sulla sequenza dei trade

Dopo aver ottenuto una lista di trade (anche solo 50-100), applicare un resampling Monte Carlo (bootstrap) per stimare la distribuzione realistica di drawdown, non fidarsi del singolo drawdown storico osservato:

```python
import numpy as np

def monte_carlo_drawdown(trade_returns, n_simulations=10000):
    max_drawdowns = []
    for _ in range(n_simulations):
        resampled = np.random.choice(trade_returns, size=len(trade_returns), replace=True)
        equity_curve = np.cumprod(1 + resampled)
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - running_max) / running_max
        max_drawdowns.append(drawdown.min())
    return np.percentile(max_drawdowns, [5, 50, 95])  # worst-case, mediano, best-case
```

Se il 95° percentile di drawdown simulato è insostenibile per il tuo capitale/psicologia, la strategia — per quanto bella nel backtest puntuale — non è pronta.

### 8.3 Costi di transazione realistici (non opzionali)

Nel backtest, includere **sempre**:
- Commissioni del broker/exchange
- Slippage stimato (tipicamente 1-3 tick su strumenti liquidi, di più su illiquidi)
- Spread bid-ask al momento dell'ingresso/uscita

```python
# Esempio Backtrader: impostare commissione e slippage realistici
cerebro.broker.setcommission(commission=0.001)  # 0.1% per lato
cerebro.broker.set_slippage_perc(perc=0.0005)   # 0.05% di slippage stimato
```

### 8.4 Metriche da monitorare (oltre al win rate)

Il win rate da solo è **fuorviante**. Monitorare sempre insieme:

| Metrica | Perché serve |
|---|---|
| **Profit Factor** (lordo vinto / lordo perso) | Deve essere > 1.3-1.5 per avere margine dopo costi reali |
| **Sharpe Ratio** | Rendimento aggiustato per volatilità |
| **Sortino Ratio** | Come Sharpe ma penalizza solo la volatilità negativa (più rilevante per mean reversion) |
| **Expectancy** = (Win% × Avg Win) − (Loss% × Avg Loss) | Il vero indicatore di edge per trade |
| **Max Drawdown** e durata del drawdown | Sostenibilità psicologica e di capitale |

Un win rate del 75% con expectancy negativa (stop loss enormi occasionali) è una strategia perdente camuffata da "vincente".

---

## 9. Setup Tecnico Consigliato

### 9.1 Stack tecnologico

```
Linguaggio:       Python 3.11+
Backtesting:      Backtrader (flessibile, buon supporto intraday) 
                  o vectorbt (più veloce per ottimizzazioni su griglie ampie)
Indicatori:       TA-Lib (RSI, ADX, Bollinger, ATR nativi e ottimizzati in C)
Dati storici:     Polygon.io / Alpaca (equities USA), CCXT (crypto)
Dati real-time:   WebSocket feed del broker/exchange scelto
Esecuzione live:  Alpaca API (equities) o CCXT (crypto)
Statistica:       statsmodels (Variance Ratio Test), numpy/scipy (Hurst, Monte Carlo)
```

### 9.2 Architettura del sistema

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Data Feed       │ --> │  Regime Filter    │ --> │  Signal Engine   │
│  (real-time OHLCV│     │  (ADX, Hurst)     │     │  (RSI+BB+Vol)    │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                             │
                         ┌──────────────────┐               ▼
                         │  Risk Manager     │ <──── Segnale valido
                         │  (sizing, stops)  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Execution Layer  │
                         │  (broker/exchange │
                         │   API)             │
                         └──────────────────┘
```

### 9.3 Mercati e timeframe consigliati per iniziare

Vista la tua esperienza pregressa (Python, Backtrader, energy sector):
- **Timeframe:** 5-15 minuti (compromesso tra numero di segnali e rumore statistico)
- **Asset:** iniziare su 5-10 titoli liquidi dello stesso settore che già conosci, poi espandere
- **Sessione:** evitare le prime/ultime 30 minuti di mercato regolare

---

## 10. Checklist Pre-Live (da rispettare sempre)

- [ ] Walk-forward analysis completata su almeno 3-4 finestre out-of-sample
- [ ] Monte Carlo su sequenza trade eseguito, drawdown al 95° percentile accettabile
- [ ] Costi di transazione realistici inclusi nel backtest (commissioni + slippage + spread)
- [ ] Filtro di regime (ADX/Hurst) implementato e testato separatamente dal segnale
- [ ] Stop di regime attivo (uscita se il mercato passa da mean-reverting a trending)
- [ ] Position sizing basato sul rischio, non su size fissa
- [ ] Paper trading di almeno 4-6 settimane con esecuzione reale (non solo simulata) prima di capitale vero
- [ ] Expectancy per trade calcolata e positiva anche includendo lo scenario peggiore Monte Carlo
- [ ] Nessun parametro ottimizzato sull'intero dataset (solo su finestre di train)

---

## 11. Errori Comuni da Evitare (riassunto critico)

1. **Ottimizzare i parametri su tutto lo storico** → overfitting garantito, fallimento live.
2. **Ignorare il filtro di regime** → la strategia opera anche in trend forte e perde tutto ciò che ha guadagnato.
3. **Stop loss fisso in %** invece che basato su ATR → non si adatta alla volatilità corrente.
4. **Guardare solo il win rate** senza controllare expectancy e profit factor.
5. **Backtest senza costi di transazione realistici** → il problema che probabilmente hai già vissuto con il pairs trading.
6. **Correlazione ignorata tra posizioni multiple** → si crede di essere diversificati ma si è esposti a un solo rischio ripetuto.
7. **Nessun time stop** → capitale bloccato in trade "morti" che non convergono né vanno in stop.

---

## 12. Guida Operativa Step-by-Step all'Implementazione

Questa sezione traduce tutto quanto descritto finora in una sequenza operativa concreta, dal fetch dei dati fino al deployment live. Ogni step include cosa fare, perché, e codice di riferimento.

---

### 12.1 Fetch Dati

**Obiettivo:** ottenere dati OHLCV puliti, allineati e privi di bias, sia storici (per backtest) sia real-time (per il live).

#### Passo 1 — Definire l'universo di asset
Selezionare 5-10 titoli/asset liquidi, idealmente dello stesso settore (riuso della tua esperienza su energy sector), per poter poi applicare filtri di correlazione.

```python
universe = ["XOM", "CVX", "COP", "SLB", "EOG"]  # esempio energy sector
```

**Perché:** partire da un universo ristretto e noto permette di validare la logica prima di scalare, e riduce il rischio di survivorship bias se si sceglie l'universo *prima* di guardare le performance storiche (mai selezionare i titoli "perché sono andati bene" — è survivorship bias puro).

#### Passo 2 — Fetch dati storici (per backtest)

```python
import alpaca_trade_api as tradeapi
import pandas as pd

api = tradeapi.REST(API_KEY, API_SECRET, base_url="https://paper-api.alpaca.markets")

def fetch_historical_data(symbol, timeframe="5Min", start="2022-01-01", end="2024-12-31"):
    bars = api.get_bars(symbol, timeframe, start=start, end=end).df
    bars = bars[["open", "high", "low", "close", "volume"]]
    return bars

data = {sym: fetch_historical_data(sym) for sym in universe}
```

**Perché Alpaca (o Polygon):** forniscono dati intraday storici già aggiustati per split/dividendi (adjusted), evitando gap artificiali nei prezzi che genererebbero falsi segnali di mean reversion.

#### Passo 3 — Pulizia e validazione dei dati

```python
def clean_data(df):
    df = df[~df.index.duplicated(keep="first")]      # rimuove timestamp duplicati
    df = df.dropna()                                    # rimuove barre incomplete
    df = df[(df["volume"] > 0)]                          # rimuove barre a volume zero (mercato chiuso/halted)
    df = df.sort_index()
    return df

data = {sym: clean_data(df) for sym, df in data.items()}
```

**Perché:** dati sporchi (gap, duplicati, barre a volume zero per halt di trading) generano segnali fantasma — z-score e RSI calcolati su dati corrotti producono falsi ingressi.

#### Passo 4 — Allineamento temporale multi-asset

```python
def align_data(data_dict):
    common_index = None
    for df in data_dict.values():
        common_index = df.index if common_index is None else common_index.intersection(df.index)
    return {sym: df.loc[common_index] for sym, df in data_dict.items()}

data = align_data(data)
```

**Perché:** se si opera su più asset in parallelo per il risk management aggregato (Sezione 7.1), serve che tutte le serie abbiano gli stessi timestamp, altrimenti i calcoli di correlazione ed esposizione aggregata sono falsati.

#### Passo 5 — Setup del fetch real-time (per paper/live trading)

```python
from alpaca_trade_api.stream import Stream

stream = Stream(API_KEY, API_SECRET, base_url="https://paper-api.alpaca.markets")

async def on_bar(bar):
    # bar contiene: symbol, open, high, low, close, volume, timestamp
    update_live_dataframe(bar)

for sym in universe:
    stream.subscribe_bars(on_bar, sym)

stream.run()
```

**Perché il websocket e non il polling:** il polling (richieste REST ripetute) introduce latenza variabile e rischia rate-limit da parte del broker; il websocket garantisce dati in tempo reale con overhead minimo, essenziale anche per una strategia non-HFT come questa.

---

### 12.2 Creazione Indicatori

Ogni indicatore va costruito come modulo indipendente e testato singolarmente prima di essere combinato nel segnale finale.

#### Indicatore 1 — ADX (Average Directional Index)
**Cos'è:** misura la forza di un trend (non la direzione), su una scala 0-100.
**Perché lo usiamo:** è il primo filtro di regime (Sezione 4). Se l'ADX è alto, il mercato sta trendando e la mean reversion va disattivata.

```python
import talib

def add_adx(df, period=14):
    df["adx"] = talib.ADX(df["high"], df["low"], df["close"], timeperiod=period)
    return df
```

#### Indicatore 2 — Hurst Exponent
**Cos'è:** misura statistica che classifica una serie storica come mean-reverting (H<0.5), random walk (H≈0.5) o trending/persistente (H>0.5).
**Perché lo usiamo:** l'ADX misura la forza del trend *attuale*, ma l'Hurst conferma la natura statistica *strutturale* della serie in una finestra più ampia — le due misure insieme riducono i falsi positivi del filtro di regime.

```python
import numpy as np

def add_hurst(df, window=252, min_lag=2, max_lag=100):
    def hurst(ts):
        lags = range(min_lag, max_lag)
        tau = [np.std(np.subtract(ts[lag:], ts[:-lag])) for lag in lags]
        poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
        return poly[0] * 2.0

    df["hurst"] = df["close"].rolling(window).apply(lambda x: hurst(x.values), raw=False)
    return df
```

#### Indicatore 3 — RSI (Relative Strength Index)
**Cos'è:** oscillatore momentum 0-100 che misura la velocità e l'ampiezza dei movimenti di prezzo recenti.
**Perché lo usiamo:** è il primo segnale di ingresso (Sezione 5) — identifica condizioni di ipercomprato (>70) e ipervenduto (<30), cioè le deviazioni che la strategia vuole sfruttare.

```python
def add_rsi(df, period=14):
    df["rsi"] = talib.RSI(df["close"], timeperiod=period)
    return df
```

#### Indicatore 4 — Bollinger Bands
**Cos'è:** bande di deviazione standard (tipicamente ±2σ) attorno a una media mobile.
**Perché lo usiamo:** quantifica *quanto* il prezzo si è allontanato dalla media in termini statistici assoluti (non solo di momentum come l'RSI) — è la seconda conferma indipendente richiesta dal segnale.

```python
def add_bollinger(df, period=20, std_dev=2):
    upper, middle, lower = talib.BBANDS(df["close"], timeperiod=period,
                                          nbdevup=std_dev, nbdevdn=std_dev)
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = upper, middle, lower
    return df
```

#### Indicatore 5 — Z-score rolling
**Cos'è:** normalizzazione della deviazione del prezzo dalla media, espressa in numero di deviazioni standard.
**Perché lo usiamo:** rende la deviazione confrontabile tra asset diversi (un titolo a 10$ e uno a 500$ non sono comparabili in termini assoluti) ed è la terza conferma quantitativa, oltre a essere il criterio di uscita (target = z-score → 0).

```python
def add_zscore(df, window=20):
    rolling_mean = df["close"].rolling(window).mean()
    rolling_std = df["close"].rolling(window).std()
    df["zscore"] = (df["close"] - rolling_mean) / rolling_std
    return df
```

#### Indicatore 6 — Volume Filter
**Cos'è:** confronto tra volume corrente e media mobile del volume.
**Perché lo usiamo:** una deviazione di prezzo su basso volume è spesso rumore/illiquidità, non una vera overreaction del mercato — il filtro volume separa i segnali "reali" da quelli statisticamente deboli.

```python
def add_volume_filter(df, window=20, multiplier=1.5):
    df["vol_avg"] = df["volume"].rolling(window).mean()
    df["vol_confirm"] = df["volume"] > (df["vol_avg"] * multiplier)
    return df
```

#### Indicatore 7 — ATR (Average True Range)
**Cos'è:** misura la volatilità media recente in termini assoluti di prezzo.
**Perché lo usiamo:** non è un segnale di ingresso ma è essenziale per stop loss adattivi (Sezione 6.2) e per il position sizing (Sezione 7.1) — evita stop fissi in % che non si adattano alla volatilità corrente dell'asset.

```python
def add_atr(df, period=14):
    df["atr"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=period)
    return df
```

#### Pipeline completa di creazione indicatori

```python
def build_all_indicators(df):
    df = add_adx(df)
    df = add_hurst(df)
    df = add_rsi(df)
    df = add_bollinger(df)
    df = add_zscore(df)
    df = add_volume_filter(df)
    df = add_atr(df)
    return df.dropna()  # rimuove le righe iniziali senza indicatori calcolabili (warm-up period)

data = {sym: build_all_indicators(df) for sym, df in data.items()}
```

---

### 12.3 Costruzione del Filtro di Regime

**Obiettivo:** produrre un flag booleano `regime_ok` che autorizza o blocca la generazione di segnali.

```python
def apply_regime_filter(df, adx_threshold=22, hurst_threshold=0.45):
    df["regime_ok"] = (df["adx"] < adx_threshold) & (df["hurst"] < hurst_threshold)
    return df
```

**Step di validazione (obbligatorio prima di proseguire):**
1. Calcolare la percentuale di tempo in cui `regime_ok = True` sui dati storici — se è troppo bassa (<10%) il filtro è troppo restrittivo, se troppo alta (>70%) probabilmente non sta filtrando nulla di utile.
2. Verificare a occhio (plot) che i periodi con `regime_ok = True` corrispondano visivamente a fasi laterali/range-bound del prezzo, e `regime_ok = False` a trend evidenti.

---

### 12.4 Costruzione del Segnale di Ingresso

```python
def generate_entry_signals(df, z_threshold=2):
    long_signal = (
        df["regime_ok"] &
        (df["rsi"] < 30) &
        (df["close"] < df["bb_lower"]) &
        (df["zscore"] < -z_threshold) &
        df["vol_confirm"]
    )

    short_signal = (
        df["regime_ok"] &
        (df["rsi"] > 70) &
        (df["close"] > df["bb_upper"]) &
        (df["zscore"] > z_threshold) &
        df["vol_confirm"]
    )

    df["long_entry"] = long_signal
    df["short_entry"] = short_signal
    return df
```

**Step di validazione:** contare il numero di segnali generati su tutto il periodo storico. Se sono troppo pochi (<30-50 in totale sull'intero storico) il campione non sarà statisticamente affidabile per validare la strategia — allargare l'universo di asset o allentare leggermente le soglie (con cautela, senza fare curve-fitting).

---

### 12.5 Costruzione della Logica di Uscita

```python
def simulate_exit(df, entry_idx, direction, atr_multiplier=1.5, max_bars=25, adx_stop=25):
    entry_price = df["close"].iloc[entry_idx]
    entry_atr = df["atr"].iloc[entry_idx]
    stop_distance = entry_atr * atr_multiplier

    stop_price = entry_price - stop_distance if direction == "long" else entry_price + stop_distance

    for i in range(entry_idx + 1, min(entry_idx + max_bars, len(df))):
        row = df.iloc[i]

        # Stop di regime: uscita se il trend riprende forza
        if row["adx"] > adx_stop:
            return row["close"], i, "regime_stop"

        # Stop loss classico
        if direction == "long" and row["low"] <= stop_price:
            return stop_price, i, "stop_loss"
        if direction == "short" and row["high"] >= stop_price:
            return stop_price, i, "stop_loss"

        # Take profit: ritorno alla media (z-score torna verso 0)
        if direction == "long" and row["zscore"] >= 0:
            return row["close"], i, "take_profit"
        if direction == "short" and row["zscore"] <= 0:
            return row["close"], i, "take_profit"

    # Time stop: nessuna condizione soddisfatta entro max_bars
    last_row = df.iloc[min(entry_idx + max_bars, len(df) - 1)]
    return last_row["close"], entry_idx + max_bars, "time_stop"
```

**Perché ogni componente:**
- **Stop di regime** (già descritto in 6.3): priorità massima, protegge dal fallimento strutturale della strategia.
- **Stop loss su ATR**: adattivo alla volatilità reale dell'asset in quel momento specifico.
- **Take profit su z-score**: esce quando la mean reversion si è statisticamente "completata", non su un target arbitrario in %.
- **Time stop**: libera capitale se il trade non converge né va in stop — evita immobilizzo prolungato.

---

### 12.6 Costruzione del Position Sizing

```python
def calculate_position_size(account_equity, risk_pct, entry_price, stop_price):
    risk_amount = account_equity * (risk_pct / 100)
    per_share_risk = abs(entry_price - stop_price)
    shares = int(risk_amount / per_share_risk)
    return shares
```

**Step operativo:** integrare questa funzione nel motore di backtest in modo che ogni trade simulato usi la size correttamente calcolata, non una size fissa — un backtest a size fissa sovrastima o sottostima sistematicamente il rischio reale.

---

### 12.7 Assemblaggio del Motore di Backtest (Backtrader)

```python
import backtrader as bt

class MeanReversionStrategy(bt.Strategy):
    params = dict(
        rsi_period=14, bb_period=20, bb_std=2,
        adx_period=14, atr_period=14,
        adx_threshold=22, z_threshold=2,
        risk_pct=1.0, atr_multiplier=1.5, max_bars=25
    )

    def __init__(self):
        self.rsi = bt.ind.RSI(period=self.p.rsi_period)
        self.bb = bt.ind.BollingerBands(period=self.p.bb_period, devfactor=self.p.bb_std)
        self.adx = bt.ind.ADX(period=self.p.adx_period)
        self.atr = bt.ind.ATR(period=self.p.atr_period)
        self.bar_executed = 0

    def next(self):
        if self.position:
            # Logica di uscita (stop di regime, stop loss, take profit, time stop)
            if self.adx[0] > 25 or (len(self) - self.bar_executed) > self.p.max_bars:
                self.close()
            return

        if self.adx[0] < self.p.adx_threshold:
            if self.rsi[0] < 30 and self.data.close[0] < self.bb.lines.bot[0]:
                size = self.calculate_size()
                self.buy(size=size)
                self.bar_executed = len(self)
            elif self.rsi[0] > 70 and self.data.close[0] > self.bb.lines.top[0]:
                size = self.calculate_size()
                self.sell(size=size)
                self.bar_executed = len(self)

    def calculate_size(self):
        risk_amount = self.broker.getvalue() * (self.p.risk_pct / 100)
        stop_distance = self.atr[0] * self.p.atr_multiplier
        return int(risk_amount / stop_distance)
```

**Step operativo:**
1. Caricare i dati puliti nel `cerebro` di Backtrader con `bt.feeds.PandasData`.
2. Impostare commissioni e slippage realistici (vedi Sezione 8.3).
3. Eseguire un primo backtest su un solo asset per validare che la logica non abbia bug prima di scalare all'intero universo.

---

### 12.8 Esecuzione della Walk-Forward Analysis

```python
def walk_forward_windows(df, train_months=6, test_months=1):
    windows = []
    start = df.index.min()
    end = df.index.max()
    current = start

    while current + pd.DateOffset(months=train_months + test_months) <= end:
        train_start = current
        train_end = current + pd.DateOffset(months=train_months)
        test_start = train_end
        test_end = test_start + pd.DateOffset(months=test_months)

        windows.append({
            "train": df.loc[train_start:train_end],
            "test": df.loc[test_start:test_end]
        })
        current += pd.DateOffset(months=test_months)

    return windows

windows = walk_forward_windows(data["XOM"])
```

**Step operativo:**
1. Per ogni finestra, ottimizzare i parametri (es. soglia RSI, ATR multiplier) SOLO sul segmento `train`.
2. Applicare i parametri trovati al segmento `test` senza modificarli.
3. Aggregare le metriche (Sharpe, win rate, profit factor) SOLO dai risultati `test` di tutte le finestre.

---

### 12.9 Esecuzione del Monte Carlo sui Trade

```python
def run_monte_carlo(trade_log, n_simulations=10000):
    returns = trade_log["pnl_pct"].values
    results = []
    for _ in range(n_simulations):
        resampled = np.random.choice(returns, size=len(returns), replace=True)
        equity = np.cumprod(1 + resampled)
        drawdown = (equity - np.maximum.accumulate(equity)) / np.maximum.accumulate(equity)
        results.append(drawdown.min())

    return {
        "worst_case_5pct": np.percentile(results, 5),
        "median": np.percentile(results, 50),
        "best_case_95pct": np.percentile(results, 95)
    }
```

**Step operativo:** eseguire questa analisi sull'intero trade log aggregato dalla walk-forward analysis (non su un singolo backtest puntuale), per avere una stima robusta del drawdown atteso.

---

### 12.10 Paper Trading

**Step 1** — Deploy della stessa identica logica di segnale/uscita usata nel backtest su un conto paper (Alpaca paper trading, Binance testnet, ecc.), collegata al feed dati real-time del Passo 12.1.5.

**Step 2** — Loggare ogni trade con timestamp, prezzo di ingresso/uscita, motivazione di uscita (stop_loss/take_profit/time_stop/regime_stop), esattamente come nel backtest, per poter confrontare le metriche paper vs backtest.

**Step 3** — Durata minima: 4-6 settimane o almeno 30-50 trade eseguiti, il primo dei due che arriva per ultimo (in mercati poco volatili potrebbero servire più settimane per accumulare un campione statisticamente utile).

**Step 4** — Confrontare le metriche paper trading con quelle della walk-forward analysis (Sezione 12.8). Uno scostamento significativo (win rate paper molto più basso di quello di backtest) indica quasi sempre problemi di slippage/esecuzione non modellati correttamente, non un problema della logica di segnale.

---

### 12.11 Deployment Live (solo dopo checklist Sezione 10 superata)

**Step 1** — Iniziare con size ridotta (es. 25-50% della size calcolata dal position sizing) per le prime 2-4 settimane di capitale reale, anche se il paper trading è stato positivo — l'esecuzione con capitale reale introduce dinamiche psicologiche ed esecutive (es. rifiuti di ordine, latenza reale) non sempre visibili in paper trading.

**Step 2** — Monitorare le stesse metriche del paper trading (Sezione 12.10) su base continuativa, con un controllo settimanale.

**Step 3** — Scalare gradualmente alla size piena di position sizing solo dopo che le metriche live confermano quelle attese dalla walk-forward analysis, per almeno 4-6 settimane consecutive.

---

## 13. Prossimi Passi Suggeriti

1. Implementare il **Livello 1 (filtro di regime)** isolatamente e validarlo statisticamente prima di aggiungere il segnale di ingresso.
2. Backtestare su dati storici del settore energy che già conosci (riuso di infrastruttura Backtrader esistente).
3. Eseguire walk-forward + Monte Carlo prima di qualunque paper trading.
4. Solo dopo paper trading positivo per 4-6 settimane, passare a capitale reale minimo.

---

*Documento redatto come base tecnica di riferimento per lo sviluppo del progetto Mean Reversion Intraday. Da aggiornare man mano che vengono raccolti dati reali di backtest e paper trading.*# Mean Reversion Intraday — Documentazione Tecnica

**Versione:** 1.0
**Autore progetto:** Gagio
**Stack di riferimento:** Python 3.11+, Backtrader / vectorbt, pandas, TA-Lib

---

## 1. Introduzione e Obiettivo

Questo documento descrive in dettaglio la strategia **Mean Reversion Intraday**, la logica statistica che la sottende, l'implementazione tecnica, e — soprattutto — le tecniche di **ottimizzazione progressiva** per massimizzare il win rate mantenendo un risk/reward sostenibile.

L'obiettivo non è solo "avere ragione spesso" (alto win rate), ma avere ragione spesso **con un edge netto dopo costi**, evitando il problema classico: tanti piccoli trade vinti che vengono spazzati via da pochi trade grossi persi durante un trend forte.

---

## 2. Logica Teorica della Strategia

### 2.1 Il principio statistico

La mean reversion si basa sull'ipotesi che il prezzo di un asset, dopo una deviazione anomala rispetto alla sua media recente, tenda a tornare verso quella media nel breve termine. Questo accade per motivi di **microstruttura di mercato**:

- **Overreaction**: i trader retail e gli algoritmi di momentum a breve termine spingono il prezzo oltre il "fair value" temporaneo in risposta a flussi di ordini, non a nuova informazione fondamentale.
- **Liquidity provision**: i market maker e gli arbitraggisti intervengono per "correggere" la deviazione, fornendo liquidità nella direzione opposta al movimento estremo.
- **Mean-reverting noise**: su timeframe intraday, gran parte della varianza di prezzo è rumore microstrutturale (bid-ask bounce, ordini di grandi dimensioni eseguiti a tranche), non vero trend.

### 2.2 Quando NON funziona (condizione critica)

La mean reversion **fallisce sistematicamente** in presenza di:
- Trend direzionale forte (news reali, cambio di regime)
- Bassa liquidità (lo spread bid-ask "mangia" il piccolo edge)
- Eventi macro/earnings (la deviazione non è rumore, è repricing reale)

**Questo è il punto più importante dell'intero documento**: la strategia non deve mai operare "a prescindere". Deve operare solo quando esiste evidenza statistica che il regime di mercato attuale è mean-reverting. Questo si misura, non si assume.

---

## 3. Framework a 3 Livelli

Per ottimizzare il win rate in modo robusto (non overfittato), la strategia va strutturata su tre livelli indipendenti:

```
LIVELLO 1: Filtro di Regime (decide SE tradare)
    ↓
LIVELLO 2: Segnale di Ingresso (decide QUANDO entrare)
    ↓
LIVELLO 3: Gestione dell'Uscita (decide QUANDO uscire)
```

Il vero win rate elevato non nasce dal segnale di ingresso, ma dal **Livello 1**. Un buon filtro di regime elimina l'80% dei trade "cattivi" prima ancora che il segnale scatti.

---

## 4. Livello 1 — Filtro di Regime (il più importante)

### 4.1 Indicatori di regime

| Indicatore | Funzione | Soglia tipica |
|---|---|---|
| **ADX (Average Directional Index)** | Misura la forza del trend | Operare mean reversion solo se ADX < 20–25 |
| **Hurst Exponent** | Misura se la serie è mean-reverting (H<0.5), random walk (H=0.5) o trending (H>0.5) | Operare solo se H < 0.45 |
| **ATR relativo (ATR / prezzo)** | Filtra condizioni di volatilità anomala | Escludere se ATR% > 2 deviazioni standard dalla media |
| **Variance Ratio Test** | Test statistico di mean reversion vs random walk | p-value < 0.05 conferma mean reversion |

### 4.2 Implementazione del filtro ADX + Hurst

```python
import numpy as np
import pandas as pd

def hurst_exponent(price_series, max_lag=100):
    """Calcola l'esponente di Hurst per determinare il regime."""
    lags = range(2, max_lag)
    tau = [np.std(np.subtract(price_series[lag:], price_series[:-lag]))
           for lag in lags]
    poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
    return poly[0] * 2.0

def is_mean_reverting_regime(df, adx_threshold=22, hurst_threshold=0.45):
    """
    df deve contenere colonne: 'high', 'low', 'close'
    Ritorna una serie booleana: True = regime adatto a mean reversion
    """
    adx = calculate_adx(df, period=14)  # usare TA-Lib: talib.ADX
    hurst = hurst_exponent(df['close'].values[-252:])  # ultimi ~252 periodi

    regime_ok = (adx < adx_threshold) and (hurst < hurst_threshold)
    return regime_ok
```

> **Nota tecnica:** l'Hurst Exponent va ricalcolato periodicamente (es. ogni 20-50 barre), non ad ogni tick — è un indicatore di regime, non di ingresso.

### 4.3 Filtro aggiuntivo: esclusione eventi

Escludere sempre:
- Giorni di earnings/report trimestrali (per equities)
- Orari di rilascio dati macro (per FX/futures — NFP, CPI, FOMC)
- Le prime/ultime 15-30 minuti di sessione (volatilità anomala di apertura/chiusura)

---

## 5. Livello 2 — Segnale di Ingresso

### 5.1 Indicatori combinati (non uno solo)

Usare un **singolo oscillatore non basta** per un win rate elevato: genera troppi falsi segnali. La combinazione di 2-3 conferme indipendenti aumenta drasticamente la qualità del segnale.

| Indicatore | Parametro base | Ruolo |
|---|---|---|
| **RSI** | Periodo 14, soglie 30/70 | Identifica ipercomprato/ipervenduto |
| **Bollinger Bands** | 20 periodi, 2 deviazioni standard | Identifica deviazione statistica dal prezzo medio |
| **Z-score del prezzo** | Rolling window 20-50 periodi | Quantifica la deviazione in termini standardizzati |
| **Volume spike** | Volume > 1.5x media mobile volume | Conferma che la deviazione è "reale" (non rumore a basso volume) |

### 5.2 Regola di ingresso ottimizzata (esempio long)

```python
def entry_signal_long(df, rsi_period=14, bb_period=20, bb_std=2, z_threshold=-2):
    rsi = talib.RSI(df['close'], timeperiod=rsi_period)
    upper, middle, lower = talib.BBANDS(df['close'], timeperiod=bb_period, 
                                          nbdevup=bb_std, nbdevdn=bb_std)
    rolling_mean = df['close'].rolling(bb_period).mean()
    rolling_std = df['close'].rolling(bb_period).std()
    z_score = (df['close'] - rolling_mean) / rolling_std

    volume_confirm = df['volume'] > (df['volume'].rolling(20).mean() * 1.5)

    # Tripla conferma: RSI + Bollinger + Z-score, con volume come filtro extra
    condition = (
        (rsi < 30) &
        (df['close'] < lower) &
        (z_score < z_threshold) &
        volume_confirm
    )
    return condition
```

**Perché la tripla conferma aumenta il win rate:** ogni indicatore da solo genera falsi positivi in scenari diversi (RSI soffre di divergenze in trend, Bollinger Bands si allargano in alta volatilità, lo z-score da solo ignora il contesto di volume). Richiedendo l'allineamento di più segnali indipendenti, si filtrano statisticamente i casi ambigui — al costo di una minore frequenza di trade (trade-off accettabile: **meglio meno trade con edge reale che tanti trade mediocri**).

### 5.3 Micro-conferma di prezzo (price action)

Aggiungere una conferma di price action riduce ulteriormente i falsi segnali:
- **Candela di rigetto** (pin bar / hammer) alla banda inferiore
- **Divergenza RSI positiva** (prezzo fa un minimo più basso, RSI fa un minimo più alto)

Questo è opzionale ma aumenta tipicamente il win rate del 5-10% a scapito della frequenza.

---

## 6. Livello 3 — Gestione dell'Uscita (dove si vince o si perde davvero)

### 6.1 Il principio chiave

Il win rate elevato della mean reversion (60-80%) è **strutturalmente legato** a come si gestisce l'uscita. Un target di profitto piccolo e uno stop loss stretto ma non troppo generano molte piccole vincite — ma se lo stop è troppo stretto, si viene bruciati dal rumore prima del reversal.

### 6.2 Regole di uscita ottimizzate

| Componente | Regola | Razionale |
|---|---|---|
| **Take Profit** | Ritorno alla media mobile (banda centrale Bollinger) o z-score → 0 | Non fissare un target percentuale arbitrario: uscire quando la mean reversion è "completata" statisticamente |
| **Stop Loss** | 1.5–2× ATR dal prezzo di ingresso | Adattivo alla volatilità corrente, non un valore fisso in % |
| **Time Stop** | Uscita forzata dopo N barre (es. 20-30 barre a 5 min) se il target non è raggiunto | Evita di restare intrappolati se il regime cambia durante il trade |
| **Stop di regime** | Se ADX supera la soglia durante il trade → uscita immediata | Il mercato è passato da mean-reverting a trending: l'edge non esiste più |

### 6.3 Implementazione dello stop di regime (fondamentale)

```python
def check_regime_stop(current_adx, adx_threshold=25):
    """Uscita di emergenza se il regime cambia durante il trade aperto."""
    return current_adx > adx_threshold
```

Questo singolo controllo è spesso la differenza tra una strategia mean reversion profittevole e una che perde tutto in un trend improvviso — è il meccanismo che protegge dal fallimento strutturale descritto al punto 2.2.

---

## 7. Position Sizing e Risk Management

### 7.1 Sizing adattivo alla volatilità

```python
def position_size(account_equity, risk_per_trade_pct, atr, stop_multiplier=1.5):
    """
    Calcola la size in base al rischio fisso per trade e alla volatilità corrente.
    """
    risk_amount = account_equity * (risk_per_trade_pct / 100)
    stop_distance = atr * stop_multiplier
    size = risk_amount / stop_distance
    return size
```

- **Rischio per trade consigliato:** 0.5–1% del capitale (mai oltre il 2%)
- **Correlazione tra posizioni:** se si opera su più asset contemporaneamente, limitare l'esposizione aggregata a settori/asset correlati (es. non aprire 5 posizioni mean reversion su titoli energy nello stesso momento — è lo stesso bet ripetuto 5 volte, non 5 bet indipendenti)

### 7.2 Kelly frazionato per lo scaling

Una volta che la strategia ha uno storico di almeno 100+ trade fuori-sample:

```python
def fractional_kelly(win_rate, avg_win, avg_loss, fraction=0.25):
    """
    Kelly Criterion frazionato (usare 1/4 o 1/2 Kelly, mai Kelly pieno).
    """
    b = avg_win / avg_loss
    kelly_pct = win_rate - ((1 - win_rate) / b)
    return max(0, kelly_pct * fraction)
```

**Importante:** Kelly pieno è troppo aggressivo e genera drawdown insostenibili emotivamente e finanziariamente. Usare sempre una frazione (1/4 – 1/2 Kelly).

---

## 8. Processo di Ottimizzazione (senza cadere nell'overfitting)

Questo è il punto dove la maggior parte dei trader retail — incluse esperienze pregresse su pairs trading — fallisce: backtest ottimo, live negativo. Ecco il processo corretto.

### 8.1 Walk-Forward Analysis (obbligatorio)

```
[Dati Storici Totali]
   |
   ├── Finestra 1: Train (6 mesi) → Test (1 mese)
   ├── Finestra 2: Train (6 mesi, shiftata) → Test (1 mese)
   ├── Finestra 3: ...
   └── Finestra N: ...

Media risultati SOLO sulle finestre di TEST (mai sul train)
```

Mai ottimizzare i parametri (RSI period, soglie Bollinger, ATR multiplier) su tutto il dataset e poi testare sullo stesso periodo: è il motivo #1 per cui un backtest "bello" diventa PNL negativo live.

### 8.2 Monte Carlo sulla sequenza dei trade

Dopo aver ottenuto una lista di trade (anche solo 50-100), applicare un resampling Monte Carlo (bootstrap) per stimare la distribuzione realistica di drawdown, non fidarsi del singolo drawdown storico osservato:

```python
import numpy as np

def monte_carlo_drawdown(trade_returns, n_simulations=10000):
    max_drawdowns = []
    for _ in range(n_simulations):
        resampled = np.random.choice(trade_returns, size=len(trade_returns), replace=True)
        equity_curve = np.cumprod(1 + resampled)
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - running_max) / running_max
        max_drawdowns.append(drawdown.min())
    return np.percentile(max_drawdowns, [5, 50, 95])  # worst-case, mediano, best-case
```

Se il 95° percentile di drawdown simulato è insostenibile per il tuo capitale/psicologia, la strategia — per quanto bella nel backtest puntuale — non è pronta.

### 8.3 Costi di transazione realistici (non opzionali)

Nel backtest, includere **sempre**:
- Commissioni del broker/exchange
- Slippage stimato (tipicamente 1-3 tick su strumenti liquidi, di più su illiquidi)
- Spread bid-ask al momento dell'ingresso/uscita

```python
# Esempio Backtrader: impostare commissione e slippage realistici
cerebro.broker.setcommission(commission=0.001)  # 0.1% per lato
cerebro.broker.set_slippage_perc(perc=0.0005)   # 0.05% di slippage stimato
```

### 8.4 Metriche da monitorare (oltre al win rate)

Il win rate da solo è **fuorviante**. Monitorare sempre insieme:

| Metrica | Perché serve |
|---|---|
| **Profit Factor** (lordo vinto / lordo perso) | Deve essere > 1.3-1.5 per avere margine dopo costi reali |
| **Sharpe Ratio** | Rendimento aggiustato per volatilità |
| **Sortino Ratio** | Come Sharpe ma penalizza solo la volatilità negativa (più rilevante per mean reversion) |
| **Expectancy** = (Win% × Avg Win) − (Loss% × Avg Loss) | Il vero indicatore di edge per trade |
| **Max Drawdown** e durata del drawdown | Sostenibilità psicologica e di capitale |

Un win rate del 75% con expectancy negativa (stop loss enormi occasionali) è una strategia perdente camuffata da "vincente".

---

## 9. Setup Tecnico Consigliato

### 9.1 Stack tecnologico

```
Linguaggio:       Python 3.11+
Backtesting:      Backtrader (flessibile, buon supporto intraday) 
                  o vectorbt (più veloce per ottimizzazioni su griglie ampie)
Indicatori:       TA-Lib (RSI, ADX, Bollinger, ATR nativi e ottimizzati in C)
Dati storici:     Polygon.io / Alpaca (equities USA), CCXT (crypto)
Dati real-time:   WebSocket feed del broker/exchange scelto
Esecuzione live:  Alpaca API (equities) o CCXT (crypto)
Statistica:       statsmodels (Variance Ratio Test), numpy/scipy (Hurst, Monte Carlo)
```

### 9.2 Architettura del sistema

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Data Feed       │ --> │  Regime Filter    │ --> │  Signal Engine   │
│  (real-time OHLCV│     │  (ADX, Hurst)     │     │  (RSI+BB+Vol)    │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                             │
                         ┌──────────────────┐               ▼
                         │  Risk Manager     │ <──── Segnale valido
                         │  (sizing, stops)  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Execution Layer  │
                         │  (broker/exchange │
                         │   API)             │
                         └──────────────────┘
```

### 9.3 Mercati e timeframe consigliati per iniziare

Vista la tua esperienza pregressa (Python, Backtrader, energy sector):
- **Timeframe:** 5-15 minuti (compromesso tra numero di segnali e rumore statistico)
- **Asset:** iniziare su 5-10 titoli liquidi dello stesso settore che già conosci, poi espandere
- **Sessione:** evitare le prime/ultime 30 minuti di mercato regolare

---

## 10. Checklist Pre-Live (da rispettare sempre)

- [ ] Walk-forward analysis completata su almeno 3-4 finestre out-of-sample
- [ ] Monte Carlo su sequenza trade eseguito, drawdown al 95° percentile accettabile
- [ ] Costi di transazione realistici inclusi nel backtest (commissioni + slippage + spread)
- [ ] Filtro di regime (ADX/Hurst) implementato e testato separatamente dal segnale
- [ ] Stop di regime attivo (uscita se il mercato passa da mean-reverting a trending)
- [ ] Position sizing basato sul rischio, non su size fissa
- [ ] Paper trading di almeno 4-6 settimane con esecuzione reale (non solo simulata) prima di capitale vero
- [ ] Expectancy per trade calcolata e positiva anche includendo lo scenario peggiore Monte Carlo
- [ ] Nessun parametro ottimizzato sull'intero dataset (solo su finestre di train)

---

## 11. Errori Comuni da Evitare (riassunto critico)

1. **Ottimizzare i parametri su tutto lo storico** → overfitting garantito, fallimento live.
2. **Ignorare il filtro di regime** → la strategia opera anche in trend forte e perde tutto ciò che ha guadagnato.
3. **Stop loss fisso in %** invece che basato su ATR → non si adatta alla volatilità corrente.
4. **Guardare solo il win rate** senza controllare expectancy e profit factor.
5. **Backtest senza costi di transazione realistici** → il problema che probabilmente hai già vissuto con il pairs trading.
6. **Correlazione ignorata tra posizioni multiple** → si crede di essere diversificati ma si è esposti a un solo rischio ripetuto.
7. **Nessun time stop** → capitale bloccato in trade "morti" che non convergono né vanno in stop.

---

## 12. Guida Operativa Step-by-Step all'Implementazione

Questa sezione traduce tutto quanto descritto finora in una sequenza operativa concreta, dal fetch dei dati fino al deployment live. Ogni step include cosa fare, perché, e codice di riferimento.

---

### 12.1 Fetch Dati

**Obiettivo:** ottenere dati OHLCV puliti, allineati e privi di bias, sia storici (per backtest) sia real-time (per il live).

#### Passo 1 — Definire l'universo di asset
Selezionare 5-10 titoli/asset liquidi, idealmente dello stesso settore (riuso della tua esperienza su energy sector), per poter poi applicare filtri di correlazione.

```python
universe = ["XOM", "CVX", "COP", "SLB", "EOG"]  # esempio energy sector
```

**Perché:** partire da un universo ristretto e noto permette di validare la logica prima di scalare, e riduce il rischio di survivorship bias se si sceglie l'universo *prima* di guardare le performance storiche (mai selezionare i titoli "perché sono andati bene" — è survivorship bias puro).

#### Passo 2 — Fetch dati storici (per backtest)

```python
import alpaca_trade_api as tradeapi
import pandas as pd

api = tradeapi.REST(API_KEY, API_SECRET, base_url="https://paper-api.alpaca.markets")

def fetch_historical_data(symbol, timeframe="5Min", start="2022-01-01", end="2024-12-31"):
    bars = api.get_bars(symbol, timeframe, start=start, end=end).df
    bars = bars[["open", "high", "low", "close", "volume"]]
    return bars

data = {sym: fetch_historical_data(sym) for sym in universe}
```

**Perché Alpaca (o Polygon):** forniscono dati intraday storici già aggiustati per split/dividendi (adjusted), evitando gap artificiali nei prezzi che genererebbero falsi segnali di mean reversion.

#### Passo 3 — Pulizia e validazione dei dati

```python
def clean_data(df):
    df = df[~df.index.duplicated(keep="first")]      # rimuove timestamp duplicati
    df = df.dropna()                                    # rimuove barre incomplete
    df = df[(df["volume"] > 0)]                          # rimuove barre a volume zero (mercato chiuso/halted)
    df = df.sort_index()
    return df

data = {sym: clean_data(df) for sym, df in data.items()}
```

**Perché:** dati sporchi (gap, duplicati, barre a volume zero per halt di trading) generano segnali fantasma — z-score e RSI calcolati su dati corrotti producono falsi ingressi.

#### Passo 4 — Allineamento temporale multi-asset

```python
def align_data(data_dict):
    common_index = None
    for df in data_dict.values():
        common_index = df.index if common_index is None else common_index.intersection(df.index)
    return {sym: df.loc[common_index] for sym, df in data_dict.items()}

data = align_data(data)
```

**Perché:** se si opera su più asset in parallelo per il risk management aggregato (Sezione 7.1), serve che tutte le serie abbiano gli stessi timestamp, altrimenti i calcoli di correlazione ed esposizione aggregata sono falsati.

#### Passo 5 — Setup del fetch real-time (per paper/live trading)

```python
from alpaca_trade_api.stream import Stream

stream = Stream(API_KEY, API_SECRET, base_url="https://paper-api.alpaca.markets")

async def on_bar(bar):
    # bar contiene: symbol, open, high, low, close, volume, timestamp
    update_live_dataframe(bar)

for sym in universe:
    stream.subscribe_bars(on_bar, sym)

stream.run()
```

**Perché il websocket e non il polling:** il polling (richieste REST ripetute) introduce latenza variabile e rischia rate-limit da parte del broker; il websocket garantisce dati in tempo reale con overhead minimo, essenziale anche per una strategia non-HFT come questa.

---

### 12.2 Creazione Indicatori

Ogni indicatore va costruito come modulo indipendente e testato singolarmente prima di essere combinato nel segnale finale.

#### Indicatore 1 — ADX (Average Directional Index)
**Cos'è:** misura la forza di un trend (non la direzione), su una scala 0-100.
**Perché lo usiamo:** è il primo filtro di regime (Sezione 4). Se l'ADX è alto, il mercato sta trendando e la mean reversion va disattivata.

```python
import talib

def add_adx(df, period=14):
    df["adx"] = talib.ADX(df["high"], df["low"], df["close"], timeperiod=period)
    return df
```

#### Indicatore 2 — Hurst Exponent
**Cos'è:** misura statistica che classifica una serie storica come mean-reverting (H<0.5), random walk (H≈0.5) o trending/persistente (H>0.5).
**Perché lo usiamo:** l'ADX misura la forza del trend *attuale*, ma l'Hurst conferma la natura statistica *strutturale* della serie in una finestra più ampia — le due misure insieme riducono i falsi positivi del filtro di regime.

```python
import numpy as np

def add_hurst(df, window=252, min_lag=2, max_lag=100):
    def hurst(ts):
        lags = range(min_lag, max_lag)
        tau = [np.std(np.subtract(ts[lag:], ts[:-lag])) for lag in lags]
        poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
        return poly[0] * 2.0

    df["hurst"] = df["close"].rolling(window).apply(lambda x: hurst(x.values), raw=False)
    return df
```

#### Indicatore 3 — RSI (Relative Strength Index)
**Cos'è:** oscillatore momentum 0-100 che misura la velocità e l'ampiezza dei movimenti di prezzo recenti.
**Perché lo usiamo:** è il primo segnale di ingresso (Sezione 5) — identifica condizioni di ipercomprato (>70) e ipervenduto (<30), cioè le deviazioni che la strategia vuole sfruttare.

```python
def add_rsi(df, period=14):
    df["rsi"] = talib.RSI(df["close"], timeperiod=period)
    return df
```

#### Indicatore 4 — Bollinger Bands
**Cos'è:** bande di deviazione standard (tipicamente ±2σ) attorno a una media mobile.
**Perché lo usiamo:** quantifica *quanto* il prezzo si è allontanato dalla media in termini statistici assoluti (non solo di momentum come l'RSI) — è la seconda conferma indipendente richiesta dal segnale.

```python
def add_bollinger(df, period=20, std_dev=2):
    upper, middle, lower = talib.BBANDS(df["close"], timeperiod=period,
                                          nbdevup=std_dev, nbdevdn=std_dev)
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = upper, middle, lower
    return df
```

#### Indicatore 5 — Z-score rolling
**Cos'è:** normalizzazione della deviazione del prezzo dalla media, espressa in numero di deviazioni standard.
**Perché lo usiamo:** rende la deviazione confrontabile tra asset diversi (un titolo a 10$ e uno a 500$ non sono comparabili in termini assoluti) ed è la terza conferma quantitativa, oltre a essere il criterio di uscita (target = z-score → 0).

```python
def add_zscore(df, window=20):
    rolling_mean = df["close"].rolling(window).mean()
    rolling_std = df["close"].rolling(window).std()
    df["zscore"] = (df["close"] - rolling_mean) / rolling_std
    return df
```

#### Indicatore 6 — Volume Filter
**Cos'è:** confronto tra volume corrente e media mobile del volume.
**Perché lo usiamo:** una deviazione di prezzo su basso volume è spesso rumore/illiquidità, non una vera overreaction del mercato — il filtro volume separa i segnali "reali" da quelli statisticamente deboli.

```python
def add_volume_filter(df, window=20, multiplier=1.5):
    df["vol_avg"] = df["volume"].rolling(window).mean()
    df["vol_confirm"] = df["volume"] > (df["vol_avg"] * multiplier)
    return df
```

#### Indicatore 7 — ATR (Average True Range)
**Cos'è:** misura la volatilità media recente in termini assoluti di prezzo.
**Perché lo usiamo:** non è un segnale di ingresso ma è essenziale per stop loss adattivi (Sezione 6.2) e per il position sizing (Sezione 7.1) — evita stop fissi in % che non si adattano alla volatilità corrente dell'asset.

```python
def add_atr(df, period=14):
    df["atr"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=period)
    return df
```

#### Pipeline completa di creazione indicatori

```python
def build_all_indicators(df):
    df = add_adx(df)
    df = add_hurst(df)
    df = add_rsi(df)
    df = add_bollinger(df)
    df = add_zscore(df)
    df = add_volume_filter(df)
    df = add_atr(df)
    return df.dropna()  # rimuove le righe iniziali senza indicatori calcolabili (warm-up period)

data = {sym: build_all_indicators(df) for sym, df in data.items()}
```

---

### 12.3 Costruzione del Filtro di Regime

**Obiettivo:** produrre un flag booleano `regime_ok` che autorizza o blocca la generazione di segnali.

```python
def apply_regime_filter(df, adx_threshold=22, hurst_threshold=0.45):
    df["regime_ok"] = (df["adx"] < adx_threshold) & (df["hurst"] < hurst_threshold)
    return df
```

**Step di validazione (obbligatorio prima di proseguire):**
1. Calcolare la percentuale di tempo in cui `regime_ok = True` sui dati storici — se è troppo bassa (<10%) il filtro è troppo restrittivo, se troppo alta (>70%) probabilmente non sta filtrando nulla di utile.
2. Verificare a occhio (plot) che i periodi con `regime_ok = True` corrispondano visivamente a fasi laterali/range-bound del prezzo, e `regime_ok = False` a trend evidenti.

---

### 12.4 Costruzione del Segnale di Ingresso

```python
def generate_entry_signals(df, z_threshold=2):
    long_signal = (
        df["regime_ok"] &
        (df["rsi"] < 30) &
        (df["close"] < df["bb_lower"]) &
        (df["zscore"] < -z_threshold) &
        df["vol_confirm"]
    )

    short_signal = (
        df["regime_ok"] &
        (df["rsi"] > 70) &
        (df["close"] > df["bb_upper"]) &
        (df["zscore"] > z_threshold) &
        df["vol_confirm"]
    )

    df["long_entry"] = long_signal
    df["short_entry"] = short_signal
    return df
```

**Step di validazione:** contare il numero di segnali generati su tutto il periodo storico. Se sono troppo pochi (<30-50 in totale sull'intero storico) il campione non sarà statisticamente affidabile per validare la strategia — allargare l'universo di asset o allentare leggermente le soglie (con cautela, senza fare curve-fitting).

---

### 12.5 Costruzione della Logica di Uscita

```python
def simulate_exit(df, entry_idx, direction, atr_multiplier=1.5, max_bars=25, adx_stop=25):
    entry_price = df["close"].iloc[entry_idx]
    entry_atr = df["atr"].iloc[entry_idx]
    stop_distance = entry_atr * atr_multiplier

    stop_price = entry_price - stop_distance if direction == "long" else entry_price + stop_distance

    for i in range(entry_idx + 1, min(entry_idx + max_bars, len(df))):
        row = df.iloc[i]

        # Stop di regime: uscita se il trend riprende forza
        if row["adx"] > adx_stop:
            return row["close"], i, "regime_stop"

        # Stop loss classico
        if direction == "long" and row["low"] <= stop_price:
            return stop_price, i, "stop_loss"
        if direction == "short" and row["high"] >= stop_price:
            return stop_price, i, "stop_loss"

        # Take profit: ritorno alla media (z-score torna verso 0)
        if direction == "long" and row["zscore"] >= 0:
            return row["close"], i, "take_profit"
        if direction == "short" and row["zscore"] <= 0:
            return row["close"], i, "take_profit"

    # Time stop: nessuna condizione soddisfatta entro max_bars
    last_row = df.iloc[min(entry_idx + max_bars, len(df) - 1)]
    return last_row["close"], entry_idx + max_bars, "time_stop"
```

**Perché ogni componente:**
- **Stop di regime** (già descritto in 6.3): priorità massima, protegge dal fallimento strutturale della strategia.
- **Stop loss su ATR**: adattivo alla volatilità reale dell'asset in quel momento specifico.
- **Take profit su z-score**: esce quando la mean reversion si è statisticamente "completata", non su un target arbitrario in %.
- **Time stop**: libera capitale se il trade non converge né va in stop — evita immobilizzo prolungato.

---

### 12.6 Costruzione del Position Sizing

```python
def calculate_position_size(account_equity, risk_pct, entry_price, stop_price):
    risk_amount = account_equity * (risk_pct / 100)
    per_share_risk = abs(entry_price - stop_price)
    shares = int(risk_amount / per_share_risk)
    return shares
```

**Step operativo:** integrare questa funzione nel motore di backtest in modo che ogni trade simulato usi la size correttamente calcolata, non una size fissa — un backtest a size fissa sovrastima o sottostima sistematicamente il rischio reale.

---

### 12.7 Assemblaggio del Motore di Backtest (Backtrader)

```python
import backtrader as bt

class MeanReversionStrategy(bt.Strategy):
    params = dict(
        rsi_period=14, bb_period=20, bb_std=2,
        adx_period=14, atr_period=14,
        adx_threshold=22, z_threshold=2,
        risk_pct=1.0, atr_multiplier=1.5, max_bars=25
    )

    def __init__(self):
        self.rsi = bt.ind.RSI(period=self.p.rsi_period)
        self.bb = bt.ind.BollingerBands(period=self.p.bb_period, devfactor=self.p.bb_std)
        self.adx = bt.ind.ADX(period=self.p.adx_period)
        self.atr = bt.ind.ATR(period=self.p.atr_period)
        self.bar_executed = 0

    def next(self):
        if self.position:
            # Logica di uscita (stop di regime, stop loss, take profit, time stop)
            if self.adx[0] > 25 or (len(self) - self.bar_executed) > self.p.max_bars:
                self.close()
            return

        if self.adx[0] < self.p.adx_threshold:
            if self.rsi[0] < 30 and self.data.close[0] < self.bb.lines.bot[0]:
                size = self.calculate_size()
                self.buy(size=size)
                self.bar_executed = len(self)
            elif self.rsi[0] > 70 and self.data.close[0] > self.bb.lines.top[0]:
                size = self.calculate_size()
                self.sell(size=size)
                self.bar_executed = len(self)

    def calculate_size(self):
        risk_amount = self.broker.getvalue() * (self.p.risk_pct / 100)
        stop_distance = self.atr[0] * self.p.atr_multiplier
        return int(risk_amount / stop_distance)
```

**Step operativo:**
1. Caricare i dati puliti nel `cerebro` di Backtrader con `bt.feeds.PandasData`.
2. Impostare commissioni e slippage realistici (vedi Sezione 8.3).
3. Eseguire un primo backtest su un solo asset per validare che la logica non abbia bug prima di scalare all'intero universo.

---

### 12.8 Esecuzione della Walk-Forward Analysis

```python
def walk_forward_windows(df, train_months=6, test_months=1):
    windows = []
    start = df.index.min()
    end = df.index.max()
    current = start

    while current + pd.DateOffset(months=train_months + test_months) <= end:
        train_start = current
        train_end = current + pd.DateOffset(months=train_months)
        test_start = train_end
        test_end = test_start + pd.DateOffset(months=test_months)

        windows.append({
            "train": df.loc[train_start:train_end],
            "test": df.loc[test_start:test_end]
        })
        current += pd.DateOffset(months=test_months)

    return windows

windows = walk_forward_windows(data["XOM"])
```

**Step operativo:**
1. Per ogni finestra, ottimizzare i parametri (es. soglia RSI, ATR multiplier) SOLO sul segmento `train`.
2. Applicare i parametri trovati al segmento `test` senza modificarli.
3. Aggregare le metriche (Sharpe, win rate, profit factor) SOLO dai risultati `test` di tutte le finestre.

---

### 12.9 Esecuzione del Monte Carlo sui Trade

```python
def run_monte_carlo(trade_log, n_simulations=10000):
    returns = trade_log["pnl_pct"].values
    results = []
    for _ in range(n_simulations):
        resampled = np.random.choice(returns, size=len(returns), replace=True)
        equity = np.cumprod(1 + resampled)
        drawdown = (equity - np.maximum.accumulate(equity)) / np.maximum.accumulate(equity)
        results.append(drawdown.min())

    return {
        "worst_case_5pct": np.percentile(results, 5),
        "median": np.percentile(results, 50),
        "best_case_95pct": np.percentile(results, 95)
    }
```

**Step operativo:** eseguire questa analisi sull'intero trade log aggregato dalla walk-forward analysis (non su un singolo backtest puntuale), per avere una stima robusta del drawdown atteso.

---

### 12.10 Paper Trading

**Step 1** — Deploy della stessa identica logica di segnale/uscita usata nel backtest su un conto paper (Alpaca paper trading, Binance testnet, ecc.), collegata al feed dati real-time del Passo 12.1.5.

**Step 2** — Loggare ogni trade con timestamp, prezzo di ingresso/uscita, motivazione di uscita (stop_loss/take_profit/time_stop/regime_stop), esattamente come nel backtest, per poter confrontare le metriche paper vs backtest.

**Step 3** — Durata minima: 4-6 settimane o almeno 30-50 trade eseguiti, il primo dei due che arriva per ultimo (in mercati poco volatili potrebbero servire più settimane per accumulare un campione statisticamente utile).

**Step 4** — Confrontare le metriche paper trading con quelle della walk-forward analysis (Sezione 12.8). Uno scostamento significativo (win rate paper molto più basso di quello di backtest) indica quasi sempre problemi di slippage/esecuzione non modellati correttamente, non un problema della logica di segnale.

---

### 12.11 Deployment Live (solo dopo checklist Sezione 10 superata)

**Step 1** — Iniziare con size ridotta (es. 25-50% della size calcolata dal position sizing) per le prime 2-4 settimane di capitale reale, anche se il paper trading è stato positivo — l'esecuzione con capitale reale introduce dinamiche psicologiche ed esecutive (es. rifiuti di ordine, latenza reale) non sempre visibili in paper trading.

**Step 2** — Monitorare le stesse metriche del paper trading (Sezione 12.10) su base continuativa, con un controllo settimanale.

**Step 3** — Scalare gradualmente alla size piena di position sizing solo dopo che le metriche live confermano quelle attese dalla walk-forward analysis, per almeno 4-6 settimane consecutive.

---

## 13. Prossimi Passi Suggeriti

1. Implementare il **Livello 1 (filtro di regime)** isolatamente e validarlo statisticamente prima di aggiungere il segnale di ingresso.
2. Backtestare su dati storici del settore energy che già conosci (riuso di infrastruttura Backtrader esistente).
3. Eseguire walk-forward + Monte Carlo prima di qualunque paper trading.
4. Solo dopo paper trading positivo per 4-6 settimane, passare a capitale reale minimo.

---

*Documento redatto come base tecnica di riferimento per lo sviluppo del progetto Mean Reversion Intraday. Da aggiornare man mano che vengono raccolti dati reali di backtest e paper trading.*