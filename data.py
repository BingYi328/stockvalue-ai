import math
import pandas as pd


def resolve_ticker(query):
    """Resolve a ticker or company name to a Yahoo Finance symbol."""
    import yfinance as yf
    query=str(query or '').strip()
    if not query:
        raise ValueError('Enter a company name or ticker symbol.')
    candidate=query.upper()
    valid_candidate=len(candidate)<=16 and all(c.isalnum() or c in '.-^' for c in candidate)
    try:
        search=yf.Search(query, max_results=8)
        quotes=getattr(search,'quotes',[]) or []
        for quote in quotes:
            symbol=str(quote.get('symbol') or '').upper()
            if symbol==candidate and quote.get('quoteType') in {'EQUITY','ETF'}:
                return symbol
        for quote in quotes:
            symbol=quote.get('symbol')
            if symbol and quote.get('quoteType') in {'EQUITY','ETF'}:
                return str(symbol).upper()
    except Exception:
        pass
    if valid_candidate:
        return candidate
    raise ValueError(f'Could not resolve "{query}" to a stock or ETF ticker.')


def get_news_and_dates(ticker):
    """Retrieve recent Yahoo Finance news and available event dates."""
    import yfinance as yf
    obj=yf.Ticker(ticker)
    news=[]
    try:
        for item in (obj.news or [])[:12]:
            content=item.get('content',item) if isinstance(item,dict) else {}
            title=content.get('title') or item.get('title')
            provider=(content.get('provider') or {}).get('displayName') if isinstance(content.get('provider'),dict) else content.get('publisher') or item.get('publisher')
            link=content.get('clickThroughUrl') or content.get('canonicalUrl') or {}
            if isinstance(link,dict): link=link.get('url')
            timestamp=content.get('pubDate') or item.get('providerPublishTime')
            if isinstance(timestamp,(int,float)):
                timestamp=pd.to_datetime(timestamp,unit='s',utc=True)
            else:
                timestamp=pd.to_datetime(timestamp,utc=True,errors='coerce')
            if title:
                news.append({'Headline':title,'Publisher':provider or 'Yahoo Finance','Published':timestamp,'Link':link or ''})
    except Exception:
        news=[]
    news_df=pd.DataFrame(news)
    if not news_df.empty:
        news_df=news_df.sort_values('Published',ascending=False,na_position='last').reset_index(drop=True)
        news_df['Published']=news_df['Published'].map(lambda x:x.strftime('%Y-%m-%d %H:%M UTC') if pd.notna(x) else 'Date unavailable')
    dates=[]
    try:
        calendar=obj.calendar
        if isinstance(calendar,pd.DataFrame):
            for key,value in calendar.items():
                values=value.dropna().tolist() if hasattr(value,'dropna') else [value]
                dates.append({'Event':str(key),'Date':', '.join(str(x) for x in values)})
        elif isinstance(calendar,dict):
            for key,value in calendar.items():
                values=value if isinstance(value,(list,tuple,pd.Series)) else [value]
                dates.append({'Event':str(key),'Date':', '.join(str(x) for x in values)})
    except Exception:
        pass
    try:
        earnings_dates=obj.get_earnings_dates(limit=8)
        if earnings_dates is not None and not earnings_dates.empty:
            for date in earnings_dates.index[:8]:
                dates.append({'Event':'Earnings date','Date':str(pd.Timestamp(date))})
    except Exception:
        pass
    dates_df=pd.DataFrame(dates).drop_duplicates() if dates else pd.DataFrame(columns=['Event','Date'])
    return news_df,dates_df


