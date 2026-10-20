import math
from pathlib import Path
import pandas as pd
import streamlit as st
from engine import dcf_per_share, gordon, risk_metrics, fcfe_per_share, fcfe_from_components
from data import get_stock, extract_fcf, extract_fcfe_components
from advanced import three_stage_fcfe, implied_earnings_growth

st.set_page_config(page_title='StockValue AI',page_icon='📈',layout='wide')
logo_path=Path(__file__).with_name('StockValueAI_logo_improved.png')
if logo_path.exists():
    st.image(str(logo_path),width=150)
st.title('StockValue AI')
st.caption('Educational equity research dashboard | Data: Yahoo Finance via yfinance (unofficial, subject to availability) | Not investment advice')

@st.cache_data(ttl=900,show_spinner=False)
def load_stock_cached(symbol):
    """Cache live market/fundamental data for 15 minutes per ticker."""
    return get_stock(symbol)

@st.cache_data(ttl=900,show_spinner=False)
def load_peer_table_cached(peer_symbols):
    """Cache peer-summary requests for 15 minutes."""
    import yfinance as yf
    return peer_table(list(peer_symbols),lambda x:yf.Ticker(x).info or {})

def secret_text(name,default=''):
    """Read a text secret without embedding credentials in source code."""
    try:
        value=st.secrets.get(name,default)
    except Exception:
        value=default
    return str(value or '').strip()
with st.sidebar:
    ticker=st.text_input('Stock ticker','MSFT').strip().upper()
    load=st.button('Analyze stock',type='primary',use_container_width=True)
    st.markdown('**Model settings**')
    growth=st.number_input('Annual FCF growth (%)',-90.0,100.0,7.0,0.5)/100
    discount=st.number_input('Discount rate / WACC (%)',0.1,60.0,10.0,0.5)/100
    terminal_growth=st.number_input('Terminal growth (%)',-5.0,15.0,2.5,0.5)/100
    years=st.slider('Forecast years',3,15,5)
    rf=st.number_input('Risk-free rate (%)',0.0,25.0,4.0,0.25)/100
    erp=st.number_input('Equity risk premium (%)',0.0,20.0,5.0,0.25)/100
    st.caption('Defaults are illustrative assumptions, not company-specific forecasts.')
if load:
    with st.spinner('Retrieving public market data...'):
        try: st.session_state['result']=(ticker,load_stock_cached(ticker))
        except Exception as exc:
            st.error(f'Live data unavailable: {exc}. Please try another ticker or retry later.')
            st.stop()
if 'result' not in st.session_state:
    st.info('Enter a stock ticker and click **Analyze stock** to retrieve available live financial data.')
    st.stop()
_stored_ticker,_stored_data=st.session_state['result']
if len(_stored_data)==5:
    info,hist,market,cashflow,balance=_stored_data
    income=pd.DataFrame()
else:
    info,hist,market,cashflow,balance,income=_stored_data
ticker=_stored_ticker
from funds import security_route,etf_analysis
if security_route(info)=='ETF':
    st.subheader(f"ETF research: {info.get('longName') or ticker} ({ticker})")
    st.info('ETF detected: operating-company FCFE, DDM, SEC Company Facts earnings, and EPS-based peer valuation are not applicable.')
    try:
        fund=etf_analysis(info,hist,market)
        c1,c2,c3=st.columns(3)
        c1.metric('Latest adjusted price',f"{fund['price']:,.2f}")
        c2.metric('Reported NAV',f"{fund['nav']:,.2f}" if fund['nav'] is not None else 'Unavailable')
        c3.metric('Price / NAV premium',f"{fund['premium_discount']:+.2%}" if fund['premium_discount'] is not None else 'Unavailable')
        st.write('Annualized historical volatility:',f"{fund['volatility']:.2%}" if fund['volatility'] is not None else 'Unavailable')
        st.write('Maximum historical drawdown:',f"{fund['max_drawdown']:.2%}")
        st.write('Reported fund assets:',fund['assets'] if fund['assets'] is not None else 'Unavailable')
        st.write('Reported expense ratio:',fund['expense_ratio'] if fund['expense_ratio'] is not None else 'Unavailable')
        st.write('Tracking error vs SPY:',f"{fund['tracking_error_annualized']:.2%}" if fund.get('tracking_error_annualized') is not None else 'Unavailable')
        st.line_chart(hist['Close'])
        st.warning('NAV may be stale or missing; compare only matched timestamps. SPY may not be the correct ETF benchmark. Verify holdings, fund documents, and expense ratio before investing.')
    except Exception as exc: st.error(f'ETF analysis unavailable: {exc}')
    st.stop()

