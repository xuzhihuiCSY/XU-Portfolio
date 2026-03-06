# stocks/services.py
import numpy as np
import pandas as pd


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    close = close.astype(float)
    delta = close.diff()

    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / (avg_loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))

    return rsi.bfill().fillna(50.0)


def compute_boll(close: pd.Series, window: int = 20, n_std: float = 2.0):
    close = close.astype(float)
    ma = close.rolling(window).mean()
    sd = close.rolling(window).std()
    upper = ma + n_std * sd
    lower = ma - n_std * sd
    return ma, upper, lower


def compute_kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9):
    high = high.astype(float)
    low = low.astype(float)
    close = close.astype(float)

    low_n = low.rolling(n).min()
    high_n = high.rolling(n).max()

    denom = (high_n - low_n).replace(0, np.nan)
    rsv = ((close - low_n) / denom) * 100.0
    rsv = rsv.replace([np.inf, -np.inf], np.nan).bfill().fillna(50.0)

    k = pd.Series(index=close.index, dtype=float)
    d = pd.Series(index=close.index, dtype=float)

    if len(close) == 0:
        return k, d, k

    k.iloc[0] = 50.0
    d.iloc[0] = 50.0

    for i in range(1, len(close)):
        k.iloc[i] = (2 / 3) * k.iloc[i - 1] + (1 / 3) * rsv.iloc[i]
        d.iloc[i] = (2 / 3) * d.iloc[i - 1] + (1 / 3) * k.iloc[i]

    j = 3 * k - 2 * d
    return k, d, j


def safe_float(x):
    try:
        if x is None:
            return None
        if isinstance(x, (np.floating, np.integer)):
            return float(x)
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def to_series_list(s: pd.Series):
    if s is None:
        return []
    return [safe_float(v) for v in s.tolist()]


def pick_columns_case_insensitive(df: pd.DataFrame, wanted: list[str]) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    col_map = {str(c).lower(): c for c in df.columns}
    keep = []
    for w in wanted:
        k = str(w).lower()
        if k in col_map:
            keep.append(col_map[k])

    if not keep:
        return pd.DataFrame()

    return df[keep].copy()


def df_to_records(df: pd.DataFrame, max_rows: int = 6, max_cols: int = 10):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []

    df2 = df.copy().head(max_rows)

    cols = list(df2.columns)[:max_cols]
    df2 = df2[cols].replace({np.nan: None})

    out = []
    for idx, row in df2.iterrows():
        label = str(idx)
        values = {}
        for c in df2.columns:
            v = row[c]
            if isinstance(v, (int, float, np.integer, np.floating)):
                values[str(c)] = safe_float(v)
            else:
                values[str(c)] = v
        out.append({"label": label, "values": values})
    return out
