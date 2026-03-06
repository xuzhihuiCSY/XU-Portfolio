# stocks/views.py
from __future__ import annotations

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

import pandas as pd
import yfinance as yf
from yahooquery import Ticker

from .services import (
    compute_rsi,
    compute_boll,
    compute_kdj,
    safe_float,
    to_series_list,
    pick_columns_case_insensitive,
    df_to_records,
)

STOCKS = [
    {"symbol": "TSLA", "name": "Tesla"},
    {"symbol": "NVDA", "name": "NVIDIA"},
    {"symbol": "AMZN", "name": "Amazon"},
    {"symbol": "AMC",  "name": "AMC"},
    {"symbol": "AAPL", "name": "Apple"},
]

ALLOWED = {s["symbol"] for s in STOCKS}


def stocks_page(request):
    return render(request, "stocks/stocks.html", {"stocks": STOCKS})


def _safe_get_dict(obj, key: str) -> dict:
    if isinstance(obj, dict):
        v = obj.get(key)
        return v if isinstance(v, dict) else {}
    return {}


def _normalize_recommendation_trend(rec_raw, symbol: str):
    try:
        if isinstance(rec_raw, pd.DataFrame):
            df = rec_raw.copy()
            if "symbol" in df.columns:
                df = df[df["symbol"] == symbol]
            df = df.tail(6)
            return df.replace({pd.NA: None}).to_dict(orient="records")
        if isinstance(rec_raw, dict):
            return rec_raw.get(symbol)
        return None
    except Exception:
        return None


def _normalize_statement_df(raw, symbol: str) -> pd.DataFrame:
    """
    yahooquery statements should return a DataFrame.
    Index by asOfDate if available, sort newest first.
    """
    if raw is None or not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame()

    df = raw.copy()

    if "symbol" in df.columns:
        df = df[df["symbol"].astype(str).str.upper() == symbol].copy()

    if "asOfDate" in df.columns:
        df["asOfDate"] = pd.to_datetime(df["asOfDate"], errors="coerce")
        df = df.sort_values("asOfDate", ascending=False).set_index("asOfDate")

    # drop metadata cols
    for meta in ("symbol", "periodType", "currencyCode"):
        if meta in df.columns:
            df = df.drop(columns=[meta])

    return df


@require_GET
def stock_data(request, symbol: str):
    symbol = symbol.upper().strip()
    if symbol not in ALLOWED:
        return JsonResponse({"error": "Symbol not allowed."}, status=400)

    cache_key = f"stock_data_v4_{symbol}"
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)

    # -----------------------
    # yfinance price history
    # -----------------------
    try:
        hist = yf.Ticker(symbol).history(period="6mo", interval="1d", auto_adjust=False)
    except Exception as e:
        return JsonResponse({"error": f"yfinance failed: {e}"}, status=503)

    if hist is None or hist.empty:
        return JsonResponse({"error": "No price data returned."}, status=503)

    hist = hist.dropna()
    hist.index = pd.to_datetime(hist.index)

    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]

    rsi = compute_rsi(close, 14)
    mid, up, lowb = compute_boll(close, 20, 2.0)
    k, d, j = compute_kdj(high, low, close, 9)

    last = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else last

    last_close = float(last["Close"])
    prev_close = float(prev["Close"]) if float(prev["Close"]) != 0 else last_close
    change = last_close - prev_close
    change_pct = (change / prev_close) * 100 if prev_close else 0.0

    # -----------------------
    # yahooquery data
    # -----------------------
    yq = Ticker(symbol)

    price_all = getattr(yq, "price", None)
    summary_all = getattr(yq, "summary_detail", None)
    rec_raw = getattr(yq, "recommendation_trend", None)

    price = _safe_get_dict(price_all, symbol)
    summary = _safe_get_dict(summary_all, symbol)
    rec_payload = _normalize_recommendation_trend(rec_raw, symbol)

    # ---- statements (NO trailing arg; your yahooquery doesn't support it)
    try:
        income_raw = yq.income_statement(frequency="a")
    except TypeError:
        income_raw = yq.income_statement()

    try:
        balance_raw = yq.balance_sheet(frequency="a")
    except TypeError:
        balance_raw = yq.balance_sheet()

    try:
        cash_raw = yq.cash_flow(frequency="a")
    except TypeError:
        cash_raw = yq.cash_flow()

    income_df = _normalize_statement_df(income_raw, symbol)
    balance_df = _normalize_statement_df(balance_raw, symbol)
    cash_df = _normalize_statement_df(cash_raw, symbol)

    # Pick common metrics (CamelCase)
    income_df = pick_columns_case_insensitive(income_df, [
        "TotalRevenue",
        "GrossProfit",
        "OperatingIncome",
        "NetIncome",
        "DilutedEPS",
    ])

    balance_df = pick_columns_case_insensitive(balance_df, [
        "TotalAssets",
        "TotalLiabilitiesNetMinorityInterest",
        "StockholdersEquity",
        "CashAndCashEquivalents",
        "TotalDebt",
    ])

    cash_df = pick_columns_case_insensitive(cash_df, [
        "OperatingCashFlow",
        "InvestingCashFlow",
        "FinancingCashFlow",
        "CapitalExpenditure",
        "FreeCashFlow",
    ])

    # -----------------------
    # signals
    # -----------------------
    rsi_now = float(rsi.iloc[-1]) if len(rsi) else 50.0

    boll_pos = "inside"
    try:
        up_last = safe_float(up.iloc[-1])
        low_last = safe_float(lowb.iloc[-1])
        if up_last is not None and last_close > float(up_last):
            boll_pos = "above_upper"
        elif low_last is not None and last_close < float(low_last):
            boll_pos = "below_lower"
    except Exception:
        pass

    k_now = safe_float(k.iloc[-1])
    d_now = safe_float(d.iloc[-1])
    kdj_note = "K above D" if (k_now is not None and d_now is not None and k_now > d_now) else "K below D"

    payload = {
        "symbol": symbol,
        "name": next(s["name"] for s in STOCKS if s["symbol"] == symbol),

        "market": {
            "last_close": last_close,
            "change": float(change),
            "change_pct": float(change_pct),
            "currency": price.get("currency") or summary.get("currency") or "",
        },

        "series": {
            "dates": [d.strftime("%Y-%m-%d") for d in close.index.to_pydatetime()],
            "close": [float(x) for x in close.tolist()],
            "boll_mid": to_series_list(mid),
            "boll_up": to_series_list(up),
            "boll_low": to_series_list(lowb),
            "rsi": to_series_list(rsi),
            "k": to_series_list(k),
            "d": to_series_list(d),
            "j": to_series_list(j),
        },

        "signals": {
            "rsi_now": rsi_now,
            "boll_pos": boll_pos,
            "kdj_note": kdj_note,
        },

        "analyst": {
            "shortName": price.get("shortName") or price.get("longName") or "",
            "marketCap": summary.get("marketCap", None),
            "recommendationTrend": rec_payload,
        },

        "financials": {
            "income": df_to_records(income_df, max_rows=6, max_cols=10),
            "balance": df_to_records(balance_df, max_rows=6, max_cols=10),
            "cashflow": df_to_records(cash_df, max_rows=6, max_cols=10),
        }
    }

    cache.set(cache_key, payload, 60 * 30)
    return JsonResponse(payload)