price=float(hist['Close'].iloc[-1]); currency=info.get('currency','USD')
st.subheader(f"{info.get('longName') or ticker} ({ticker})")
st.caption(f'Latest available adjusted price: {hist.index[-1].date()} | Currency: {currency} | Source: Yahoo Finance (unofficial)')
if currency!='USD': st.warning('Non-USD listing: all financial statement units and quote currencies must be checked for consistency before interpreting the DCF.')

# Visible data-quality checks prevent missing provider fields from being mistaken for verified zeroes.
missing_fields=[]
for label, value in [('Shares outstanding', info.get('sharesOutstanding')), ('Total debt', info.get('totalDebt')), ('Total cash', info.get('totalCash')), ('Revenue', info.get('totalRevenue')), ('Operating cash flow', info.get('operatingCashflow'))]:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        missing_fields.append(label)
with st.expander('Data quality and model warnings', expanded=bool(missing_fields)):
    st.write('**Quote date:**', hist.index[-1].date())
    st.write('**History used:**', f'{len(hist):,} daily observations')
    st.write('**Cash-flow statement columns available:**', f'{len(cashflow.columns) if cashflow is not None and not cashflow.empty else 0}')
    if missing_fields:
        st.warning('Unavailable or non-numeric fields: ' + ', '.join(missing_fields) + '. Missing values are not treated as verified zeroes.')
    else:
        st.success('Core market and operating fields needed by the dashboard are available.')
    st.caption('Provider fields can be stale, restated, differently defined, or reported in a different currency. Review the original filing before relying on any estimate.')
