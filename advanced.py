"""Three-stage equity cash flow valuation and reverse-implied growth."""
import math

def three_stage_fcfe(fcfe0, shares, ke, high_growth, transition_growth, stable_growth, high_years=5, transition_years=5, payout_conversion=1.0):
    """Discount FCFE to equity. Transition growth linearly converges to transition_growth.
    payout_conversion is normalized FCFE / earnings (fixed), used in reverse earnings-growth analysis.
    """
    values=(fcfe0,shares,ke,high_growth,transition_growth,stable_growth,payout_conversion)
    if not all(math.isfinite(float(x)) for x in values): raise ValueError('All inputs must be finite.')
    if fcfe0<=0 or shares<=0 or payout_conversion<=0: raise ValueError('Positive normalized FCFE, shares and conversion ratio required.')
    if high_years<1 or transition_years<1 or high_years+transition_years>40: raise ValueError('Invalid forecast horizon.')
    if ke<=stable_growth or ke<=-1 or any(g<=-1 for g in (high_growth,transition_growth,stable_growth)):
        raise ValueError('Cost of equity must exceed terminal growth; all growth rates must exceed -100%.')
    cash=fcfe0; pv=0; forecast=[]
    for year in range(1,high_years+transition_years+1):
        if year<=high_years: growth=high_growth
        else:
            fraction=(year-high_years)/transition_years
            growth=high_growth+(transition_growth-high_growth)*fraction
        cash*=1+growth
        discounted=cash/(1+ke)**year
        pv+=discounted
        forecast.append({'Year':year,'Growth':growth,'FCFE':cash,'Present value':discounted})
    terminal=cash*(1+stable_growth)/(ke-stable_growth)
    terminal_pv=terminal/(1+ke)**len(forecast)
    value=(pv+terminal_pv)/shares
    return {'per_share':value,'equity_value':pv+terminal_pv,'terminal_fraction':terminal_pv/(pv+terminal_pv),'forecast':forecast,'terminal_value':terminal,'pv_terminal':terminal_pv}

def implied_earnings_growth(price, fcfe0, shares, ke, transition_growth, stable_growth, high_years=5, transition_years=5, low=-0.95, high=3.0):
    """Solve constant initial EPS growth assuming constant FCFE/EPS conversion and share count.
    Bracket bisection: returns None when observed price is outside model bounds.
    """
    if not math.isfinite(price) or price<=0: raise ValueError('Positive market price required.')
    def residual(g): return three_stage_fcfe(fcfe0,shares,ke,g,transition_growth,stable_growth,high_years,transition_years)['per_share']-price
    a,b=low,high
    fa,fb=residual(a),residual(b)
    if fa>0 or fb<0: return None
    for _ in range(110):
        m=(a+b)/2
        fm=residual(m)
        if fm<0: a=m
        else: b=m
    return (a+b)/2
