"""Report helpers. PDF generation is optional at runtime."""
import io

def sustainable_growth(info):
    roe=info.get('returnOnEquity'); payout=info.get('payoutRatio')
    if isinstance(roe,(int,float)) and isinstance(payout,(int,float)): return roe*(1-payout)
    return None

def model_analysis(price, fcfe, shares, ke, g1, g2, g3, n1, n2, info):
    from advanced import implied_earnings_growth
    implied=implied_earnings_growth(price,fcfe,shares,ke,g2,g3,n1,n2)
    return {'growth_gap':implied-sustainable_growth(info) if implied is not None and sustainable_growth(info) is not None else None,'implied_growth':implied,'price':price}

def report_pdf(ticker, info, price, currency, analysis, assumptions, risk, date, sec_table=None, analyst=None, peers=None):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError as exc: raise ValueError('Install reportlab to generate the PDF report.') from exc
    buffer=io.BytesIO(); pdf=canvas.Canvas(buffer,pagesize=letter); pdf.setTitle(f'{ticker} equity research')
    lines=[f'StockValue AI educational research report: {ticker}',f'Date: {date}',f'Price: {price:,.2f} {currency}','Educational use only — not investment advice.','',f"Market-implied growth: {analysis.get('implied_growth')}",f"Growth gap: {analysis.get('growth_gap')}",f"Risk metrics: {risk}",f"Assumptions: {assumptions}"]
    y=750
    for line in lines:
        pdf.drawString(45,y,str(line)[:115]); y-=18
        if y<55: pdf.showPage(); y=750
    pdf.save(); return buffer.getvalue()