c1,c2,c3,c4=st.columns(4)
c1.metric('Latest adjusted close',f'{price:,.2f} {currency}')
c2.metric('Market capitalization',f"{info['marketCap']/1e9:,.2f}B" if isinstance(info.get('marketCap'),(float,int)) else 'N/A')
c3.metric('Trailing P/E',f"{info['trailingPE']:.1f}" if isinstance(info.get('trailingPE'),(int,float)) else 'N/A')
c4.metric('Dividend yield',f"{info['dividendYield']*100:.2f}%" if isinstance(info.get('dividendYield'),(float,int)) else 'N/A')
valuation,risk,fundamentals,notes=st.tabs(['Intrinsic valuation','Risk & return','Financial fundamentals','Methods & caveats'])
with valuation:
    fcf,fcf_source=extract_fcf(info,cashflow)
    shares=info.get('sharesOutstanding')
    debt=info.get('totalDebt'); cash=info.get('totalCash')
    st.caption(f'FCF source: {fcf_source}. Free cash flow, shares, and net debt can be overridden below.')
    with st.expander('Inspect / override financial inputs',expanded=not(fcf and shares)):
        fcf_b=st.number_input('Normalized annual FCFE or FCFF (billions)',value=float(fcf or 0)/1e9,format='%.4f',help='Use normalized positive FCFF for an enterprise DCF; Yahoo freeCashflow is often a levered/unlevered proxy, so check definitions.')
        shares_b=st.number_input('Shares outstanding (billions)',min_value=0.0,value=float(shares or 0)/1e9,format='%.5f')
        net_debt_b=st.number_input('Net debt (billions: debt minus cash)',value=(float(debt or 0)-float(cash or 0))/1e9,format='%.4f')
    st.warning('Select the appropriate cash-flow basis: FCFE is discounted at cost of equity without subtracting net debt; FCFF is discounted at WACC with net debt deducted. Yahoo freeCashflow is not automatically verified as either measure.')
    basis=st.radio('Cash-flow basis', ['FCFE (equity cash flow)','FCFF (enterprise cash flow)'], horizontal=True)
    effective_net_debt=0 if basis.startswith('FCFE') else net_debt_b*1e9
    st.caption('For FCFE, enter cost of equity in the discount-rate control. For FCFF, enter WACC.')
    try:
        dcf=dcf_per_share(fcf_b*1e9,growth,discount,terminal_growth,years,effective_net_debt,shares_b*1e9)
        intrinsic=dcf['per_share']
        a,b,c=st.columns(3)
        a.metric('Illustrative DCF value / share',f'{intrinsic:,.2f} {currency}')
        b.metric('Upside / downside vs price',f'{(intrinsic/price-1)*100:+.1f}%')
        c.metric('Margin of safety',f'{(1-price/intrinsic)*100:.1f}%' if intrinsic>0 else 'N/A')
        st.caption(f"Terminal value share of enterprise value: {dcf['terminal_fraction']:.1%} — high values indicate sensitivity to terminal assumptions.")
        st.markdown('#### Discount-rate / growth sensitivity')
        rows=[]
        for g in [growth-0.02,growth,growth+0.02]:
            row={'FCF growth':f'{g:.1%}'}
            for r in [discount-0.02,discount,discount+0.02]:
                try: row[f'{r:.1%} WACC']=round(dcf_per_share(fcf_b*1e9,g,r,terminal_growth,years,effective_net_debt,shares_b*1e9)['per_share'],2)
                except ValueError: row[f'{r:.1%} WACC']=None
            rows.append(row)
        sensitivity_df=pd.DataFrame(rows).set_index('FCF growth')
        st.dataframe(sensitivity_df,use_container_width=True)
        st.download_button('Download DCF sensitivity CSV',sensitivity_df.to_csv().encode('utf-8'),file_name=f'{ticker}_dcf_sensitivity.csv',mime='text/csv')
        st.markdown('#### Scenario estimates (illustrative, not calibrated probabilities)')
        scenarios=[]
        for name,dg,dr in [('Bear',-0.03,0.02),('Base',0,0),('Bull',0.03,-0.01)]:
            try: value=dcf_per_share(fcf_b*1e9,growth+dg,discount+dr,terminal_growth,years,effective_net_debt,shares_b*1e9)['per_share']
            except ValueError: value=float('nan')
            scenarios.append({'Scenario':name,'Value / share':value,'Upside %':(value/price-1)*100})
        st.dataframe(pd.DataFrame(scenarios),hide_index=True,use_container_width=True)
    except ValueError as exc: st.info(f'DCF unavailable: {exc}')
    st.markdown('### Free Cash Flow to Equity (FCFE) valuation')
    st.caption('FCFE = cash flow from operations − capital expenditures + net borrowing. Financial statement labels and signs must be verified. All values below are in billions of reporting currency.')
    parts=extract_fcfe_components(cashflow)
    cfo_b=st.number_input('Annual operating cash flow (billions)',value=float(parts['cfo'] or 0)/1e9,format='%.4f',key='fcfe_cfo')
    capex_b=st.number_input('Annual capital expenditures, positive outflow (billions)',min_value=0.0,value=float(parts['capex'] or 0)/1e9,format='%.4f',key='fcfe_capex')
    borrowing_b=st.number_input('Annual net borrowing: debt issued minus repaid (billions)',value=float(parts['net_borrowing'] or 0)/1e9,format='%.4f',key='fcfe_borrow')
    if parts['net_borrowing'] is None:
        st.warning('Net borrowing was not found. The displayed zero is a placeholder, NOT a verified zero. Enter debt issuance minus debt repayments from the cash flow statement before interpreting the FCFE result.')
    st.caption('Net borrowing data: '+parts['borrowing_source']+'. For banks, insurers, and other financial firms, conventional FCFE reconstruction may be inappropriate.')
    fcfe_growth=st.number_input('FCFE annual forecast growth (%)',-90.0,100.0,7.0,0.5,key='fcfe_growth')/100
    use_capm=st.checkbox('Estimate cost of equity using CAPM (beta vs SPY)',value=True)
    capm_beta=None
    try: capm_beta=risk_metrics(hist['Close'],market['Close'],rf)['beta']
    except Exception: pass
    if use_capm and capm_beta is not None and math.isfinite(capm_beta):
        ke=rf+capm_beta*erp
        st.write(f'CAPM cost of equity: {ke:.2%} (beta = {capm_beta:.2f}; risk-free rate = {rf:.2%}; equity risk premium = {erp:.2%})')
    else:
        ke=st.number_input('FCFE cost of equity (%)',min_value=0.1,max_value=60.0,value=11.0,step=0.5,key='fcfe_ke')/100
    fcfe_terminal=st.number_input('FCFE perpetual growth (%)',-5.0,15.0,2.5,0.5,key='fcfe_terminal')/100
    fcfe_years=st.slider('FCFE projection years',3,15,5,key='fcfe_years')
    try:
        annual_fcfe=fcfe_from_components(cfo_b*1e9,capex_b*1e9,borrowing_b*1e9)
        fcfe_result=fcfe_per_share(annual_fcfe,fcfe_growth,ke,fcfe_terminal,fcfe_years,shares_b*1e9)
        fcfe_value=fcfe_result['per_share']
        x,y,z=st.columns(3)
        x.metric('FCFE intrinsic value / share',f'{fcfe_value:,.2f} {currency}')
        y.metric('FCFE upside / downside',f'{(fcfe_value/price-1)*100:+.1f}%')
        z.metric('Normalized FCFE (billions)',f'{annual_fcfe/1e9:,.3f}')
        st.caption(f"Terminal value accounts for {fcfe_result['terminal_fraction']:.1%} of estimated equity value before any adjustments.")
        st.markdown('#### FCFE cost-of-equity / growth sensitivity')
        sens=[]
        for gg in [fcfe_growth-0.02,fcfe_growth,fcfe_growth+0.02]:
            line={'FCFE growth':f'{gg:.1%}'}
            for kk in [ke-0.02,ke,ke+0.02]:
                try: line[f'{kk:.1%} cost of equity']=round(fcfe_per_share(annual_fcfe,gg,kk,fcfe_terminal,fcfe_years,shares_b*1e9)['per_share'],2)
                except ValueError: line[f'{kk:.1%} cost of equity']=None
            sens.append(line)
        st.dataframe(pd.DataFrame(sens).set_index('FCFE growth'),use_container_width=True)
    except ValueError as exc:
        st.info(f'FCFE valuation unavailable: {exc}. Check reported cash flow, borrowing, shares, and discount assumptions.')
    borrowing_verified=st.checkbox('I verified net borrowing against the company cash-flow statement (including if zero)',value=False,key='borrow_verified')
    st.markdown('### Three-stage FCFE & market-implied earnings growth')
    st.caption('Stage 1: high growth. Stage 2: linear fade from high growth to a mature transition rate. Stage 3: stable perpetual growth. Reverse valuation solves the stage-1 earnings growth rate that equates modeled equity value to the observed price, **assuming constant FCFE-to-earnings conversion and shares**.')
    col1,col2=st.columns(2)
    with col1:
        high_g=st.number_input('Stage 1 annual FCFE / EPS growth (%)',-90.0,150.0,12.0,0.5,key='three_high')/100
        high_n=st.slider('Stage 1 years',1,15,5,key='three_high_n')
        fade_n=st.slider('Stage 2 transition years',1,15,5,key='three_fade_n')
    with col2:
        mature_g=st.number_input('Stage 2 end-of-transition growth (%)',-50.0,50.0,4.0,0.5,key='three_mature')/100
        stable_g=st.number_input('Stage 3 perpetual FCFE growth (%)',-5.0,15.0,2.5,0.25,key='three_stable')/100
        assumed_sustainable=st.number_input('Assumed sustainable near-term earnings growth (%)',-90.0,150.0,10.0,0.5,key='sustainable')/100
    try:
        if parts['net_borrowing'] is None and not borrowing_verified:
            st.warning('Three-stage and reverse valuations require verified net borrowing. Check the confirmation box above after checking the financial statement.')
        elif annual_fcfe<=0:
            st.info('Three-stage and reverse models require positive normalized FCFE. Normalize cyclicality or use a different valuation method.')
        else:
            result3=three_stage_fcfe(annual_fcfe,shares_b*1e9,ke,high_g,mature_g,stable_g,high_n,fade_n)
            implied=implied_earnings_growth(price,annual_fcfe,shares_b*1e9,ke,mature_g,stable_g,high_n,fade_n)
            a,b,c=st.columns(3)
            a.metric('Three-stage FCFE intrinsic / share',f'{result3["per_share"]:,.2f} {currency}')
            b.metric('Upside / downside',f'{(result3["per_share"]/price-1):+.1%}')
            c.metric('Market-implied initial EPS growth',f'{implied:.2%}' if implied is not None else 'Not bracketed')
            if implied is not None:
                gap=implied-assumed_sustainable
                st.metric('Implied minus assumed sustainable growth',f'{gap:+.2%}')
                if gap>0.03: st.warning('Market price requires growth materially ABOVE your sustainable-growth assumption. Investigate competitive advantage, reinvestment, ROE, analyst forecasts, and dilution.')
                elif gap < -0.03: st.info('Market-implied growth is below your sustainable-growth assumption. This may indicate upside or unmodeled risk.')
                else: st.info('Market-implied growth is close to your sustainable-growth assumption; this is not evidence of actual sustainability.')
            else: st.warning('The market price lies outside the values produced by initial growth rates from -95% to +300%. Change model inputs or review financial data.')
            st.caption(f'Terminal value represents {result3["terminal_fraction"]:.1%} of equity value. High terminal reliance increases model risk.')
            st.dataframe(pd.DataFrame(result3['forecast']).assign(**{'FCFE (billions)':lambda d:d['FCFE']/1e9,'PV (billions)':lambda d:d['Present value']/1e9})[['Year','Growth','FCFE (billions)','PV (billions)']],hide_index=True,use_container_width=True)
            st.download_button('Download three-stage forecast CSV',pd.DataFrame(result3['forecast']).to_csv(index=False).encode('utf-8'),file_name=f'{ticker}_three_stage_fcfe.csv',mime='text/csv')
            st.markdown('#### Implied growth sensitivity to cost of equity')
            grid=[]
            for shift in [-0.02,-0.01,0,0.01,0.02]:
                kk=ke+shift
                try: ig=implied_earnings_growth(price,annual_fcfe,shares_b*1e9,kk,mature_g,stable_g,high_n,fade_n)
                except ValueError: ig=None
                grid.append({'Cost of equity':f'{kk:.2%}','Market-implied initial growth':f'{ig:.2%}' if ig is not None else 'N/A'})
            st.dataframe(pd.DataFrame(grid),hide_index=True,use_container_width=True)
    except (ValueError,UnboundLocalError) as exc: st.info(f'Three-stage valuation unavailable: {exc}')
    st.caption('The implied rate is a MODEL-IMPLIED growth assumption, not an observed consensus EPS forecast. Fixed FCFE/earnings conversion, share count, borrowing policy, and mature growth are strong assumptions. Compare with historical EPS CAGR and independently sourced analyst estimates before judging sustainability.')
    st.warning('FCFE reconstruction can be misleading when debt flows are missing, net borrowing is unusually high, cash flows are negative, or the firm is financial. The model requires positive sustainable FCFE and cost of equity above perpetual growth.')
    st.markdown('#### Gordon dividend discount model')
    div=info.get('dividendRate')
    div=st.number_input('Annual dividend per share',min_value=0.0,value=float(div or 0),format='%.4f')
    dg=st.number_input('Perpetual dividend growth (%)',-20.0,20.0,3.0,0.5)/100
    try:
        ddm_value=gordon(div,ke,dg)
        st.metric('DDM intrinsic value / share',f'{ddm_value:,.2f} {currency}')
    except ValueError:
        ddm_value=None
        st.caption('DDM requires a positive dividend and cost of equity above dividend growth.')
    st.markdown('### Valuation methods at a glance')
    summary_rows=[]
    for method, value in [('DCF', locals().get('intrinsic')), ('FCFE', locals().get('fcfe_value')), ('DDM', locals().get('ddm_value'))]:
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            summary_rows.append({'Method':method,'Estimated value / share':float(value),'Current price':price,'Upside / downside':float(value/price-1)})
    if summary_rows:
        summary_df=pd.DataFrame(summary_rows)
        st.dataframe(summary_df.style.format({'Estimated value / share':'{:.2f}','Current price':'{:.2f}','Upside / downside':'{:.1%}'}),hide_index=True,use_container_width=True)
        st.download_button('Download valuation summary CSV',summary_df.to_csv(index=False).encode('utf-8'),file_name=f'{ticker}_valuation_summary.csv',mime='text/csv')
        st.caption('These estimates are not directly comparable when they use different cash-flow definitions or discount rates. Review the assumptions and data basis for each method.')

