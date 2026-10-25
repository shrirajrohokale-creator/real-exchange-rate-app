"""Real Exchange Rate Explorer (IMF data) - MBA International Finance.

Run with:  streamlit run app.py

Definitions
-----------
S(t)      = units of Country 2 currency per one unit of Country 1 currency
P1, P2    = monthly CPI index of Country 1 / Country 2
RER(t)    = S(t) * P1(t) / P2(t)
RER*      = average of RER(t) over valid months in the selected sample
RealIndex = 100 * RER(t) / RER*

IMF exchange-rate data are local-currency units per USD (XDC_USD), so with
e_i = units of currency i per USD:   S = e2 / e1.
"""

from __future__ import annotations

import io
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
BASE_URL = "https://api.imf.org/external/sdmx/3.0"
AGENCY = "IMF.STA"
CPI_FLOW = "CPI"
ER_FLOW = "ER"
FIRST_MONTH = pd.Timestamp("1976-01-01")
# Version selectors tried in order ("+" = latest stable in SDMX 3.0).
VERSIONS = ["+", "~"]
HEADERS_CSV = {"Accept": "application/vnd.sdmx.data+csv;version=2.0.0, text/csv;q=0.9"}
HEADERS_JSON = {"Accept": "application/vnd.sdmx.data+json;version=2.0.0, application/json;q=0.9"}

# IMF member countries / economies (ISO3 -> name) plus the Euro area (G163).
COUNTRIES: dict[str, str] = {
    "G163": "Euro area", "AFG": "Afghanistan", "ALB": "Albania", "DZA": "Algeria",
    "AGO": "Angola", "ATG": "Antigua and Barbuda", "ARG": "Argentina", "ARM": "Armenia",
    "AUS": "Australia", "AUT": "Austria", "AZE": "Azerbaijan", "BHS": "Bahamas, The",
    "BHR": "Bahrain", "BGD": "Bangladesh", "BRB": "Barbados", "BLR": "Belarus",
    "BEL": "Belgium", "BLZ": "Belize", "BEN": "Benin", "BTN": "Bhutan",
    "BOL": "Bolivia", "BIH": "Bosnia and Herzegovina", "BWA": "Botswana", "BRA": "Brazil",
    "BRN": "Brunei Darussalam", "BGR": "Bulgaria", "BFA": "Burkina Faso", "BDI": "Burundi",
    "CPV": "Cabo Verde", "KHM": "Cambodia", "CMR": "Cameroon", "CAN": "Canada",
    "CAF": "Central African Republic", "TCD": "Chad", "CHL": "Chile", "CHN": "China, P.R.: Mainland",
    "COL": "Colombia", "COM": "Comoros", "COD": "Congo, Dem. Rep. of the", "COG": "Congo, Rep. of",
    "CRI": "Costa Rica", "CIV": "Côte d'Ivoire", "HRV": "Croatia", "CYP": "Cyprus",
    "CZE": "Czech Republic", "DNK": "Denmark", "DJI": "Djibouti", "DMA": "Dominica",
    "DOM": "Dominican Republic", "ECU": "Ecuador", "EGY": "Egypt", "SLV": "El Salvador",
    "GNQ": "Equatorial Guinea", "ERI": "Eritrea", "EST": "Estonia", "SWZ": "Eswatini",
    "ETH": "Ethiopia", "FJI": "Fiji", "FIN": "Finland", "FRA": "France",
    "GAB": "Gabon", "GMB": "Gambia, The", "GEO": "Georgia", "DEU": "Germany",
    "GHA": "Ghana", "GRC": "Greece", "GRD": "Grenada", "GTM": "Guatemala",
    "GIN": "Guinea", "GNB": "Guinea-Bissau", "GUY": "Guyana", "HTI": "Haiti",
    "HND": "Honduras", "HKG": "Hong Kong SAR", "HUN": "Hungary", "ISL": "Iceland",
    "IND": "India", "IDN": "Indonesia", "IRN": "Iran", "IRQ": "Iraq",
    "IRL": "Ireland", "ISR": "Israel", "ITA": "Italy", "JAM": "Jamaica",
    "JPN": "Japan", "JOR": "Jordan", "KAZ": "Kazakhstan", "KEN": "Kenya",
    "KIR": "Kiribati", "KOR": "Korea, Rep. of", "KWT": "Kuwait", "KGZ": "Kyrgyz Republic",
    "LAO": "Lao P.D.R.", "LVA": "Latvia", "LBN": "Lebanon", "LSO": "Lesotho",
    "LBR": "Liberia", "LBY": "Libya", "LTU": "Lithuania", "LUX": "Luxembourg",
    "MAC": "Macao SAR", "MDG": "Madagascar", "MWI": "Malawi", "MYS": "Malaysia",
    "MDV": "Maldives", "MLI": "Mali", "MLT": "Malta", "MHL": "Marshall Islands",
    "MRT": "Mauritania", "MUS": "Mauritius", "MEX": "Mexico", "FSM": "Micronesia",
    "MDA": "Moldova", "MNG": "Mongolia", "MNE": "Montenegro", "MAR": "Morocco",
    "MOZ": "Mozambique", "MMR": "Myanmar", "NAM": "Namibia", "NRU": "Nauru",
    "NPL": "Nepal", "NLD": "Netherlands", "NZL": "New Zealand", "NIC": "Nicaragua",
    "NER": "Niger", "NGA": "Nigeria", "MKD": "North Macedonia", "NOR": "Norway",
    "OMN": "Oman", "PAK": "Pakistan", "PLW": "Palau", "PAN": "Panama",
    "PNG": "Papua New Guinea", "PRY": "Paraguay", "PER": "Peru", "PHL": "Philippines",
    "POL": "Poland", "PRT": "Portugal", "QAT": "Qatar", "ROU": "Romania",
    "RUS": "Russian Federation", "RWA": "Rwanda", "WSM": "Samoa", "SMR": "San Marino",
    "STP": "São Tomé and Príncipe", "SAU": "Saudi Arabia", "SEN": "Senegal", "SRB": "Serbia",
    "SYC": "Seychelles", "SLE": "Sierra Leone", "SGP": "Singapore", "SVK": "Slovak Republic",
    "SVN": "Slovenia", "SLB": "Solomon Islands", "SOM": "Somalia", "ZAF": "South Africa",
    "SSD": "South Sudan", "ESP": "Spain", "LKA": "Sri Lanka", "KNA": "St. Kitts and Nevis",
    "LCA": "St. Lucia", "VCT": "St. Vincent and the Grenadines", "SDN": "Sudan", "SUR": "Suriname",
    "SWE": "Sweden", "CHE": "Switzerland", "SYR": "Syria", "TWN": "Taiwan Province of China",
    "TJK": "Tajikistan", "TZA": "Tanzania", "THA": "Thailand", "TLS": "Timor-Leste",
    "TGO": "Togo", "TON": "Tonga", "TTO": "Trinidad and Tobago", "TUN": "Tunisia",
    "TUR": "Türkiye", "TKM": "Turkmenistan", "TUV": "Tuvalu", "UGA": "Uganda",
    "UKR": "Ukraine", "ARE": "United Arab Emirates", "GBR": "United Kingdom",
    "USA": "United States", "URY": "Uruguay", "UZB": "Uzbekistan", "VUT": "Vanuatu",
    "VEN": "Venezuela", "VNM": "Vietnam", "YEM": "Yemen", "ZMB": "Zambia", "ZWE": "Zimbabwe",
}


