"""Auditable research metrics and fixed-layout PDF equity report."""
import io, math
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch
from advanced import three_stage_fcfe, implied_earnings_growth
from data import find_latest


def historical_eps_growth(info):
    """EPS growth proxy supplied by vendor; not a historical multi-year CAGR."""
    x=info.get('earningsQuarterlyGrowth')
    return float(x) if isinstance(x,(int,float)) and math.isfinite(x) else None


def sustainable_growth(info):
    """ROE x retention using vendor's trailing dividend payout ratio; screening estimate only."""
    roe=info.get('returnOnEquity'); payout=info.get('payoutRatio')
    if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (roe,payout)): return None
    if roe<=0 or payout<0 or payout>1: return None
    return float(roe*(1-payout))


def model_analysis(price,fcfe,shares,ke,g1,g2,g3,n1,n2,info):
    val=three_stage_fcfe(fcfe,shares,ke,g1,g2,g3,n1,n2)
    implied=implied_earnings_growth(price,fcfe,shares,ke,g2,g3,n1,n2)
    sgr=sustainable_growth(info)
    return {'valuation':val,'implied':implied,'sgr':sgr,'growth_gap':implied-sgr if implied is not None and sgr is not None else None,
            'upside':val['per_share']/price-1,'eps_growth_proxy':historical_eps_growth(info)}