with risk:
    try:
        metrics=risk_metrics(hist['Close'],market['Close'],rf)
        a,b,c=st.columns(3)
        a.metric('Beta vs SPY',f"{metrics['beta']:.2f}")
        b.metric('Annualized volatility',f"{metrics['volatility']:.1%}")
        c.metric('Historical annualized price return',f"{metrics['annualized_price_return']:.1%}")
        a,b,c=st.columns(3)
        a.metric('Sharpe ratio (historical)',f"{metrics['sharpe']:.2f}")
        b.metric('Maximum drawdown',f"{metrics['max_drawdown']:.1%}")
        c.metric('Daily historical VaR 95%',f"{metrics['historical_var_95']:.1%}")
        st.metric('CAPM required return (assumed inputs)',f"{(rf+metrics['beta']*erp):.1%}")
        aligned=pd.concat([hist['Close'].rename('Stock'),market['Close'].rename('SPY')],axis=1).dropna()
        st.line_chart(aligned/aligned.iloc[0]*100)
        st.caption(f"{metrics['n_returns']} aligned daily observations; SPY is a proxy, not the theoretical market portfolio. Historical price returns exclude separately distributed cash dividends. VaR is a one-day empirical quantile, not a loss limit.")
    except Exception as exc: st.warning(f'Risk analysis unavailable: {exc}')
