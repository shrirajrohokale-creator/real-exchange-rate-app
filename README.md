# Real Exchange Rate Explorer (IMF data)

A Streamlit app for an MBA International Finance course. Pick any two IMF countries (or the Euro area), pull monthly IMF CPI and exchange-rate data from January 1976 (where available), and explore the nominal and real exchange rate.

## Economics

| Symbol | Meaning |
|---|---|
| `S(t)` | Units of **Country 2** currency per **1 unit of Country 1** currency |
| `P1(t)`, `P2(t)` | Monthly CPI of Country 1 and Country 2 |
| `RER(t)` | `S(t) × P1(t) / P2(t)` |
| `RER*` | Average of `RER(t)` over valid months in the selected start–end sample |
| `Real Index(t)` | `100 × RER(t) / RER*` |

- IMF exchange rates are quoted as **local currency units per USD** (`XDC_USD`). With `e1`, `e2` = units of Country 1 / Country 2 currency per USD, the app computes `S = e2 / e1`.
- `RER*` and the Real Index are **recalculated whenever the sample dates change**.
- Nominal `S(t)` is plotted in actual currency units (never normalised).
- A month is "valid" only if both CPIs and both exchange rates exist and are positive. Invalid months are shown as gaps in the charts and excluded from `RER*`.
- Interpretation: a Real Index above 100 means Country 1's goods are relatively expensive (its currency is strong in real terms) versus the sample average; below 100 means relatively cheap.

## Features

- Country 1 / Country 2 selectors (IMF members plus Euro area, code `G163`).
- Sample start/end month slider.
- Chart modes: **Real**, **Nominal**, or **Both** (Both uses separate left/right y-axes).
- CSV download of every observation and calculation in the selected sample (exchange rates per USD, CPIs, `S`, `RER`, `RER*`, Real Index, and a valid-month flag).

## Data

- API base: `https://api.imf.org/external/sdmx/3.0`
- CPI: dataflow `IMF.STA/CPI`, key `{ISO3}.CPI._T.IX.M`
- Exchange rate: dataflow `IMF.STA/ER`, key `{ISO3}.XDC_USD.PA_RT.M`
- Euro area uses `G163`.
- Responses are cached for 12 hours.

IMF coverage varies: some countries start after 1976, have gaps, or lack one of the two series. The app warns when a series is unavailable and works with the overlapping valid months.

## Run it

Requires Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501). An internet connection is required.

## Notes and troubleshooting

- **"unavailable" warnings**: the IMF does not publish that series for that country (or the key differs). Try another country.
- **Request errors**: the app tries the latest dataflow version (`+`), then `~`, and both CSV and JSON responses. If the IMF changes the dataflow IDs, adjust `CPI_FLOW`, `ER_FLOW` and `AGENCY` at the top of `app.py`.
- **Currency regimes**: exchange-rate series reflect the IMF's period-average rate for the local currency. For Euro-area members before 1999, national currencies apply; use `G163` for the euro itself.
- The country list is embedded in `app.py` for reliability; edit the `COUNTRIES` dictionary to add or remove entries.
