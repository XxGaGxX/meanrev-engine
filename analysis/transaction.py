def apply_transaction_costs(pnl, notional, bps=20):
    """bps: 10-30 per liquidi come questi, sono tutti large cap liquidi"""
    cost = notional * (bps / 10000)
    return pnl - cost