with fundamentals:
    fields={'Revenue':info.get('totalRevenue'),'Net income':info.get('netIncomeToCommon'),'Operating cash flow':info.get('operatingCashflow'),'Free cash flow':info.get('freeCashflow'),'Total debt':info.get('totalDebt'),'Total cash':info.get('totalCash'),'Return on equity':info.get('returnOnEquity'),'Profit margin':info.get('profitMargins')}
    st.dataframe(pd.DataFrame([{'Metric':k,'Reported value':v} for k,v in fields.items()]),hide_index=True,use_container_width=True)
    st.caption('Availability and definitions vary by company and data provider; reported values may represent different reporting periods.')
with notes:
    st.markdown('''**Data provenance:** yfinance retrieves public Yahoo Finance data using an unofficial interface; reliability, redistribution rights, availability and update timing are not guaranteed. The app does not use a paid API key.\n\n**FCFE model:** FCFE = CFO - capex + net borrowing; use the cost of equity and do not subtract debt again. The net-borrowing field must be verified against the statement of cash flows. The DDM also uses the cost of equity.\n\n**DCF limitation:** This is an educational screening calculation. A robust enterprise DCF requires forecast *unlevered* free cash flow (FCFF), a consistent WACC, and net-debt reconciliation. For a levered free-cash-flow-to-equity (FCFE) model, discount at cost of equity and do **not** subtract net debt.\n\n**Risk:** Beta, Sharpe ratio and volatility are historical estimates. CAPM expected return depends on assumed risk-free rate and equity premium. Price-only historical returns are not total returns.\n\n**Decision support:** No automatic buy/sell recommendation is generated. Verify financial statements, dilution, one-time items, currency, debt, industry cyclicality and assumptions before investing. No price feed or estimate is guaranteed real-time.''')

