import numpy as np
import pandas as pd
import statsmodels.api as sm


def hedge(df2, df1):
    """
    Calcola hedge ratio e intercetta via OLS su log prices.
    Returns (hedge_ratio, intercept).
    """
    log_mpc = np.log(df2['Close'].replace([np.inf, -np.inf], np.nan))
    log_psx = np.log(df1['Close'].replace([np.inf, -np.inf], np.nan))

    data = pd.concat([log_mpc, log_psx], axis=1, join='inner').dropna()
    data.columns = ['log_mpc', 'log_psx']

    if data.empty:
        raise ValueError('Nessun dato valido per calcolare hedge ratio: verifica NaN/inf nei prezzi.')

    X = sm.add_constant(data['log_psx'])  # aggiunge intercetta alla regressione
    model = sm.OLS(data['log_mpc'], X).fit()
    hedge_ratio = float(model.params.iloc[1])  # il coefficiente
    intercept = float(model.params.iloc[0])    # l'intercetta α
    return (hedge_ratio, intercept)


def rolling_ols_beta_alpha(price1, price2, window=60):
    """
    Calcola β e α tramite OLS (numpy, senza statsmodels) sugli ultimi `window` prezzi.
    Usata nella strategia per ricalcolare il β rolling a ogni recalc_freq barre.

    Args:
        price1: lista/array di prezzi del primo asset.
        price2: lista/array di prezzi del secondo asset.
        window: finestra di lookback per la regressione (default 60).

    Returns:
        (beta, alpha) — coefficiente angolare e intercetta.
    """
    log1 = np.log(np.array(price1[-window:], dtype=float))
    log2 = np.log(np.array(price2[-window:], dtype=float))

    mask = ~(np.isnan(log1) | np.isnan(log2))
    log1, log2 = log1[mask], log2[mask]

    if len(log1) < 10:
        raise ValueError(f'Too few valid points ({len(log1)}) for rolling OLS')

    # OLS: log1 = alpha + beta * log2
    X = np.column_stack([np.ones_like(log2), log2])
    coeffs = np.linalg.lstsq(X, log1, rcond=None)[0]
    alpha, beta = float(coeffs[0]), float(coeffs[1])
    return (beta, alpha) 