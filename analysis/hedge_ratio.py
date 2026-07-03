import numpy as np
import statsmodels.api as sm

def hedge(df2, df1):
    log_mpc = np.log(df2['Close'])
    log_psx = np.log(df1['Close'])
    

    X = sm.add_constant(log_psx)  # aggiunge intercetta alla regressione
    model = sm.OLS(log_mpc, X).fit()
    hedge_ratio = model.params.iloc[1]  # il coefficiente, non l'intercetta
    return hedge_ratio 