def technical_indicators(history):
    """Calculate OHLCV technical indicators and current signal warnings."""
    frame=history.copy()
    if frame.empty or not {'Open','High','Low','Close'}.issubset(frame.columns):
        return pd.DataFrame(),[]
    frame=frame[['Open','High','Low','Close','Volume']].dropna().copy()
    frame['MA20']=frame['Close'].rolling(20).mean()
    frame['MA50']=frame['Close'].rolling(50).mean()
    frame['MA200']=frame['Close'].rolling(200).mean()
    frame['BB_Middle']=frame['MA20']
    frame['BB_STD']=frame['Close'].rolling(20).std()
    frame['BB_Upper']=frame['BB_Middle']+2*frame['BB_STD']
    frame['BB_Lower']=frame['BB_Middle']-2*frame['BB_STD']
    delta=frame['Close'].diff()
    gains=delta.clip(lower=0).rolling(14).mean()
    losses=(-delta.clip(upper=0)).rolling(14).mean()
    rs=gains/losses.replace(0,float('nan'))
    frame['RSI14']=100-(100/(1+rs))
    ema12=frame['Close'].ewm(span=12,adjust=False).mean()
    ema26=frame['Close'].ewm(span=26,adjust=False).mean()
    frame['MACD']=ema12-ema26
    frame['MACD_Signal']=frame['MACD'].ewm(span=9,adjust=False).mean()
    frame['MACD_Hist']=frame['MACD']-frame['MACD_Signal']
    signals=[]
    recent=frame.dropna(subset=['MA50','MA200']).tail(2)
    if len(recent)==2:
        prev,curr=recent.iloc[0],recent.iloc[1]
        if prev['MA50']<=prev['MA200'] and curr['MA50']>curr['MA200']:
            signals.append(('warning','Golden cross: the 50-day moving average crossed above the 200-day moving average.'))
        elif prev['MA50']>=prev['MA200'] and curr['MA50']<curr['MA200']:
            signals.append(('warning','Dead cross: the 50-day moving average crossed below the 200-day moving average.'))
    latest=frame.iloc[-1]
    if pd.notna(latest['BB_Upper']) and latest['Close']>latest['BB_Upper']:
        signals.append(('warning','Price broke above the upper Bollinger Band; momentum is strong but the move may be extended.'))
    elif pd.notna(latest['BB_Lower']) and latest['Close']<latest['BB_Lower']:
        signals.append(('warning','Price broke below the lower Bollinger Band; downside momentum is strong but the move may be extended.'))
    if pd.notna(latest['RSI14']):
        if latest['RSI14']>=70: signals.append(('warning',f"RSI is overbought at {latest['RSI14']:.1f}."))
        elif latest['RSI14']<=30: signals.append(('warning',f"RSI is oversold at {latest['RSI14']:.1f}."))
    macd_recent=frame.dropna(subset=['MACD','MACD_Signal']).tail(2)
    if len(macd_recent)==2:
        prev,curr=macd_recent.iloc[0],macd_recent.iloc[1]
        if prev['MACD']<=prev['MACD_Signal'] and curr['MACD']>curr['MACD_Signal']:
            signals.append(('info','MACD bullish crossover.'))
        elif prev['MACD']>=prev['MACD_Signal'] and curr['MACD']<curr['MACD_Signal']:
            signals.append(('warning','MACD bearish crossover.'))
    if len(frame)>=3:
        a,b,c=frame.iloc[-3],frame.iloc[-2],frame.iloc[-1]
        body=max(abs(b['Close']-b['Open']),1e-12)
        morning=(a['Close']<a['Open'] and abs(b['Close']-b['Open'])<=abs(a['Close']-a['Open'])*0.45 and c['Close']>c['Open'] and c['Close']>(a['Open']+a['Close'])/2)
        evening=(a['Close']>a['Open'] and abs(b['Close']-b['Open'])<=abs(a['Close']-a['Open'])*0.45 and c['Close']<c['Open'] and c['Close']<(a['Open']+a['Close'])/2)
        if morning: signals.append(('info','Possible morning star reversal pattern detected.'))
        if evening: signals.append(('warning','Possible evening star reversal pattern detected.'))
    return frame,signals


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
    info=enrich_info_from_statements(info,income,cashflow,balance)
    return info, history, market, cashflow, balance, income


def find_latest(frame, labels):
    if frame is None or frame.empty: return None
    for label in labels:
        if label in frame.index:
            values=pd.to_numeric(frame.loc[label],errors='coerce').dropna()
            if len(values): return float(values.iloc[0])
    return None

def _fill_missing(info,key,frame,labels):
    """Fill a missing Yahoo summary field from an annual statement when possible."""
    current=info.get(key)
    if current is None or not isinstance(current,(int,float)) or not math.isfinite(float(current)):
        value=find_latest(frame,labels)
        if value is not None:
            info[key]=value

def enrich_info_from_statements(info,income,cashflow,balance):
    """Use annual statements as a transparent fallback for incomplete summary data."""
    info=dict(info or {})
    _fill_missing(info,'sharesOutstanding',balance,['Ordinary Shares Number','Share Issued','Common Stock Equity'])
    _fill_missing(info,'totalDebt',balance,['Total Debt','Long Term Debt','Long Term Debt And Capital Lease Obligation','Current Debt'])
    _fill_missing(info,'totalCash',balance,['Cash Cash Equivalents And Short Term Investments','Cash And Cash Equivalents','Cash Financial'])
    _fill_missing(info,'totalRevenue',income,['Total Revenue','Operating Revenue','Revenue'])
    _fill_missing(info,'netIncomeToCommon',income,['Net Income','Net Income Common Stockholders','Net Income Including Noncontrolling Interests'])
    _fill_missing(info,'operatingCashflow',cashflow,['Operating Cash Flow','Cash Flow From Continuing Operating Activities'])
    _fill_missing(info,'freeCashflow',cashflow,['Free Cash Flow'])
    return info


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
                if isinstance(period,(int,float)) and not isinstance(period,bool):
                    period_date=pd.Timestamp(year=int(period),month=12,day=31)
                else:
                    period_date=pd.Timestamp(period)
                valid.append((period_date,value))
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
