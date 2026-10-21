"""ETF detection and basic fund diagnostics."""
import math
import pandas as pd

def security_route(info):
    return 'ETF' if str((info or {}).get('quoteType','')).upper()=='ETF' else 'EQUITY'

def etf_analysis(info, history, market):
    close=pd.to_numeric(history['Close'],errors='coerce').dropna()
    returns=close.pct_change().dropna()
    wealth=(1+returns).cumprod(); drawdown=wealth/wealth.cummax()-1
    nav=info.get('navPrice')
    price=float(close.iloc[-1])
    return {'price':price,'nav':float(nav) if isinstance(nav,(int,float)) else None,'premium_discount':(price/float(nav)-1) if isinstance(nav,(int,float)) and nav else None,'volatility':float(returns.std()*math.sqrt(252)) if len(returns)>1 else None,'max_drawdown':float(drawdown.min()) if len(drawdown) else float('nan'),'assets':info.get('totalAssets'),'expense_ratio':info.get('annualReportExpenseRatio'),'tracking_error_annualized':None}
