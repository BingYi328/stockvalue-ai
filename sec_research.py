"""SEC companyfacts research: no invented data; missing values stay missing."""
import math
import requests
import pandas as pd

BASE='https://data.sec.gov'
TICKERS='https://www.sec.gov/files/company_tickers.json'

def _get(url, user_agent):
    if not user_agent or '@' not in user_agent:
        raise ValueError('Provide a descriptive SEC User-Agent with a contact email.')
    r=requests.get(url,headers={'User-Agent':user_agent,'Accept-Encoding':'gzip, deflate','Host':url.split('/')[2]},timeout=25)
    r.raise_for_status()
    return r.json()

def cik_for_ticker(ticker,user_agent):
    data=_get(TICKERS,user_agent)
    for item in data.values():
        if item['ticker'].upper()==ticker.upper(): return str(item['cik_str']).zfill(10)
    raise ValueError('Ticker not found in SEC ticker mapping.')

def fetch_companyfacts(ticker,user_agent):
    cik=cik_for_ticker(ticker,user_agent)
    return _get(f'{BASE}/api/xbrl/companyfacts/CIK{cik}.json',user_agent)

TAGS={
 'Revenue':['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet'],
 'Net income':['NetIncomeLoss'],
 'EPS diluted':['EarningsPerShareDiluted'],
 'Equity':['StockholdersEquity'],
 'Operating cash flow':['NetCashProvidedByUsedInOperatingActivities'],
 'Capital expenditures':['PaymentsToAcquirePropertyPlantAndEquipment'],
}
def annual_series(facts,tags,unit):
    """Align annual XBRL values by the period END, never the filing's fy.

    Comparative figures in a later 10-K often carry the later filing fiscal
    year. Their end date identifies the actual observation year.
    """
    gaap=facts.get('facts',{}).get('us-gaap',{})
    combined={}; tag_used={}
    for tag in tags:
        for x in gaap.get(tag,{}).get('units',{}).get(unit,[]):
            if x.get('form') not in ('10-K','10-K/A') or not x.get('end'): continue
            try:
                end=pd.Timestamp(x['end']); filed=pd.Timestamp(x['filed'])
                if x.get('start'):
                    days=(end-pd.Timestamp(x['start'])).days
                    if not 330<=days<=380: continue
                elif tag!='StockholdersEquity': continue
                # Prefer explicitly framed annual periods where present; dates
                # still determine the actual fiscal period of the fact.
                year=end.year
                priority=(filed, x.get('accn',''))
                key=(year,end.strftime('%Y-%m-%d'))
                if key not in combined or priority>combined[key][0]:
                    combined[key]=(priority,float(x['val']),tag)
            except (KeyError,TypeError,ValueError,OverflowError): continue
    # For each end-calendar-year, prefer the latest reported period end;
    # this avoids merging an issuer's fiscal-year end with a short transition.
    out={}; sources={}; periods={}
    for (year,end), (priority,value,tag) in combined.items():
        if year not in out or (end,priority)>(periods[year],out[year][0]):
            out[year]=(priority,value);sources[year]=tag;periods[year]=end
    return {y:v[1] for y,v in out.items()},sources,periods

def historical_table(facts):
    series={}; sources={}; periods={}
    for name,tags in TAGS.items():
        s,src,ends=annual_series(facts,tags,'USD/shares' if name=='EPS diluted' else 'USD')
        series[name]=s;sources[name]=src;periods[name]=ends
    years=sorted(set().union(*(set(x) for x in series.values())))
    df=pd.DataFrame({'Fiscal year':years})
    for name,s in series.items(): df[name]=df['Fiscal year'].map(s)
    # Explicitly disclose dates: fiscal-year labels are based on period-end
    # calendar year and may not equal the issuer's named fiscal year.
    df['Period end']=[periods['Net income'].get(y) or periods['Revenue'].get(y) or periods['Equity'].get(y) for y in years]
    eq=series['Equity'];ni=series['Net income']
    df['ROE (avg equity)']=[ni[y]/((eq[y]+eq[y-1])/2) if y in ni and y in eq and y-1 in eq and (eq[y]+eq[y-1])>0 else float('nan') for y in years]
    df['EPS YoY growth']=[(series['EPS diluted'][y]/series['EPS diluted'][y-1]-1) if y in series['EPS diluted'] and y-1 in series['EPS diluted'] and series['EPS diluted'][y-1]>0 else float('nan') for y in years]
    return df,sources

def eps_cagr(df,years=3):
    valid=df[['Fiscal year','EPS diluted']].dropna().sort_values('Fiscal year')
    if len(valid)<years+1: return None
    end=valid.iloc[-1]; start=valid[valid['Fiscal year']==end['Fiscal year']-years]
    if start.empty or float(start.iloc[0]['EPS diluted'])<=0 or float(end['EPS diluted'])<=0: return None
    return (float(end['EPS diluted'])/float(start.iloc[0]['EPS diluted']))**(1/years)-1

def analyst_summary(info):
    # Provider summary fields, NOT verified sell-side consensus; timestamps often absent.
    keys=['forwardEps','trailingEps','earningsGrowth','revenueGrowth','targetMeanPrice','targetLowPrice','targetHighPrice','numberOfAnalystOpinions']
    return {k:info.get(k) for k in keys}

def peer_table(tickers,loader):
    rows=[]
    for ticker in tickers:
        try:
            info=loader(ticker)
            rows.append({'Ticker':ticker,'Company':info.get('shortName') or ticker,'Sector':info.get('sector'),'Industry':info.get('industry'),
                         'Trailing P/E':info.get('trailingPE'),'Forward P/E':info.get('forwardPE'),'P/B':info.get('priceToBook'),
                         'EV/EBITDA':info.get('enterpriseToEbitda'),'ROE':info.get('returnOnEquity'),'Operating margin':info.get('operatingMargins'),
                         'Market cap':info.get('marketCap'),'Status':'Available'})
        except Exception as exc:
            rows.append({'Ticker':ticker,'Status':f'Unavailable: {str(exc)[:90]}'})
    return pd.DataFrame(rows)
