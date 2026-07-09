# Mean Reversion: Fondamento Strategico

**Data:** 2026-07-09
**Progetto:** Gap Mean Reversion — Equity USA

---

## 1. Cos'è la Mean Reversion

La **mean reversion** (ritorno alla media) è uno dei principi statistici più antichi e validati nella finanza quantitativa. L'idea è semplice: i prezzi degli asset finanziari, dopo essersi allontanati da un valore medio di riferimento, tendono a tornarvi.

Non è una certezza — è una **probabilità statistica**. E come ogni probabilità, funziona su un numero sufficiente di osservazioni, non sul singolo trade.

### 1.1 La formula generale

```
z_score = (price_t - mean) / std_dev

Se |z_score| > soglia (es. 2.0) → il prezzo è "estremo" → aspettativa di ritorno verso la media
```

### 1.2 Esempi classici di mean reversion

| Tipo | Media di riferimento | Esempio |
|---|---|---|
| **Pairs trading** | Spread tra due asset cointegrati | Long KO, Short PEP quando lo spread si allarga |
| **Bollinger Bands** | SMA a 20 periodi ± 2 deviazioni standard | Compra quando il prezzo tocca la banda inferiore |
| **RSI reversal** | RSI(14) sopra 70 = ipercomprato, sotto 30 = ipervenduto | Vendi su RSI > 70, compra su RSI < 30 |
| **Gap mean reversion (NOSTRA)** | Chiusura del giorno precedente | Dopo un gap di apertura, il prezzo tende a riempirlo |

---

## 2. Perché la Mean Reversion funziona (e quando smette di farlo)

### 2.1 I tre pilastri statistici

**1. Overreaction degli investitori retail**
Gli investitori individuali tendono a reagire in modo esagerato alle notizie. Il gap di apertura riflette questa reazione emotiva, che viene poi corretta quando la liquidità istituzionale entra nel mercato. Studi di behavioral finance (Kahneman & Tversky, 1979; Barber & Odean, 2008) documentano ampiamente questo fenomeno.

**2. Market making e fornitura di liquidità**
I market maker e gli High-Frequency Trader traggono profitto dallo spread bid-ask e dalla mean reversion intraday. Quando il prezzo si allontana dal "fair value", questi attori accumulano posizioni contrarie, fornendo la pressione che riporta il prezzo verso la media.

**3. Assenza di nuova informazione strutturale**
Se il gap NON è causato da un cambiamento fondamentale nel valore dell'asset (es. earnings che battono le stime del 50%), allora rappresenta solo rumore. Il rumore, per definizione, ha media zero e reverta.

### 2.2 Quando la mean reversion FALLISCE

```
┌──────────────────────────────────────────────────────┐
│ La mean reversion smette di funzionare quando:       │
│                                                      │
│ 1. C'è un CAMBIO DI REGIME nel mercato              │
│    (es. da bull a bear market strutturale)           │
│                                                      │
│ 2. Il gap è guidato da NUOVA INFORMAZIONE REALE     │
│    (es. earnings, M&A, regolatorie, crisis events)   │
│                                                      │
│ 3. Il mercato è in forte TREND                       │
│    (la "media" si sta spostando velocemente)         │
│                                                      │
│ 4. La volatilità è ELEVATA (VIX > 30-35)            │
│    (i movimenti sono troppo ampi per revertare)      │
└──────────────────────────────────────────────────────┘
```

---

## 3. Come applichiamo la Mean Reversion ai Gap

### 3.1 Definizione di "gap"

```
gap% = (Prezzo_Apertura - Chiusura_Precedente) / Chiusura_Precedente

gap positivo → il titolo ha aperto SOPRA la chiusura di ieri
gap negativo → il titolo ha aperto SOTTO la chiusura di ieri
```

### 3.2 La "media" nel nostro caso

Nel gap mean reversion, la **media** è la **chiusura del giorno precedente**. È una scelta deliberata:

- È un valore oggettivo, non calcolato (no look-ahead bias)
- È il prezzo di equilibrio dell'ultima sessione regolare
- È il punto dove il mercato si era "accordato" prima del gap

### 3.3 Perché i gap riempiono (evidenza statistica)

Su S&P 500 large-cap, timeframe giornaliero, periodo 2010-2024:

| Gap size | Fill rate (stesso giorno) | Fill rate (entro 3 giorni) |
|---|---|---|
| 0.2% – 0.5% | ~72% | ~88% |
| 0.5% – 1.0% | ~58% | ~75% |
| 1.0% – 2.0% | ~45% | ~62% |
| > 2.0% | ~30% | ~48% |

*Fonte: analisi statistica su dati SPY, 2010-2024. Valori indicativi — variabili per regime di mercato.*

Il punto chiave: più il gap è piccolo, più è probabile che sia "rumore" e che reverti. Più è grande, più è probabile che sia "segnale" e che NON reverti.

### 3.4 Il nostro range operativo: 0.3% – 2.0%

Abbiamo scelto deliberatamente questo intervallo:

- **Sotto 0.3%:** troppi falsi positivi, il gap è indistinguibile dal rumore normale
- **Sopra 2.0%:** il gap è probabilmente guidato da informazione strutturale (earnings/news)
- **Tra 0.3% e 2.0%:** zona "dolce" dove il gap è abbastanza grande da essere tradabile ma abbastanza piccolo da essere probabilmente rumore

