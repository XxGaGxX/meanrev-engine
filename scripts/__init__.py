"""scripts package marker.

Allows tests to `from scripts.eda_gap_expectancy import run_eda` without
mutating sys.path. Scripts that run as `python scripts/X.py` continue to
work (they insert ROOT onto sys.path themselves, as before).
"""
