"""Run real-data smoke tests locally; never substitute synthetic values for live results."""
import argparse, csv, os
from datetime import datetime, timezone
from data import get_stock, extract_fcfe_components
from sec_research import fetch_companyfacts, historical_table, eps_cagr

TICKERS=['SPCX','BE','TSLA','AAPL','MSFT']
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--sec-user-agent',default=os.getenv('SEC_USER_AGENT',''))
    p.add_argument('--output',default='ticker_validation_results.csv')
    args=p.parse_args()
    rows=[]
    for ticker in TICKERS:
        row={'ticker':ticker,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'asset_class':'ETF' if ticker=='SPCX' else 'Operating company','market_status':'NOT TESTED','sec_status':'NOT TESTED','fcfe_status':'NOT TESTED','eps_cagr_3y':'','notes':''}
        try:
            info,hist,market,cf,bs=get_stock(ticker)
            row['market_status']='PASS' if len(hist)>30 else 'INSUFFICIENT HISTORY'
            kind=info.get('quoteType','')
            if kind and kind.upper() in ('ETF','MUTUALFUND','FUND'):
                row['asset_class']='ETF';row['fcfe_status']='NOT APPLICABLE'
            else:
                parts=extract_fcfe_components(cf)
                row['fcfe_status']='INPUTS PRESENT' if all(parts[k] is not None for k in ('cfo','capex','net_borrowing')) else 'REQUIRES VERIFIED BORROWING/CASHFLOW'
            row['notes']=f"Yahoo type: {kind}; history rows: {len(hist)}"
        except Exception as exc: row['market_status']='FAILED';row['notes']='Market retrieval: '+str(exc)[:180]
        if ticker=='SPCX': row['sec_status']='NOT APPLICABLE (ETF companyfacts)'
        elif not args.sec_user_agent: row['sec_status']='SKIPPED: supply SEC_USER_AGENT with contact email'
        else:
            try:
                facts=fetch_companyfacts(ticker,args.sec_user_agent)
                df,_=historical_table(facts)
                row['sec_status']=f'RETRIEVED ({len(df)} fiscal-year rows)'
                cagr=eps_cagr(df)
                if cagr is not None: row['eps_cagr_3y']=f'{cagr:.6f}'
            except Exception as exc: row['sec_status']='FAILED: '+str(exc)[:160]
        rows.append(row)
        print(ticker, row['market_status'],row['sec_status'],row['fcfe_status'])
    with open(args.output,'w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print('Saved',args.output)
if __name__=='__main__': main()