def report_pdf(ticker,info,price,currency,analysis,inputs,risk=None,source_date=None,sec_table=None,analyst=None,peers=None):
    """Generate an eight-page, transparently assumption-driven research report."""
    output=io.BytesIO()
    doc=SimpleDocTemplate(output,pagesize=(612,792),rightMargin=47,leftMargin=47,topMargin=54,bottomMargin=49)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportTitle',parent=styles['Title'],fontName='Helvetica-Bold',fontSize=21,leading=25,textColor=colors.HexColor('#102a43'),spaceAfter=14))
    styles.add(ParagraphStyle(name='SectionTitleX',parent=styles['Heading1'],fontSize=15,leading=19,textColor=colors.HexColor('#153f63'),spaceAfter=14))
    styles.add(ParagraphStyle(name='ReportBody',parent=styles['BodyText'],fontSize=10,leading=15,spaceAfter=11))
    styles.add(ParagraphStyle(name='TinyNote',parent=styles['BodyText'],fontSize=8,leading=12,textColor=colors.HexColor('#52616b'),spaceAfter=9))
    S=[]
    def para(t,style='ReportBody'): S.append(Paragraph(str(t),styles[style]))
    def table(rows):
        data=[[Paragraph(str(v),styles['ReportBody']) for v in row] for row in rows]
        t=Table(data,colWidths=[260,255],repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef5')),('LINEBELOW',(0,0),(-1,0),0.8,colors.HexColor('#adc1d1')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f8fb')]),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        S.append(t);S.append(Spacer(1,16))
    def page(title): S.append(PageBreak());para(title,'SectionTitleX')
    def fmt(x,pct=False): return 'Not available' if x is None or not math.isfinite(float(x)) else (f'{x:.2%}' if pct else f'{x:,.2f}')
    v=analysis['valuation']; implied=analysis['implied']; sgr=analysis['sgr']
    stamp=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    para('STOCKVALUE AI | EQUITY RESEARCH','TinyNote')
    para(f"{info.get('longName') or ticker} ({ticker})",'ReportTitle')
    para('Independent, model-based equity valuation | Research draft')
    table([['Valuation overview','Value'],['Observed adjusted close',f'{fmt(price)} {currency}'],['Three-stage FCFE value / share',f"{fmt(v['per_share'])} {currency}"],['Modeled upside / downside',fmt(analysis['upside'],True)],['Implied high-stage EPS growth',fmt(implied,True)],['ROE x retention growth screen',fmt(sgr,True)]])
    para('Investment interpretation')
    para('The difference between modeled intrinsic value and the observed price reflects the specified cash-flow, discount-rate and growth assumptions. It is not a trading signal or a probability of a positive return.')
    para(f'Report generated: {stamp}. Price history observation: {source_date or "not verified"}. Data: Yahoo Finance through unofficial yfinance; availability, timeliness and accuracy are not guaranteed.','TinyNote')
    page('1 | Business and investment context')
    para(f"{info.get('longBusinessSummary') or 'Business summary was unavailable from the data provider.'}")
    table([['Company metric','Reported vendor value'],['Sector',info.get('sector','Unavailable')],['Industry',info.get('industry','Unavailable')],['Market capitalization',fmt(info.get('marketCap'))],['Trailing P/E',fmt(info.get('trailingPE'))]])
    para('Investment thesis framework')
    para('Evaluate revenue durability, competitive position, capital intensity, management capital allocation, dilution, and financing requirements. This automated report does not independently verify competitive advantage or qualitative management claims.')
    page('2 | Financial performance and quality')
    table([['Financial indicator','Latest provider summary'],['Revenue',fmt(info.get('totalRevenue'))],['Operating margin',fmt(info.get('operatingMargins'),True)],['Profit margin',fmt(info.get('profitMargins'),True)],['Return on equity',fmt(info.get('returnOnEquity'),True)],['Debt / equity',fmt(info.get('debtToEquity'))],['Operating cash flow',fmt(info.get('operatingCashflow'))],['Free cash flow (vendor field)',fmt(info.get('freeCashflow'))]])
    para('Cash-flow quality')
    para('The vendor free-cash-flow field is not automatically interchangeable with FCFE. FCFE requires operating cash flow minus capital spending plus net borrowing. Review debt issuance, repayments, working capital, and one-off cash flows against original filings.')
    page('3 | Three-stage FCFE valuation')
    table([['Model input','Selected assumption'],['Normalized FCFE',fmt(inputs['fcfe'])],['Shares outstanding',fmt(inputs['shares'])],['Cost of equity',fmt(inputs['ke'],True)],['High-stage growth',fmt(inputs['g1'],True)],['Transition end growth',fmt(inputs['g2'],True)],['Stable perpetual growth',fmt(inputs['g3'],True)],['Stage lengths',f"{inputs['n1']} + {inputs['n2']} years"],['Terminal value / equity value',fmt(v['terminal_fraction'],True)]])
    para('FCFE is discounted at the cost of equity; debt must not be subtracted a second time. The terminal-growth assumption must be below the cost of equity. Terminal value concentration increases sensitivity to small parameter changes.')
    page('4 | Forecast and valuation sensitivity')
    forecast=v['forecast']
    table([['Forecast year / growth','FCFE / discounted FCFE'],*[ [f"Year {r['Year']} | {r['Growth']:.1%}",f"{r['FCFE']/1e9:.2f}B / {r['Present value']/1e9:.2f}B"] for r in forecast[:10]]])
    para('The forecast mechanically follows the selected growth trajectory. These values are scenario outputs, not management guidance or independently estimated analyst forecasts.')
    page('5 | Reverse valuation and growth sustainability')
    table([['Growth comparison','Estimate'],['Market-implied initial EPS growth',fmt(implied,True)],['ROE x retention screen',fmt(sgr,True)],['Implied less growth screen',fmt(analysis['growth_gap'],True)],['Vendor quarterly earnings growth proxy',fmt(analysis['eps_growth_proxy'],True)]])
    para('The implied EPS rate is obtained by solving the FCFE model backwards, assuming a constant FCFE-to-earnings conversion ratio, unchanged share count and specified transition/stable growth. It is not an observed analyst consensus forecast.')
    para('ROE x retention is a simplified sustainability screen. A high gap warrants investigation of incremental ROE, reinvestment, financing capacity, competitive dynamics, and dilution. It does not prove that a stock is overvalued.')
    page('6 | Market risk and expected return')
    risk=risk or {}
    table([['Risk / return indicator','Estimate'],['Beta versus SPY',fmt(risk.get('beta'))],['Annualized historical volatility',fmt(risk.get('volatility'),True)],['Annualized historical price return',fmt(risk.get('annualized_price_return'),True)],['Historical Sharpe ratio',fmt(risk.get('sharpe'))],['Historical maximum drawdown',fmt(risk.get('max_drawdown'),True)],['Historical VaR (daily)',fmt(risk.get('var_95'),True)]])
    para('Historical risk and returns are sample-dependent, exclude some trading frictions and may not predict future performance. SPY is a US equity proxy rather than the theoretical CAPM market portfolio. Verify beta estimation windows and adjusted-price conventions.')
    page('7 | Scenario assessment and decision checklist')
    rows=[['Scenario','Intrinsic value / share']]
    for name,dg,dk in [('Bear',-0.04,0.02),('Base',0,0),('Bull',0.04,-0.01)]:
        try: estimate=three_stage_fcfe(inputs['fcfe'],inputs['shares'],inputs['ke']+dk,inputs['g1']+dg,inputs['g2'],inputs['g3'],inputs['n1'],inputs['n2'])['per_share']
        except ValueError: estimate=None
        rows.append([name,fmt(estimate)])
    table(rows)
    para('Review before any investment decision: confirm current filings and share count; normalize cash flows; verify borrowing and capital expenditures; test discount-rate assumptions; compare competitors; inspect catalysts, regulatory risks, and downside scenarios.')
    para('Scenario outcomes are illustrative and have no assigned probabilities. Do not infer a price target or expected investment return from a single scenario.')
    if (sec_table is not None and not sec_table.empty) or analyst or (peers is not None and not peers.empty):
        page('8 | SEC, analyst expectations and peer valuation')
    if sec_table is not None and not sec_table.empty:
        last=sec_table.sort_values('Fiscal year',ascending=False).head(3)
        table([['Fiscal year','Diluted EPS / ROE'], *[[str(int(r['Fiscal year'])),f"EPS: {fmt(r.get('EPS diluted'))} | ROE: {fmt(r.get('ROE (avg equity)'),True)}"] for _,r in last.iterrows()]])
        para('Source: SEC companyfacts, annual 10-K XBRL facts. The reported EPS and ROE are historical; the fiscal-year mapping, restatements and taxonomy require checking against the original 10-K.')
    if analyst or (peers is not None and not peers.empty):
        if analyst:
            table([['Vendor analyst summary','Value'],['Forward EPS',fmt(analyst.get('forwardEps'))],['Mean price target',fmt(analyst.get('targetMeanPrice'))],['Number of opinions',fmt(analyst.get('numberOfAnalystOpinions'))]])
        if peers is not None and not peers.empty:
            table([['Peer ticker','Trailing P/E'],*[[str(r.get('Ticker')),fmt(r.get('Trailing P/E'))] for _,r in peers.head(4).iterrows()]])
        para('Analyst and peer values are from unofficial Yahoo Finance summary fields, not SEC filings. Forecast horizons and update dates may not be disclosed. Peer P/E comparisons are not stand-alone fair-value estimates.')
    page('Sources, limitations and disclosures')
    para('Data sources: Yahoo Finance company summary, historical adjusted prices, cash-flow statements and balance-sheet summaries retrieved using the unofficial yfinance package. No licensed analyst consensus or SEC filing validation is included in this version.')
    para('Inputs and model assumptions are recorded in the valuation section. Financial fields can be missing, stale, misclassified, or denominated in inconsistent currencies. For banks and insurers, conventional FCFE reconstructed from operating cash flow and net borrowing may be unsuitable.')
    para('Model governance: Do not generate a report when normalized FCFE, verified net borrowing, shares, price, or discount rate are invalid. The report records source timestamps where available and makes no claim of guaranteed accuracy.')
    para('This report is an educational analytical tool, not individualized investment advice, a securities recommendation, or an offer to transact. Independently validate all data and assumptions before relying on it.')
    def footer(c,d):
        c.setFont('Helvetica',8);c.setFillColor(colors.HexColor('#52616b'))
        c.drawString(47,31,f'StockValue AI | {ticker} | {stamp[:10]}')
        c.drawRightString(565,31,f'Page {d.page}')
    doc.build(S,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
