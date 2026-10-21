"""Small, transparent valuation and risk helpers used by app.py."""
import math
import numpy as np
import pandas as pd

def _validate_rate(rate, name):
    if not math.isfinite(float(rate)):
        raise ValueError(f'{name} must be finite.')

def dcf_per_share(cash_flow, growth, discount_rate, terminal_growth, years, net_debt, shares):
    _validate_rate(discount_rate,'Discount rate'); _validate_rate(terminal_growth,'Terminal growth')
    if shares <= 0 or cash_flow <= 0 or years < 1 or discount_rate <= terminal_growth:
        raise ValueError('DCF requires positive cash flow and shares, and discount rate above terminal growth.')
    pv=sum(cash_flow*(1+growth)**year/(1+discount_rate)**year for year in range(1,int(years)+1))
    terminal=cash_flow*(1+growth)**years*(1+terminal_growth)/(discount_rate-terminal_growth)
    pv_terminal=terminal/(1+discount_rate)**years
    enterprise=pv+pv_terminal
    return {'enterprise_value':enterprise,'equity_value':enterprise-net_debt,'per_share':(enterprise-net_debt)/shares,'terminal_fraction':pv_terminal/enterprise}

def fcfe_from_components(cfo, capex, net_borrowing):
    if any(value is None or not math.isfinite(float(value)) for value in (cfo,capex,net_borrowing)):
        raise ValueError('FCFE requires operating cash flow, capex, and net borrowing.')
    return float(cfo)-abs(float(capex))+float(net_borrowing)

def fcfe_per_share(fcfe, growth, cost_of_equity, terminal_growth, years, shares):
    if shares <= 0 or fcfe <= 0 or cost_of_equity <= terminal_growth:
        raise ValueError('FCFE requires positive FCFE and shares, and cost of equity above terminal growth.')
    pv=sum(fcfe*(1+growth)**year/(1+cost_of_equity)**year for year in range(1,int(years)+1))
    terminal=fcfe*(1+growth)**years*(1+terminal_growth)/(cost_of_equity-terminal_growth)
    pv_terminal=terminal/(1+cost_of_equity)**years
    return {'equity_value':pv+pv_terminal,'per_share':(pv+pv_terminal)/shares,'terminal_fraction':pv_terminal/(pv+pv_terminal)}

def gordon(dividend, cost_of_equity, growth):
    if dividend <= 0 or cost_of_equity <= growth:
        raise ValueError('Gordon model requires a positive dividend and cost of equity above growth.')
    return dividend*(1+growth)/(cost_of_equity-growth)

def risk_metrics(stock_close, benchmark_close, risk_free_rate=0.0):
    aligned=pd.concat([pd.Series(stock_close,name='stock'),pd.Series(benchmark_close,name='market')],axis=1).dropna()
    returns=aligned.pct_change().dropna(); stock=returns['stock']; market=returns['market']
    if len(stock)<2 or market.var()==0: raise ValueError('Insufficient aligned price history for risk metrics.')
    beta=float(stock.cov(market)/market.var()); volatility=float(stock.std()*math.sqrt(252)); annual=float((1+stock.mean())**252-1)
    sharpe=float((stock.mean()*252-risk_free_rate)/(stock.std()*math.sqrt(252))) if stock.std() else float('nan')
    wealth=(1+stock).cumprod(); drawdown=wealth/wealth.cummax()-1
    return {'beta':beta,'volatility':volatility,'annualized_price_return':annual,'sharpe':sharpe,'max_drawdown':float(drawdown.min()),'historical_var_95':float(stock.quantile(.05)),'n_returns':len(stock)}
