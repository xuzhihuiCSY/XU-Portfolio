import os
from datetime import date, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from django.core.cache import cache
from django.http import JsonResponse

# 50 states + DC (Plotly uses state abbreviations)
STATE_ABBR = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"
]

# State FIPS used by BLS LAUS series IDs.
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10", "DC": "11",
    "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30",
    "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56",
}

BLS_ENDPOINT = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_MAX_SERIES_PER_REQUEST = 20
NATIONAL_UNRATE_SERIES = "LNS14000000"
NATIONAL_EMRATIO_SERIES = "LNS12300000"

LABOR_CACHE_KEY = "labor_data_v1"
LABOR_STALE_KEY = "labor_data_stale_v1"
LABOR_CACHE_TTL = 60 * 30      # 30 minutes
LABOR_STALE_TTL = 60 * 60 * 24 # 24 hours


def _last_5_years_start():
    return date.today() - timedelta(days=365 * 5)


def _month_label_to_date(label: str) -> date:
    year = int(label[:4])
    month = int(label[5:7])
    return date(year, month, 1)


def _state_unrate_series_id(abbr: str) -> str:
    # LAUS state unemployment rate: LAUST + state_fips + 0000000000003
    return f"LAUST{STATE_FIPS[abbr]}0000000000003"


def _emergency_payload():
    # Non-live fallback so UI remains usable when external APIs are unavailable.
    labels = [
        "2025-03", "2025-04", "2025-05", "2025-06", "2025-07", "2025-08",
        "2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02",
    ]
    unrate = [3.9, 4.0, 4.0, 4.1, 4.1, 4.2, 4.1, 4.1, 4.0, 4.1, 4.1, 4.1]
    emratio = [60.2, 60.2, 60.3, 60.3, 60.2, 60.2, 60.3, 60.3, 60.4, 60.4, 60.5, 60.5]

    state_unemp = {
        "CA": 5.4,
        "TX": 4.0,
        "NY": 4.6,
        "FL": 3.7,
        "WA": 4.5,
        "IL": 4.8,
        "PA": 4.2,
        "OH": 4.1,
        "GA": 3.7,
        "NC": 3.9,
    }

    return {
        "national": {
            "labels": labels,
            "unemployment_rate": unrate,
            "employment_pop_ratio": emratio,
            "note": "Source unavailable now. Showing emergency snapshot (not live).",
        },
        "states": {
            "latest_unemployment_rate": state_unemp,
            "note": "Partial emergency snapshot shown because live BLS data is unavailable.",
        },
        "meta": {
            "stale": True,
            "warning": "Live BLS request failed and no cache was available.",
            "fallback": "emergency_snapshot",
        },
    }

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

def _bls_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })

    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def _chunked(values, size):
    for i in range(0, len(values), size):
        yield values[i:i + size]


def _fetch_bls_series(session: requests.Session, series_ids, start_year: int, end_year: int):
    registration_key = os.getenv("BLS_API_KEY", "").strip()
    all_series = {}

    for chunk in _chunked(series_ids, BLS_MAX_SERIES_PER_REQUEST):
        payload = {
            "seriesid": chunk,
            "startyear": str(start_year),
            "endyear": str(end_year),
        }
        if registration_key:
            payload["registrationkey"] = registration_key

        resp = session.post(BLS_ENDPOINT, json=payload, timeout=35)
        resp.raise_for_status()
        body = resp.json()
        status = body.get("status")
        if status != "REQUEST_SUCCEEDED":
            msg = "; ".join(body.get("message", [])) if isinstance(body.get("message"), list) else str(body.get("message"))
            raise ValueError(f"BLS API failed: {msg or status}")

        series_list = body.get("Results", {}).get("series", [])
        for series in series_list:
            all_series[series.get("seriesID")] = series.get("data", [])

    return all_series


def _series_monthly_points(points):
    monthly = {}
    for row in points:
        period = row.get("period", "")
        if not period.startswith("M") or period == "M13":
            continue
        year = row.get("year")
        month = period[1:]
        value = _safe_float(row.get("value"))
        if year and month and value is not None:
            monthly[f"{year}-{month}"] = value
    return monthly


def _build_labor_payload():
    start = _last_5_years_start()
    end = date.today()
    start_year = start.year
    end_year = end.year
    session = _bls_session()

    state_series_map = {abbr: _state_unrate_series_id(abbr) for abbr in STATE_ABBR}
    requested_series = [NATIONAL_UNRATE_SERIES, NATIONAL_EMRATIO_SERIES] + list(state_series_map.values())
    all_series = _fetch_bls_series(session, requested_series, start_year, end_year)

    nat_unrate_points = _series_monthly_points(all_series.get(NATIONAL_UNRATE_SERIES, []))
    nat_emratio_points = _series_monthly_points(all_series.get(NATIONAL_EMRATIO_SERIES, []))

    labels = sorted(set(nat_unrate_points.keys()) & set(nat_emratio_points.keys()))
    labels = [lab for lab in labels if _month_label_to_date(lab) >= date(start.year, start.month, 1)]

    if not labels:
        raise ValueError("BLS returned no monthly national labor data")

    unrate = [nat_unrate_points.get(lab) for lab in labels]
    emratio = [nat_emratio_points.get(lab) for lab in labels]

    state_unemp = {}
    for abbr, sid in state_series_map.items():
        points = _series_monthly_points(all_series.get(sid, []))
        if not points:
            state_unemp[abbr] = None
            continue
        latest_label = sorted(points.keys())[-1]
        state_unemp[abbr] = _safe_float(points.get(latest_label))

    return {
        "national": {
            "labels": labels,
            "unemployment_rate": unrate,
            "employment_pop_ratio": emratio,
            "note": "Source: BLS. Employment metric shown is Employment-Population Ratio.",
        },
        "states": {
            "latest_unemployment_rate": state_unemp,
            "note": "Source: BLS LAUS state unemployment rate series.",
        },
        "meta": {"stale": False, "fallback": "bls_api"},
    }


def labor_data(request):
    cached = cache.get(LABOR_CACHE_KEY)
    if cached is not None:
        return JsonResponse(cached)

    try:
        payload = _build_labor_payload()
        cache.set(LABOR_CACHE_KEY, payload, LABOR_CACHE_TTL)
        cache.set(LABOR_STALE_KEY, payload, LABOR_STALE_TTL)
        return JsonResponse(payload)
    except Exception as e:
        stale = cache.get(LABOR_STALE_KEY)
        if stale is not None:
            stale_payload = dict(stale)
            meta = dict(stale_payload.get("meta", {}))
            meta["stale"] = True
            meta["warning"] = "Live BLS request failed; returning cached data."
            stale_payload["meta"] = meta
            return JsonResponse(stale_payload)

        # No cached data available yet: use emergency payload to avoid empty UI.
        payload = _emergency_payload()
        meta = dict(payload.get("meta", {}))
        meta["details"] = str(e)
        payload["meta"] = meta
        return JsonResponse(payload)
