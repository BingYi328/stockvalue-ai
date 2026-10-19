"""ETF-specific analytics. Never apply company FCFE or DDM to a fund."""
import math
import pandas as pd

def security_route(info):
    kind=str(info.get('quoteType') or '').upper()
    return 'ETF' if kind in ('ETF','MUTUALFUND','FUND') else 'OPERATING_COMPANY'

def etf_analysis(info, history, benchmark=None):
    if security_route(info)!='ETF': raise ValueError('ETF analytics require a fund security.')
    prices=pd.to_numeric(history['Close'],errors='coerce').dropna()
    if prices.empty: raise ValueError('ETF price history unavailable')
    price=float(prices.iloc[-1]); nav=info.get('navPrice')
    try: nav=float(nav) if nav is not None and math.isfinite(float(nav)) and float(nav)>0 else None
    except (TypeError,ValueError): nav=None
    premium=(price/nav-1) if nav else None
    ret=prices.pct_change().dropna()
    volatility=float(ret.std()*math.sqrt(252)) if len(ret)>2 else None
    drawdown=float((prices/prices.cummax()-1).min())
    result={'price':price,'nav':nav,'premium_discount':premium,'volatility':volatility,'max_drawdown':drawdown,
            'expense_ratio':info.get('annualReportExpenseRatio') or info.get('totalExpenseRatio'),
            'assets':info.get('totalAssets'),'yield':info.get('yield'),'holdings':info.get('holdings'),
            'nav_source':'Yahoo Finance summary (may be stale or unavailable)'}
    if benchmark is not None and not benchmark.empty:
        aligned=pd.concat([prices.rename('fund'),benchmark['Close'].rename('benchmark')],axis=1).dropna()
        if len(aligned)>3:
            daily=aligned.pct_change().dropna()
            result['tracking_difference_annualized']=float((daily['fund']-daily['benchmark']).mean()*252)
            result['tracking_error_annualized']=float((daily['fund']-daily['benchmark']).std()*math.sqrt(252))
    return result