# --------------------------------------------------------------------------
# IMF data retrieval
# --------------------------------------------------------------------------
def _parse_period(value: str) -> pd.Timestamp:
    """Parse '1976-M01' / '1976-01' into the first day of that month (monthly only)."""
    m = re.match(r"^(\d{4})-?M?(\d{1,2})$", str(value).strip())
    if not m:
        return pd.NaT
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return pd.NaT
    return pd.Timestamp(year=year, month=month, day=1)


def _parse_csv(text: str) -> pd.Series:
    df = pd.read_csv(io.StringIO(text))
    cols = {c.upper().split(":")[0].strip(): c for c in df.columns}
    t_col, v_col = cols.get("TIME_PERIOD"), cols.get("OBS_VALUE")
    if t_col is None or v_col is None:
        return pd.Series(dtype=float)
    return _to_series(df[t_col], df[v_col])


def _parse_json(payload: dict) -> pd.Series:
    """Parse SDMX-JSON (2.0 style) for a single-series response."""
    data = payload.get("data", payload)
    structure = data["structures"][0] if "structures" in data else data["structure"]
    time_values = structure["dimensions"]["observation"][0]["values"]
    periods, values = [], []
    for ds in data["dataSets"]:
        for series in ds.get("series", {}).values():
            for idx, obs in series.get("observations", {}).items():
                periods.append(time_values[int(idx)].get("id") or time_values[int(idx)].get("value"))
                values.append(obs[0])
    return _to_series(pd.Series(periods), pd.Series(values))