st.divider()
st.header('Professional equity research report')
st.caption('Generate an eight-page PDF using the active three-stage FCFE assumptions. The report is unavailable if crucial cash-flow inputs have not been verified.')
from research import model_analysis, report_pdf, sustainable_growth
screen=sustainable_growth(info)
st.write('Automatic sustainable growth screen (ROE x retention):', f'{screen:.2%}' if screen is not None else 'Unavailable - verify ROE and payout ratio')
if not (shares_b>0 and annual_fcfe>0 and ke>stable_g and (parts['net_borrowing'] is not None or borrowing_verified)):
    st.warning('Report requires positive normalized FCFE and shares, cost of equity above terminal growth, and verified net borrowing.')
else:
    try:
        analysis=model_analysis(price,annual_fcfe,shares_b*1e9,ke,high_g,mature_g,stable_g,high_n,fade_n,info)
        st.metric('Market-implied minus sustainable growth screen',f"{analysis['growth_gap']:+.2%}" if analysis['growth_gap'] is not None else 'Unavailable')
        try: report_risk=risk_metrics(hist['Close'],market['Close'],rf)
        except Exception: report_risk={}
        report=report_pdf(ticker,info,price,currency,analysis,{'fcfe':annual_fcfe,'shares':shares_b*1e9,'ke':ke,'g1':high_g,'g2':mature_g,'g3':stable_g,'n1':high_n,'n2':fade_n},report_risk,str(hist.index[-1].date()),sec_table=(st.session_state['sec_research'][1] if st.session_state.get('sec_research',('none',))[0]==ticker else None),analyst=__import__('sec_research').analyst_summary(info),peers=(st.session_state['peer_research'][1] if st.session_state.get('peer_research',('none',))[0]==ticker else None))
        st.download_button('Download equity research PDF (8-10 sections)',report,file_name=f'{ticker}_equity_research.pdf',mime='application/pdf',type='primary')
    except (ValueError,OverflowError,ZeroDivisionError) as exc: st.error(f'Report unavailable: {exc}')

