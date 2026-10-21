"""Official SEC companyfacts access with explicit user-agent handling."""
import pandas as pd

def fetch_companyfacts(ticker, user_agent):
    try:
        import requests
    except ImportError as exc:
        raise ValueError('Install requests to retrieve official SEC data.') from exc
    if not user_agent or '@' not in user_agent: raise ValueError('Provide an application name and contact email in SEC_USER_AGENT.')
    headers={'User-Agent':user_agent}; tickers=requests.get('https://www.sec.gov/files/company_tickers.json',headers=headers,timeout=20).json()
    match=next((row for row in tickers.values() if str(row.get('ticker','')).upper()==str(ticker).upper()),None)
    if not match: raise ValueError(f'Could not find SEC CIK for {ticker}.')
    cik=str(match['cik_str']).zfill(10)
    response=requests.get(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json',headers=headers,timeout=20); response.raise_for_status(); return response.json()

def historical_table(facts):
    usgaap=facts.get('facts',{}).get('us-gaap',{}); rows={}
    tags={'Revenue':['Revenues','RevenueFromContractWithCustomerExcludingAssessedTax'],'Net income':['NetIncomeLoss'],'EPS diluted':['EarningsPerShareDiluted'],'Assets':['Assets'],'Equity':['StockholdersEquity']}
    sources={}
    for label,candidates in tags.items():
        for tag in candidates:
            units=usgaap.get(tag,{}).get('units',{}); unit=next(iter(units),None)
            if unit:
                for item in units[unit]:
                    if item.get('fp')=='FY' and item.get('form') in {'10-K','20-F'} and item.get('fy'):
                        year=int(item['fy']); rows.setdefault(year,{'Fiscal year':year})[label]=item.get('val'); sources[label]=tag
                if any(label in row for row in rows.values()): break
    return pd.DataFrame([rows[y] for y in sorted(rows)]),sources

def eps_cagr(table, years=3):
    if table is None or table.empty or 'EPS diluted' not in table: return None
    data=table[['Fiscal year','EPS diluted']].dropna().sort_values('Fiscal year'); data=data[data['EPS diluted']>0]
    if len(data)<2: return None
    end=data.iloc[-1]; candidates=data[data['Fiscal year']<=end['Fiscal year']-years]
    if candidates.empty: return None
    start=candidates.iloc[-1]; return float((end['EPS diluted']/start['EPS diluted'])**(1/(end['Fiscal year']-start['Fiscal year']))-1)

def analyst_summary(info):
    return {key:info.get(key) for key in ('trailingEps','forwardEps','earningsGrowth','revenueGrowth','targetMeanPrice','numberOfAnalystOpinions')}

def peer_table(symbols, getter):
    rows=[]
    for symbol in symbols:
        try:
            info=getter(symbol); rows.append({'Ticker':symbol,'Name':info.get('shortName') or info.get('longName'),'Trailing P/E':info.get('trailingPE'),'Market cap':info.get('marketCap'),'Revenue growth':info.get('revenueGrowth')})
        except Exception: rows.append({'Ticker':symbol,'Name':'Unavailable'})
    return pd.DataFrame(rows)
