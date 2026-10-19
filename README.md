# StockValue AI — beginner setup

## What it does
Enter a US stock ticker and click **Analyze stock**. The app downloads available historical prices and fundamentals using `yfinance`, calculates an illustrative DCF, dividend model, risk statistics, and CAPM required return. You can adjust assumptions in the sidebar.

## Install and run
1. Install Python 3.10 or newer from https://www.python.org/downloads/.
2. Extract the ZIP file. Open a Terminal (macOS) or PowerShell (Windows) in the `stockvalue_ai` folder.
3. Create a virtual environment (optional but recommended): `python -m venv .venv` then activate it. On macOS: `source .venv/bin/activate`; on Windows PowerShell: `.venv\Scripts\Activate.ps1`.
4. Install: `python -m pip install -r requirements.txt` (on macOS you may need `python3`).
5. Run: `python -m streamlit run app.py`.
6. Open http://localhost:8501 if the browser does not open automatically.
7. Test with MSFT, AAPL or KO. Live results depend on Yahoo availability.

## Validate the math
Run `python -m pytest -q` in the app folder.

## Deploy
Create a GitHub repository with these files (never commit credentials), then deploy via https://share.streamlit.io/. The hosting service will install requirements and run `app.py`. Read yfinance/Yahoo terms before public or commercial deployment. For production use, replace unofficial feeds with a licensed provider and audit data fields.

## Important methodological notes
The DCF is an educational screening approximation. Yahoo `freeCashflow` is not assured to be unlevered FCFF, so applying WACC and subtracting net debt can mix inconsistent definitions. Replace with verified FCFF from statements before making investment decisions. Negative FCF is not handled by this simple model. The SPY-based risk model uses price returns rather than total returns. Intrinsic values and risk measures are estimates, not financial advice.


## FCFE valuation (Version 1.1)

The Intrinsic valuation tab now includes an independent **Free Cash Flow to Equity (FCFE)** section, in addition to the existing DCF and DDM calculations. It retrieves annual operating cash flow, capital expenditures, and net borrowing when available. Check reporting dates, signs, and missing fields; a zero placeholder for missing borrowing is not verified data.

FCFE = CFO - positive capex outlay + net borrowing. Forecast FCFE for N years, discount at cost of equity (CAPM or manual), and add a Gordon-growth terminal value. Divide equity present value by shares outstanding. Unlike FCFF, do not subtract net debt. Financial institutions and firms with negative or highly volatile FCFE require specialized models.

## Version 1.2: Three-stage FCFE and reverse-implied earnings growth

A three-stage equity model is implemented in `advanced.py` and shown in the Intrinsic Valuation tab. Stage 1 assumes constant high growth, stage 2 linearly fades the growth rate to a user-defined mature transition rate, and stage 3 uses perpetual growth with a Gordon terminal value. All equity cash flows are discounted at the cost of equity. No debt is deducted again.

The reverse valuation uses bisection to solve for the **stage-1 growth rate** that makes modeled value equal market price. Calling this an *implied earnings growth rate* assumes constant FCFE/net-income conversion, constant share count, and an unchanged financing policy. It is not a forecast, analyst consensus, or a statistically estimated probability of sustainability. Users compare the implied rate with their own sustainable earnings growth assumption and should corroborate it using historical EPS, reinvestment, ROE, industry growth, and analyst forecasts.

For this version the advanced model requires explicit confirmation of net borrowing when the data provider does not supply it. To use it, ensure cash-flow statement borrowing data is available; do not treat missing data as zero. Negative FCFE and financial firms require separate models. The growth solver searches -95% to +300% and reports when no root is bracketed. Forecast tables are downloadable as CSV.

Run: `python -m pip install -r requirements.txt` and `python -m streamlit run app.py`. Run tests: `python -m pytest tests -q`.

## Version 1.3: Equity research PDF

After entering a ticker, review the FCFE components and verify net borrowing. The bottom of the dashboard now generates a nine-page equity research PDF (cover plus eight analysis sections). It includes valuation, three-stage FCFE forecast, reverse-implied growth, ROE x retention screening, risk metrics, scenario analysis, assumptions, and disclosures. Requires `reportlab` (included in requirements). This is a model-generated research draft, not an audited analyst report. The vendor's quarterly earnings-growth field is not a multi-year EPS CAGR and analyst consensus is not retrieved. Incomplete FCFE inputs block the report.

Run: `python -m pip install -r requirements.txt` then `python -m streamlit run app.py`.
Tests: `PYTHONPATH=. python -m pytest -q`.

## Version 1.4: SEC and comparables

The new **SEC filings, earnings growth, analyst estimates & peers** dashboard adds:
- Official SEC companyfacts lookup by ticker (10-K annual XBRL tags), with user-supplied SEC-compliant User-Agent containing an email address. No API key required.
- Annual EPS, revenue, net income, equity, CFO, capex, ROE using average book equity, and 3-year diluted EPS CAGR when comparable positive endpoints exist.
- Unofficial Yahoo Finance analyst forward EPS and price-target summary; values are not guaranteed to be current or true multi-year consensus forecasts.
- User-selected peers, valuation multiples and an indicative peer-multiple price, with clear caveats.
- When these optional data have been retrieved before generating the report, SEC history and peer/analyst pages are appended to the PDF.

**Workflow:** Enter ticker > Analyze stock > open V1.4 section > enter an SEC request identity (e.g. `Research Example research@example.com`) > retrieve SEC facts > retrieve peer multiples > return to report download button. For live data the app needs outbound internet access; if unavailable, it reports errors rather than inventing data. SEC facts are annual US GAAP XBRL and coverage is incomplete for some issuers. Review all fiscal-year tags and amended filings before relying on results. This is not a licensed institutional analyst-estimate feed.


## V1.5 SEC alignment and ETF routing
- SEC annual facts are keyed by XBRL period-end date, **not** the filing's `fy`, which can refer to a later filing containing comparative periods. Annual duration must be 330-380 days. Fiscal year display uses the end-date calendar year and includes an explicit Period end column; confirm fiscal-year naming against the original filing.
- ETF and mutual-fund quote types are routed to a dedicated fund screen, bypassing operating-company FCFE/DDM, earnings and Company Facts research. The ETF screen provides price, reported NAV (when available), premium/discount, historical volatility, drawdown, and tracking error relative to SPY (which may be an inappropriate benchmark).
- Fund NAV and expense-ratio fields are unofficial and may be missing or stale. This is not a verified daily NAV feed or a holdings-level NAV valuation.
- Run `python -m pytest tests -q` and `python -m streamlit run app.py`. Live provider access is not certified by offline tests.