st.divider()
st.header('SEC filings, earnings growth, analyst estimates & peers | V1.4')
st.caption('SEC XBRL facts are official reported data. Analyst metrics and peers are retrieved separately from unofficial Yahoo Finance data and may be missing or stale.')
from sec_research import fetch_companyfacts,historical_table,eps_cagr,analyst_summary,peer_table
sec_agent_default=secret_text('SEC_USER_AGENT')
sec_agent=st.text_input('SEC request identity (application name and contact email)',value=sec_agent_default,placeholder='Equity Research App contact@example.com',help='Set SEC_USER_AGENT in Streamlit Secrets to avoid placing the request identity in source code.')
sec_tab,analyst_tab,peer_tab=st.tabs(['SEC 10-K history','Analyst comparison','Peer valuation'])
with sec_tab:
    if st.button('Retrieve official SEC annual financial facts'):
        try:
            with st.spinner('Requesting SEC companyfacts...'):
                facts=fetch_companyfacts(ticker,sec_agent or sec_agent_default)
                table,tag_sources=historical_table(facts)
            st.session_state['sec_research']=(ticker,table,tag_sources)
        except Exception as exc: st.error(f'SEC request unavailable: {exc}')
    if st.session_state.get('sec_research',('none',))[0]==ticker:
        _,table,tags=st.session_state['sec_research']
        if table.empty: st.warning('No compatible SEC annual XBRL facts were found. Do not infer zero values.')
        else:
            st.dataframe(table.sort_values('Fiscal year',ascending=False),hide_index=True,use_container_width=True)
            eps3=eps_cagr(table,3)
            st.metric('Three-year diluted EPS CAGR',f'{eps3:.2%}' if eps3 is not None else 'Unavailable / unsuitable')
            st.caption('Annual observations are aligned by XBRL period-end date, not filing fy. Fiscal year shown is the period-end calendar year; verify issuer-specific fiscal-year naming. ROE uses average equity where consecutive observations exist.')
            st.download_button('Download SEC historical financials CSV',table.to_csv(index=False).encode(),file_name=f'{ticker}_sec_history.csv')