def _to_series(periods: pd.Series, values: pd.Series) -> pd.Series:
    idx = periods.map(_parse_period)
    s = pd.Series(pd.to_numeric(values, errors="coerce").to_numpy(), index=pd.DatetimeIndex(idx))
    s = s[s.index.notna()]
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def fetch_series(flow: str, key: str) -> tuple[pd.Series, str]:
    """Fetch one monthly series. Returns (series, message). Empty series => unavailable."""
    last_msg = "no response"
    for version in VERSIONS:
        url = f"{BASE_URL}/data/dataflow/{AGENCY}/{flow}/{version}/{key}"
        params = {"startPeriod": "1976-01"}
        for headers in (HEADERS_CSV, HEADERS_JSON):
            try:
                r = requests.get(url, params=params, headers=headers, timeout=60)
            except requests.RequestException as exc:
                last_msg = f"network error: {exc}"
                continue
            if r.status_code == 404:
                last_msg = "no data (404)"
                break  # series does not exist for this version; try next version
            if r.status_code != 200:
                last_msg = f"HTTP {r.status_code}"
                continue
            try:
                ctype = r.headers.get("Content-Type", "").lower()
                s = _parse_json(r.json()) if "json" in ctype else _parse_csv(r.text)
            except Exception as exc:  # parsing problems should not crash the app
                last_msg = f"could not parse response ({exc})"
                continue
            if len(s):
                return s[s.index >= FIRST_MONTH], "ok"
            last_msg = "empty series"
    return pd.Series(dtype=float), last_msg


def load_country(iso3: str) -> tuple[pd.DataFrame, list[str]]:
    """Return DataFrame[cpi, xdc_usd] on a monthly index plus any warnings."""
    cpi, m1 = fetch_series(CPI_FLOW, f"{iso3}.CPI._T.IX.M")
    er, m2 = fetch_series(ER_FLOW, f"{iso3}.XDC_USD.PA_RT.M")
    notes = []
    if cpi.empty:
        notes.append(f"{iso3} CPI unavailable ({m1})")
    if er.empty:
        notes.append(f"{iso3} exchange rate unavailable ({m2})")
    df = pd.concat({"cpi": cpi, "xdc_usd": er}, axis=1).sort_index()
    return df, notes


# --------------------------------------------------------------------------
# Calculations
# --------------------------------------------------------------------------
def build_panel(iso1: str, iso2: str) -> tuple[pd.DataFrame, list[str]]:
    d1, n1 = load_country(iso1)
    d2, n2 = load_country(iso2)
    panel = pd.DataFrame(
        {
            "e1_per_usd": d1["xdc_usd"] if "xdc_usd" in d1 else np.nan,
            "e2_per_usd": d2["xdc_usd"] if "xdc_usd" in d2 else np.nan,
            "P1": d1["cpi"] if "cpi" in d1 else np.nan,
            "P2": d2["cpi"] if "cpi" in d2 else np.nan,
        }
    ).sort_index()
    panel = panel[panel.index >= FIRST_MONTH]
    # S = units of Country 2 currency per 1 unit of Country 1 currency = e2 / e1
    panel["S"] = panel["e2_per_usd"] / panel["e1_per_usd"]
    panel["RER"] = panel["S"] * panel["P1"] / panel["P2"]
    ok = (
        panel[["S", "P1", "P2", "RER"]].notna().all(axis=1)
        & np.isfinite(panel["RER"])
        & (panel[["e1_per_usd", "e2_per_usd", "P1", "P2"]] > 0).all(axis=1)
    )
    panel["valid"] = ok
    panel.loc[~ok, ["S", "RER"]] = np.nan
    return panel, n1 + n2


def apply_sample(panel: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, float]:
    """Restrict to [start, end] and recompute RER* and the Real Index."""
    sample = panel.loc[(panel.index >= start) & (panel.index <= end)].copy()
    rer_star = float(sample.loc[sample["valid"], "RER"].mean()) if sample["valid"].any() else float("nan")
    sample["RER_star"] = rer_star
    sample["Real_Index"] = 100 * sample["RER"] / rer_star
    return sample, rer_star


