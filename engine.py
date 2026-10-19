import math
import numpy as np
import pandas as pd


def dcf_per_share(fcf, growth, discount, terminal_growth, years, net_debt, shares):
    if not all(math.isfinite(float(v)) for v in (fcf,growth,discount,terminal_growth,net_debt,shares)):
        raise ValueError('All inputs must be finite.')
    if shares <= 0 or years < 1 or years > 30 or discount <= terminal_growth or discount <= -1 or growth <= -1:
        raise ValueError('Check shares, forecast years, discount rate and terminal growth (discount must exceed terminal growth).')
    if fcf <= 0:
        raise ValueError('Positive normalized free cash flow is required for this DCF model.')
    cashflows = [fcf * (1+growth)**t for t in range(1, years+1)]
    pv_stage = sum(cf/(1+discount)**t for t,cf in enumerate(cashflows,1))
    terminal = cashflows[-1]*(1+terminal_growth)/(discount-terminal_growth)
    pv_terminal = terminal/(1+discount)**years
    equity = pv_stage+pv_terminal-net_debt
    return {'per_share': equity/shares, 'enterprise_value':pv_stage+pv_terminal, 'equity_value':equity,
            'terminal_fraction':pv_terminal/(pv_stage+pv_terminal), 'cashflows':cashflows}


def gordon(dividend, required_return, growth):
    if dividend <= 0 or required_return <= growth or growth <= -1:
        raise ValueError('Requires positive annual dividend and required return greater than growth.')
    return dividend*(1+growth)/(required_return-growth)


def risk_metrics(stock_close, market_close, rf=0.04):
    prices = pd.concat([stock_close.rename('stock'), market_close.rename('market')],axis=1).dropna()
    rets = prices.pct_change().dropna()
    if len(rets) < 60: raise ValueError('At least 60 aligned daily return observations are required.')
    s,m = rets.stock,rets.market
    variance = m.var()
    beta = s.cov(m)/variance if variance>0 else float('nan')
    ann_return = (prices.stock.iloc[-1]/prices.stock.iloc[0])**(252/len(rets))-1 if prices.stock.iloc[0]>0 else float('nan')
    vol = s.std()*math.sqrt(252)
    sharpe = (s.mean()*252-rf)/vol if vol>0 else float('nan')
    wealth = (1+s).cumprod()
    drawdown = (wealth/wealth.cummax()-1).min()
    return {'beta':beta,'annualized_price_return':ann_return,'volatility':vol,'sharpe':sharpe,
            'max_drawdown':drawdown,'historical_var_95':-s.quantile(0.05),
            'market_return_annualized':(prices.market.iloc[-1]/prices.market.iloc[0])**(252/len(rets))-1,
            'n_returns':len(rets)}


def fcfe_from_components(cfo, capex, net_borrowing):
    if any(x is None or not math.isfinite(float(x)) for x in (cfo,capex,net_borrowing)):
        raise ValueError('CFO, capital expenditure, and net borrowing are required.')
    if capex < 0: raise ValueError('Enter capital expenditure as a positive outflow.')
    return cfo-capex+net_borrowing

def fcfe_per_share(fcfe, growth, cost_of_equity, terminal_growth, years, shares):
    result=dcf_per_share(fcfe,growth,cost_of_equity,terminal_growth,years,0,shares)
    return {'per_share':result['per_share'],'equity_value':result['equity_value'],
            'terminal_fraction':result['terminal_fraction'],'cashflows':result['cashflows']}
