"""Multi-stage FCFE helpers."""
from engine import fcfe_per_share

def three_stage_fcfe(fcfe, shares, cost_of_equity, high_growth, mature_growth, stable_growth, high_years, fade_years):
    if fcfe<=0 or shares<=0 or cost_of_equity<=stable_growth: raise ValueError('Invalid three-stage FCFE assumptions.')
    values=[]; pv=0.0; current=fcfe
    for year in range(1,int(high_years)+1):
        current*=1+high_growth; value=current/(1+cost_of_equity)**year; pv+=value
        values.append({'Year':year,'Growth':high_growth,'FCFE':current,'Present value':value})
    for step in range(1,int(fade_years)+1):
        growth=high_growth+(mature_growth-high_growth)*step/fade_years
        current*=1+growth; year=high_years+step; value=current/(1+cost_of_equity)**year; pv+=value
        values.append({'Year':year,'Growth':growth,'FCFE':current,'Present value':value})
    terminal=current*(1+stable_growth)/(cost_of_equity-stable_growth)
    pv_terminal=terminal/(1+cost_of_equity)**(high_years+fade_years)
    return {'per_share':(pv+pv_terminal)/shares,'terminal_fraction':pv_terminal/(pv+pv_terminal),'forecast':values}

def implied_earnings_growth(price, fcfe, shares, cost_of_equity, mature_growth, stable_growth, high_years, fade_years):
    if price<=0 or fcfe<=0 or shares<=0: return None
    low,high=-.95,3.0
    target=price*shares
    for _ in range(80):
        mid=(low+high)/2
        value=three_stage_fcfe(fcfe,shares,cost_of_equity,mid,mature_growth,stable_growth,high_years,fade_years)['per_share']
        if value<price: low=mid
        else: high=mid
    return (low+high)/2 if abs(three_stage_fcfe(fcfe,shares,cost_of_equity,(low+high)/2,mature_growth,stable_growth,high_years,fade_years)['per_share']-price)<max(.01,price*.01) else None