# --------------------------------------------------------------------------
# Charts / export
# --------------------------------------------------------------------------
def make_chart(sample: pd.DataFrame, view: str, name1: str, name2: str) -> go.Figure:
    real_name = "Real Index (RER* = 100)"
    nom_name = f"Nominal S ({name2} per {name1})"
    valid = sample[sample["valid"]]
    if view == "Both":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=valid.index, y=valid["Real_Index"], name=real_name,
                                 mode="lines", line=dict(color="#1f77b4")), secondary_y=False)
        fig.add_trace(go.Scatter(x=valid.index, y=valid["S"], name=nom_name,
                                 mode="lines", line=dict(color="#d62728")), secondary_y=True)
        fig.update_yaxes(title_text="Real Index", secondary_y=False)
        fig.update_yaxes(title_text=f"Units of {name2} currency per 1 unit of {name1} currency",
                         secondary_y=True)
    else:
        fig = go.Figure()
        if view == "Real":
            fig.add_trace(go.Scatter(x=valid.index, y=valid["Real_Index"], name=real_name,
                                     mode="lines", line=dict(color="#1f77b4")))
            fig.update_yaxes(title_text="Real Index (100 = sample-average RER)")
        else:
            fig.add_trace(go.Scatter(x=valid.index, y=valid["S"], name=nom_name,
                                     mode="lines", line=dict(color="#d62728")))
            fig.update_yaxes(title_text=f"Units of {name2} currency per 1 unit of {name1} currency")
    if view in ("Real", "Both"):
        fig.add_hline(y=100, line_dash="dot", line_color="gray",
                      annotation_text="RER* = 100", annotation_position="bottom right")
    fig.update_layout(
        title=f"{name1} vs {name2}: {view.lower()} exchange rate",
        hovermode="x unified", height=520, legend=dict(orientation="h", y=-0.15),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_xaxes(title_text="Month")
    return fig


def to_csv(sample: pd.DataFrame, iso1: str, iso2: str, name1: str, name2: str) -> bytes:
    out = sample.copy()
    out.insert(0, "month", out.index.strftime("%Y-%m"))
    out.insert(1, "country1", f"{name1} ({iso1})")
    out.insert(2, "country2", f"{name2} ({iso2})")
    out = out.rename(
        columns={
            "e1_per_usd": f"{iso1}_currency_per_USD",
            "e2_per_usd": f"{iso2}_currency_per_USD",
            "P1": f"P1_CPI_{iso1}",
            "P2": f"P2_CPI_{iso2}",
            "S": "S_country2_per_country1",
            "valid": "valid_month",
        }
    )
    return out.to_csv(index=False).encode("utf-8")


# --------------------------------------------------------------------------
# Streamlit UI
# --------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Real Exchange Rate Explorer", layout="wide")
    st.title("Real Exchange Rate Explorer")
    st.caption(
        "Monthly IMF CPI and exchange-rate data (from Jan 1976 where available). "
        "S(t) = units of Country 2 currency per 1 unit of Country 1 currency; "
        "RER(t) = S(t) × P1(t) / P2(t); Real Index = 100 × RER(t) / RER*."
    )

    codes = sorted(COUNTRIES, key=lambda c: (c != "G163", COUNTRIES[c]))
    label = lambda c: f"{COUNTRIES[c]} ({c})"  # noqa: E731

    with st.sidebar:
        st.header("Inputs")
        iso1 = st.selectbox("Country 1", codes, index=codes.index("USA"), format_func=label)
        iso2 = st.selectbox("Country 2", codes, index=codes.index("G163"), format_func=label)
        view = st.radio("Chart", ["Real", "Nominal", "Both"], horizontal=True)

    if iso1 == iso2:
        st.warning("Please choose two different countries.")
        return

    name1, name2 = COUNTRIES[iso1], COUNTRIES[iso2]
    with st.spinner("Fetching IMF data…"):
        panel, notes = build_panel(iso1, iso2)

    for n in notes:
        st.warning(n)

    valid_idx = panel.index[panel["valid"]]
    if len(valid_idx) < 2:
        st.error(
            "Not enough overlapping CPI and exchange-rate data for this pair. "
            "Try different countries (IMF coverage is limited for some economies)."
        )
        return

    months = [d.strftime("%Y-%m") for d in pd.date_range(valid_idx.min(), valid_idx.max(), freq="MS")]
    with st.sidebar:
        start_s, end_s = st.select_slider(
            "Sample period (start – end month)", options=months, value=(months[0], months[-1])
        )
    start, end = pd.Timestamp(start_s + "-01"), pd.Timestamp(end_s + "-01")

    sample, rer_star = apply_sample(panel, start, end)
    n_valid, n_total = int(sample["valid"].sum()), len(sample)
    if n_valid == 0:
        st.error("No valid months in the selected sample period.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("RER* (sample average)", f"{rer_star:,.4f}")
    c2.metric("Valid months", f"{n_valid} of {n_total}")
    c3.metric("Sample", f"{start_s} → {end_s}")
    if n_valid < n_total:
        st.info(f"{n_total - n_valid} month(s) in the sample are missing data and are excluded from RER*.")

    st.plotly_chart(make_chart(sample, view, name1, name2), use_container_width=True)

    st.download_button(
        "Download CSV (selected sample)",
        data=to_csv(sample, iso1, iso2, name1, name2),
        file_name=f"rer_{iso1}_{iso2}_{start_s}_{end_s}.csv",
        mime="text/csv",
    )
    with st.expander("Preview data"):
        st.dataframe(sample.reset_index(names="month"), use_container_width=True)

    st.caption(
        "Source: IMF (CPI and Exchange Rates dataflows, SDMX 3.0 API). "
        "IMF exchange rates are local currency per USD and are converted so that S = e2 / e1."
    )


if __name__ == "__main__":
    main()
