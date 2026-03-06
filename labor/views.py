from datetime import date, timedelta
import requests
from django.http import JsonResponse

# 50 states + DC (Plotly uses state abbreviations)
STATE_ABBR = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"
]

def _last_5_years_start():
    return date.today() - timedelta(days=365 * 5)

def _safe_float(x):
    try:
        if x is None:
            return None
        value = float(x)
        if value != value:  # NaN check
            return None
        return value
    except Exception:
        return None

def _fred_session() -> requests.Session:
    """
    FRED sometimes blocks requests without standard headers.
    Passing a Session with a browser-like User-Agent usually fixes "Access Denied".
    """
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })
    return s

def labor_data(request):
    import pandas as pd
    from pandas_datareader.data import DataReader

    start = _last_5_years_start()
    end = date.today()
    session = _fred_session()

    try:
        # National series from FRED:
        # UNRATE = Unemployment Rate
        # EMRATIO = Employment-Population Ratio
        df = DataReader(["UNRATE", "EMRATIO"], "fred", start, end, session=session).dropna()

        labels = [d.strftime("%Y-%m") for d in df.index.to_pydatetime()]
        unrate = [_safe_float(v) for v in df["UNRATE"].tolist()]
        emratio = [_safe_float(v) for v in df["EMRATIO"].tolist()]

        # State unemployment series IDs like CAUR, NYUR, TXUR...
        series_ids = {abbr: f"{abbr}UR" for abbr in STATE_ABBR}
        st_df = DataReader(list(series_ids.values()), "fred", start, end, session=session)

        latest = st_df.ffill().iloc[-1].to_dict()
        state_unemp = {abbr: _safe_float(latest.get(sid)) for abbr, sid in series_ids.items()}

        return JsonResponse({
            "national": {
                "labels": labels,
                "unemployment_rate": unrate,
                "employment_pop_ratio": emratio,
                "note": "Source: FRED. Employment metric shown is Employment-Population Ratio (EMRATIO)."
            },
            "states": {
                "latest_unemployment_rate": state_unemp,
                "note": "Source: FRED state unemployment series (e.g., CAUR, NYUR, TXUR)."
            }
        })

    except Exception as e:
        # Return a clean error JSON so frontend can show a message instead of breaking
        return JsonResponse({
            "error": "Failed to fetch FRED data (may be blocked by network/CDN).",
            "details": str(e),
        }, status=503)
