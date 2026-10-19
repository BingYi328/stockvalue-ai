# StockValue AI V1.4 - five-ticker validation audit

Date: 2026-10-18. Requested symbols: SPCX, BE, TSLA, APPL, MSFT. Corrected APPL to AAPL.

## Actual test results
- Existing unit/regression suite: **18 passed** (`PYTHONPATH=. python -m pytest -q`). These tests are primarily synthetic/mocked and do not verify live feeds.
- Outbound Yahoo Finance request: **FAILED** (DNS/network unavailable in execution environment).
- Outbound SEC Company Facts request: **FAILED** (DNS/network unavailable in execution environment).
- Therefore, live financial statements, EPS history, analyst forecasts, market prices, intrinsic values, peer prices, and downloadable ticker-specific reports are **NOT VALIDATED**.

## Security-specific applicability
- **SPCX:** SPAC-focused ETF. Company-level FCFE/DDM and SEC issuer companyfacts are inappropriate for fund NAV analysis. Current app needs ETF routing and holdings/NAV data.
- **BE:** Bloom Energy. Requires inspection of cash burn, capex, financing flows, dilution and whether normalized FCFE is positive. No reliable intrinsic value without verification.
- **TSLA:** Tesla. Validate volatile capex, debt issuance/repayments, dilution, and terminal value dependence. Reverse-implied growth is conditional on FCFE/EPS conversion.
- **AAPL:** Apple (user typed APPL). Check fiscal-year alignment, repurchases/share-count changes, dividends, and ROE distorted by low book equity.
- **MSFT:** Microsoft. Verify fiscal-year alignment, capex, stock compensation, cash flows, and peer selection.

## Methodology issues observed in code
1. SEC `annual_series` groups facts by reported `fy` and latest filed date; comparative fiscal-year contexts may be assigned to a different year. Reconcile `end`, `start`, `frame`, `fy`, `fp`, and filing accession before production use.
2. The current app uses a Yahoo summary of analyst targets, not a verified historical or forward consensus dataset with forecast dates.
3. The current peer group is user-selected; sector/industry matching and multiple normalization are not automatic.
4. The current FCFE model refuses non-positive normalized FCFE, appropriate as a safeguard but not sufficient for BE/TSLA in every period.
5. A 10-page synthetic PDF demonstrates layout, not live end-to-end reporting.

## Run the real-data checks on an internet-connected machine
From the application directory:

```
python -m pip install -r requirements.txt
python validate_tickers.py --sec-user-agent "StockValue Research your-email@example.com"
```

Replace the example email with your own. Review `ticker_validation_results.csv`. Avoid publishing private keys or contact details in shared reports. Live financial conclusions require review of the underlying 10-K filings and vendor data.