with analyst_tab:
    a=analyst_summary(info)
    st.dataframe(pd.DataFrame([{'Vendor field':k,'Value':v} for k,v in a.items()]),hide_index=True,use_container_width=True)
    if isinstance(a.get('forwardEps'),(float,int)) and isinstance(a.get('trailingEps'),(float,int)) and a['trailingEps']>0:
        implied_1y=a['forwardEps']/a['trailingEps']-1
        st.metric('Forward EPS / trailing EPS - 1',f'{implied_1y:.2%}')
        st.caption('This is an approximate one-year EPS change between non-identical reporting windows, NOT a long-run consensus EPS CAGR. Do not compare it directly with a five-year implied growth rate without horizon adjustment.')
    st.warning('Consensus forecast source dates, contributor counts and definitions may be unavailable. Missing analyst values are never substituted with assumed forecasts.')
with peer_tab:
    peers=st.text_input('Peer tickers (comma-separated; user-selected)',value='AAPL,GOOGL,AMZN',help='Review comparability by sector, business model, leverage, profitability, and accounting standards.')
    if st.button('Retrieve peer multiples'):
        tickers=[x.strip().upper() for x in peers.split(',') if x.strip()][:8]
        import yfinance as yf
        with st.spinner('Loading peer summary data...'):
            st.session_state['peer_research']=(ticker,load_peer_table_cached(tuple(tickers)))
    if st.session_state.get('peer_research',('none',))[0]==ticker:
        peers_df=st.session_state['peer_research'][1]
        st.dataframe(peers_df,hide_index=True,use_container_width=True)
        valid=peers_df[pd.to_numeric(peers_df.get('Trailing P/E'),errors='coerce')>0].copy() if 'Trailing P/E' in peers_df else pd.DataFrame()
        if not valid.empty:
            median_pe=float(pd.to_numeric(valid['Trailing P/E']).median())
            eps=info.get('trailingEps')
            st.metric('Peer median trailing P/E',f'{median_pe:.2f}x')
            if isinstance(eps,(float,int)) and eps>0:
                st.metric('Illustrative peer-implied price (median P/E x trailing EPS)',f'{median_pe*eps:,.2f} {currency}')
                st.caption('Not an intrinsic value. Multiple differences may reflect growth, leverage, risk, profitability, or accounting differences.')
        st.download_button('Download peer comparison CSV',peers_df.to_csv(index=False).encode(),file_name=f'{ticker}_peers.csv')
