import math
import pandas as pd


def get_stock(ticker):
    import yfinance as yf
    ticker=ticker.strip().upper()
    if not ticker or len(ticker)>16 or not all(c.isalnum() or c in '.-^' for c in ticker):
        raise ValueError('Enter a valid ticker symbol.')
    obj=yf.Ticker(ticker)
    info=obj.info or {}
    history=obj.history(period='5y', auto_adjust=True)
    if history.empty: raise ValueError('No historical prices found for this ticker.')
    market=yf.Ticker('SPY').history(period='5y', auto_adjust=True)
    if market.empty: raise ValueError('Could not load SPY benchmark data.')
    cashflow=obj.cashflow
    balance=obj.balance_sheet
    income=getattr(obj,'income_stmt',pd.DataFrame())
    return info, history, market, cashflow, balance, income


def find_latest(frame, labels):
    if frame is None or frame.empty: return None
    for label in labels:
        if label in frame.index:
            values=pd.to_numeric(frame.loc[label],errors='coerce').dropna()
            if len(values): return float(values.iloc[0])
    return None


def extract_fcf(info, cashflow):
    fcf=info.get('freeCashflow')
    if isinstance(fcf,(int,float)) and fcf>0: return float(fcf),'Yahoo Finance company summary (freeCashflow)'
    fcf=find_latest(cashflow,['Free Cash Flow'])
    if fcf is not None: return fcf,'Latest available annual cash flow statement'
    operating=find_latest(cashflow,['Operating Cash Flow','Cash Flow From Continuing Operating Activities'])
    capex=find_latest(cashflow,['Capital Expenditure'])
    if operating is not None and capex is not None:
        return operating+capex,'Operating cash flow plus signed capital expenditures'
    return None,'Unavailable'


def extract_fcfe_components(cashflow):
    """Annual CFO, positive capex outlay, and net debt issuance; missing borrowing stays missing."""
    cfo=find_latest(cashflow,['Operating Cash Flow','Cash Flow From Continuing Operating Activities'])
    capex=find_latest(cashflow,['Capital Expenditure','Capital Expenditures'])
    issuance=find_latest(cashflow,['Issuance Of Debt','Issuance of Debt','Long Term Debt Issuance','Long Term Debt Issuance Net'])
    repayment=find_latest(cashflow,['Repayment Of Debt','Repayment of Debt','Long Term Debt Payments'])
    net=find_latest(cashflow,['Net Issuance Payments Of Debt','Net Debt Issuance'])
    if net is not None: borrowing=net; source='Reported net debt issuance'
    elif issuance is not None and repayment is not None:
        borrowing=issuance-abs(repayment); source='Debt issuance less debt repayments'
    else: borrowing=None; source='Net borrowing unavailable: manual entry required'
    return {'cfo':cfo,'capex':abs(capex) if capex is not None else None,
            'net_borrowing':borrowing,'borrowing_source':source}


def _cagr_from_series(values, periods):
    """Return CAGR, years used, latest EPS, start EPS, and endpoint dates."""
    valid=[]
    for period,value in zip(periods,values):
        try:
            value=float(value)
            if math.isfinite(value) and value>0:
                valid.append((pd.Timestamp(period),value))
        except (TypeError,ValueError):
            continue
    valid=sorted(valid,key=lambda x:x[0])
    if len(valid)<2: return None
    end_date,end_eps=valid[-1]
    for years in (10,5,3):
        target=end_date-pd.DateOffset(years=years)
        candidates=[item for item in valid if item[0].year==target.year]
        if candidates:
            start_date,start_eps=candidates[-1]
            actual_years=(end_date-start_date).days/365.25
            if years-0.25<=actual_years<=years+0.25:
                return (end_eps/start_eps)**(1/years)-1,years,end_eps,start_eps,start_date,end_date
    return None


def estimate_eps_growth(income_stmt=None, sec_table=None):
    """Estimate recent annual diluted-EPS growth using 10-, 5-, or 3-year data."""
    if sec_table is not None and not sec_table.empty and 'EPS diluted' in sec_table.columns:
        result=_cagr_from_series(sec_table['EPS diluted'].tolist(),sec_table['Fiscal year'].tolist())
        if result:
            return (*result,'SEC annual diluted EPS')
    if income_stmt is not None and not income_stmt.empty:
        for label in ('Diluted EPS','Basic EPS','Diluted EPS Continuing Operations','Basic EPS Continuing Operations'):
            if label in income_stmt.index:
                result=_cagr_from_series(income_stmt.loc[label].tolist(),income_stmt.columns.tolist())
                if result:
                    return (*result,f'Yahoo Finance annual {label}')
    return None
