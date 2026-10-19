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
    return info, history, market, cashflow, balance


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