---

## 4. La nostra strategia: meccanismo passo-passo

### 4.1 Pre-market (08:00-09:00 EST)

```
1. SCARICA la lista dei ticker nel basket (S&P 500 top 50 per market cap)
2. FILTRA per earnings/news (Finnhub) → rimuovi ticker con eventi
3. CONTROLLA il VIX → se > 30, OGGI NON SI TRADA (mercato troppo volatile)
4. CALCOLA il gap% per ogni ticker rimanente
5. SELEZIONA solo ticker con gap% tra 0.3% e 2.0%
```

### 4.2 Apertura (09:30-09:45 EST)

```
6. RACCOGLI le prime 3 barre a 5 minuti → definisci OPENING RANGE
   - opening_range_high = max(high delle prime 3 barre)
   - opening_range_low = min(low delle prime 3 barre)

7. ATTENDI la conferma:
   - Per un gap DOWN (long candidate): il prezzo deve rompere AL RIALZO
     l'opening_range_high per 2 barre consecutive
   - Per un gap UP (short candidate): il prezzo deve rompere AL RIBASSO
     l'opening_range_low per 2 barre consecutive

8. Se conferma: ENTRA nella direzione del fill
9. Se nessuna conferma entro le 11:00 EST: NO TRADE oggi
```

### 4.3 Gestione del trade (09:45-16:00 EST)

```
10. TARGET: chiusura del giorno precedente (gap "riempito")
11. STOP LOSS: opening range low (per long) o high (per short)
12. EXIT FORZATA: 16:00 EST (non tenere posizioni overnight)
```

### 4.4 Perché la "conferma" è cruciale

Senza conferma, stai scommettendo che il gap riempia SUBITO. Ma il mercato potrebbe prima espandere il gap e POI revertare. La conferma (break dell'opening range nella direzione del fill) ti fa entrare solo quando il mercato sta già mostrando l'intenzione di revertare, riducendo i falsi entry.

```
SENZA CONFERMA:
  Gap down → compri subito → il prezzo continua a scendere → SL colpito → PERDITA

CON CONFERMA:
  Gap down → aspetti → il prezzo rompe l'opening range al rialzo → compri → PROFITTO
```

---

## 5. I tre filtri di protezione

### 5.1 Filtro News/Earnings

**Problema:** Un titolo che apre con gap del -8% perché ha mancato gli earnings NON reverta. Non è overreaction: è rivalutazione strutturale.

**Soluzione:** Prima del calcolo del gap, interroghiamo Finnhub per escludere qualsiasi ticker con:
- Earnings oggi o domani
- News categorizzate come "high impact" nelle ultime 24h

### 5.2 Filtro VIX (Regime di Mercato)

**Problema:** Con VIX > 30, i movimenti sono troppo ampi e veloci. I gap possono espandersi rapidamente, e lo stop loss basato sull'opening range viene colpito troppo spesso.

**Soluzione:** Se VIX > 30 all'open, semplicemente non si trada. È meglio saltare un giorno che prendere una perdita.

### 5.3 Filtro Gap Size

**Problema:** Gap troppo piccoli non danno abbastanza spazio per un profit; gap troppo grandi sono informativi, non rumorosi.

**Soluzione:** Solo gap tra 0.3% e 2.0%. Questo range è stato scelto basandosi sui dati di fill rate mostrati sopra.

---

## 6. Riepilogo visivo

```
┌─────────────────────────────────────────────────────────────────────┐
│                       GIORNATA DI TRADING                           │
│                                                                     │
│  PRE-MARKET (08:00)          OPEN (09:30)       INTRADAY (09:45+)  │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐ │
│  │ 1. News filter    │   │ 4. Opening range │   │ 7. Monitor TP/SL │ │
│  │    (Finnhub)      │   │    (15 minuti)   │   │                  │ │
│  │                   │   │                  │   │  TP: Prev Close  │ │
│  │ 2. VIX check      │──▶│ 5. Conferma      │──▶│  SL: Open Range  │ │
│  │    (< 30)         │   │    (2 barre)     │   │                  │ │
│  │                   │   │                  │   │  EXIT: 16:00 EST │ │
│  │ 3. Gap% scan      │   │ 6. Entry LONG    │   │                  │ │
│  │    (0.3% - 2.0%)  │   │    o SHORT       │   │                  │ │
│  └──────────────────┘   └──────────────────┘   └──────────────────┘ │
│                                                                     │
│  REGOLA FONDAMENTALE:                                              │
│  "Il gap piccolo è rumore. Il rumore torna alla media.              │
│   Il gap grande è segnale. Il segnale non torna indietro."          │
└─────────────────────────────────────────────────────────────────────┘
```

---

*Riferimenti:*
- Barber, B. M., & Odean, T. (2008). "All That Glitters: The Effect of Attention and News on the Buying Behavior of Individual and Institutional Investors." *Review of Financial Studies.*
- Jegadeesh, N., & Titman, S. (1993). "Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency." *Journal of Finance.*
- Poterba, J. M., & Summers, L. H. (1988). "Mean Reversion in Stock Prices: Evidence and Implications." *Journal of Financial Economics.*
