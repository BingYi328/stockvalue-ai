import math
import hashlib
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import streamlit as st
try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet=None
    InvalidToken=Exception
from engine import dcf_per_share, gordon, risk_metrics, fcfe_per_share, fcfe_from_components
from data import get_stock, get_intraday_history, extract_fcf, extract_fcfe_components, estimate_eps_growth, resolve_ticker, get_news_and_dates, get_transaction_activity, technical_indicators
from advanced import three_stage_fcfe, implied_earnings_growth

st.set_page_config(page_title='StockValue AI',page_icon='📈',layout='wide',initial_sidebar_state='expanded')

# Prototype-wide visitor counter. Each Streamlit session is counted once.
# It resets when the app process is restarted because no external database is used.
if '_visitor_count' not in globals():
    _visitor_count=0
if '_visitor_count_lock' not in globals():
    _visitor_count_lock=threading.Lock()
if 'visitor_registered' not in st.session_state:
    with _visitor_count_lock:
        _visitor_count+=1
        st.session_state['visitor_registered']=True
        st.session_state['visitor_number']=_visitor_count
st.markdown('''
<style>
    :root { --navy:#10243e; --blue:#1f5f8b; --teal:#159957; --ink:#172334; --muted:#667085; --line:#d9e2ec; --soft:#f4f7fa; }
    .stApp { background:linear-gradient(180deg,#f7f9fc 0%,#ffffff 38%); color:var(--ink); }
    [data-testid="stHeader"] { background:rgba(255,255,255,.88); }
    [data-testid="stSidebar"] { background:linear-gradient(180deg,#10243e 0%,#183654 100%); }
    [data-testid="stSidebar"] * { color:#f4f8fb !important; }
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea { color:#172334 !important; background:#ffffff !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] div { color:#172334 !important; }
    [data-testid="stSidebar"] button { border:1px solid rgba(255,255,255,.22); border-radius:8px; }
    [data-testid="stSidebar"] button[kind="primary"] { background:#19a974; border-color:#19a974; }
    [data-testid="stSidebar"] [data-testid="stExpander"] { background:#ffffff !important; border:2px solid #7cc7e8 !important; border-radius:10px !important; }
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"] { color:#10243e !important; background:#ffffff !important; }
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"] * { color:#10243e !important; }
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h1,
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h2,
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"] h3 { color:#0b4f71 !important; }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary,
    [data-testid="stSidebar"] [data-testid="stExpander"] summary * { color:#0b4f71 !important; font-weight:800 !important; }
    [data-testid="stSidebar"] [data-testid="stCheckbox"] label { color:#ffffff !important; font-weight:750 !important; }
    h1,h2,h3 { color:var(--navy); letter-spacing:-.02em; }
    h1 { font-size:2.35rem !important; margin-bottom:.1rem !important; }
    h2 { margin-top:1.35rem !important; }
    h3 { margin-top:1.15rem !important; }
    [data-testid="stMetric"] { background:#ffffff; border:1px solid var(--line); border-radius:12px; padding:14px 16px; box-shadow:0 4px 14px rgba(16,36,62,.06); }
    [data-testid="stMetricLabel"] { color:var(--muted) !important; font-size:.78rem !important; text-transform:uppercase; letter-spacing:.06em; }
    [data-testid="stMetricValue"] { color:var(--navy) !important; font-weight:750; }
    [data-testid="stSidebar"] [data-testid="stMetric"] { background:rgba(255,255,255,.16) !important; border:1px solid rgba(255,255,255,.42) !important; box-shadow:0 4px 14px rgba(0,0,0,.18); }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] { color:#e8f7ff !important; font-weight:800 !important; }
    [data-testid="stSidebar"] [data-testid="stMetricValue"] { color:#ffffff !important; font-size:1.45rem !important; font-weight:850 !important; }
    .portfolio-balance-card { background:linear-gradient(120deg,#0b6b4f 0%,#159957 55%,#21b878 100%); color:#ffffff; border:2px solid #b8ffe0; border-radius:14px; padding:18px 22px; margin:12px 0 18px 0; box-shadow:0 8px 22px rgba(13,105,76,.24); }
    .portfolio-balance-card .label { color:#eafff5; font-size:.82rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
    .portfolio-balance-card .amount { color:#ffffff; font-size:2rem; font-weight:900; line-height:1.15; margin-top:4px; }
    .portfolio-balance-card .detail { color:#eafff5; font-size:.88rem; margin-top:5px; }
    .visitor-counter-card { background:linear-gradient(120deg,#10243e 0%,#1f5f8b 100%); color:#ffffff; border:1px solid #7cc7e8; border-radius:14px; padding:15px 20px; margin:10px 0 20px 0; box-shadow:0 6px 18px rgba(16,36,62,.16); }
    .visitor-counter-card .welcome { color:#dff5ff; font-size:1rem; font-weight:650; }
    .visitor-counter-card .count { color:#ffffff; font-size:1.7rem; font-weight:900; margin-top:3px; }
    .visitor-counter-card .note { color:#d9ebf5; font-size:.78rem; margin-top:4px; }
    [data-testid="stTabs"] button { color:var(--muted); font-weight:650; }
    [data-testid="stTabs"] button[aria-selected="true"] { color:var(--blue); border-bottom-color:var(--teal); }
    [data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:10px; overflow:hidden; }
    [data-testid="stExpander"] { border:1px solid var(--line); border-radius:10px; background:#ffffff; }
    .research-hero { background:linear-gradient(120deg,#10243e 0%,#1f5f8b 100%); color:#ffffff; border-radius:16px; padding:25px 30px; margin:0 0 22px 0; box-shadow:0 10px 28px rgba(16,36,62,.16); }
    .research-hero h1 { color:#ffffff !important; margin:0 !important; font-size:2.2rem !important; }
    .research-hero p { margin:.45rem 0 0 0; color:#dcecf7; font-size:1rem; }
    .hero-badge { display:inline-block; margin-top:15px; padding:5px 10px; border-radius:999px; background:rgba(255,255,255,.14); color:#e9fff3; font-size:.75rem; letter-spacing:.05em; text-transform:uppercase; }
    .section-kicker { color:var(--teal); font-size:.75rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; margin:1.2rem 0 .25rem 0; }
    .source-note { color:var(--muted); font-size:.82rem; }
    div[data-testid="stAlert"] { border-radius:10px; }
</style>
''',unsafe_allow_html=True)
logo_path=Path(__file__).with_name('StockValueAI_logo_improved.png')
if logo_path.exists():
    st.image(str(logo_path),width=150)
st.markdown('''<div class="research-hero"><h1>StockValue AI</h1><p>Professional equity research dashboard for valuation, market context, and technical signals.</p><span class="hero-badge">Research prototype · FCFE first · Educational use</span></div>''',unsafe_allow_html=True)
st.markdown(f'''<div class="visitor-counter-card"><div class="welcome">Welcome to StockValue AI!</div><div class="count">You are visitor #{st.session_state['visitor_number']:,}</div><div class="note">Total visitor sessions since the last app restart: {_visitor_count:,}.</div></div>''',unsafe_allow_html=True)
st.caption('Public data via Yahoo Finance/yfinance is unofficial and may be delayed or incomplete. This dashboard is for educational research—not investment advice.')
st.markdown('Feedback on StockValue AI is welcome: [send feedback to byi328@gmail.com](mailto:byi328@gmail.com)')

# Main-page lookup remains available even when the sidebar is collapsed.
with st.container():
    st.markdown('### Quick ticker lookup')
    _main_query_col,_main_button_col=st.columns([4,1])
    with _main_query_col:
        main_security_query=st.text_input('Company name or ticker',value='MSFT',key='main_security_query',label_visibility='collapsed',placeholder='Enter a company name or ticker')
    with _main_button_col:
        main_load=st.button('Analyze',type='primary',use_container_width=True,key='main_analyze_button')

@st.cache_data(ttl=900,show_spinner=False)
def load_stock_cached(symbol):
    """Cache live market/fundamental data for 15 minutes per ticker."""
    return get_stock(symbol)

@st.cache_data(ttl=900,show_spinner=False)
def resolve_ticker_cached(query):
    return resolve_ticker(query)

@st.cache_data(ttl=900,show_spinner=False)
def load_news_dates_cached(symbol):
    try:
        return get_news_and_dates(symbol)
    except Exception:
        return pd.DataFrame(columns=['Headline','Publisher','Published','Link']),pd.DataFrame(columns=['Event','Date'])

@st.cache_data(ttl=900,show_spinner=False)
def load_transaction_activity_cached(symbol):
    try:
        return get_transaction_activity(symbol)
    except Exception:
        return pd.DataFrame(),pd.DataFrame()

@st.cache_data(ttl=300,show_spinner=False)
def load_intraday_cached(symbol,interval,period):
    return get_intraday_history(symbol,interval,period)

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

STARTING_VIRTUAL_CASH=100000.0
TERMS_VERSION='2026-10-20'
SUBSCRIBER_STORE_PATH=Path(os.environ.get('SUBSCRIBER_STORE_PATH',Path(__file__).with_name('subscriber_records.json')))

def _storage_key():
    """Read the encryption key from deployment secrets, never from source code."""
    try:
        secret_key=st.secrets.get('SUBSCRIBER_STORE_KEY','')
    except Exception:
        secret_key=''
    return str(os.environ.get('SUBSCRIBER_STORE_KEY') or secret_key or '').strip()

def _decrypt_store():
    if Fernet is None or not SUBSCRIBER_STORE_PATH.exists():
        return None
    key=_storage_key()
    if not key:
        return None
    try:
        raw=SUBSCRIBER_STORE_PATH.read_bytes()
        if not raw.startswith(b'SVAI-ENCRYPTED-1\n'):
            return None
        decrypted=Fernet(key.encode('utf-8')).decrypt(raw.split(b'\n',1)[1])
        return json.loads(decrypted.decode('utf-8'))
    except (InvalidToken,ValueError,TypeError,json.JSONDecodeError,OSError):
        return None
FORUM_EXTREME_TERMS={
    'guaranteed winner','guaranteed win','cannot lose','can’t lose','no risk',
    'certainly double','will double','to the moon','all in','sell everything',
    'zero chance of loss','100% guaranteed','sure thing','bankrupt tomorrow',
    'going to zero','definitely crash','guaranteed crash'
}

TERMS_AND_AGREEMENT='''
### StockValue AI subscriber terms and agreement

By creating an account, you acknowledge and agree that:

1. **Educational information only.** StockValue AI provides educational research tools, estimates, charts, market data, and discussion features. The information is not investment, financial, legal, tax, or accounting advice.
2. **Do not rely on one output.** Estimated values, technical signals, news, and user posts may be incomplete, delayed, inaccurate, or based on assumptions. You will not use any estimate or post as your sole support for buying, selling, or holding a stock or ETF. You will independently investigate and consider your objectives, risk tolerance, diversification, current filings, and qualified professional advice.
3. **No guarantee.** StockValue AI does not guarantee the accuracy, completeness, timeliness, or profitability of any data, estimate, signal, or user contribution. Past performance does not predict future results.
4. **Paper trading only.** Any account balance and trading activity in this prototype are simulated. No real money, brokerage account, or payment processing is involved.
5. **Forum conduct.** You may share ideas and information respectfully, but you may not post market manipulation, fraud, personal information, spam, unlawful content, or extremely bullish or extremely bearish claims such as guaranteed profits, guaranteed losses, or instructions to go all-in. The owner may remove posts or suspend access.
6. **User responsibility and limitation of responsibility.** You are responsible for your decisions and use of the app. To the maximum extent permitted by applicable law, the owner and developer are not responsible for losses, damages, missed opportunities, or other consequences arising from reliance on the app, its estimates, its data, or forum content. This provision does not eliminate rights or responsibilities that cannot legally be excluded.
7. **Privacy and prototype storage.** Passwords are stored as one-way password hashes rather than plain text, and forum posts use an anonymous subscriber alias. When encrypted storage is configured, accounts, balances, posts, and watchlists are written as authenticated encrypted data; otherwise they remain session-only. Do not submit your real name, email address, brokerage credentials, account numbers, Social Security numbers, or other confidential information.

This prototype is not a brokerage, investment adviser, research service, or recommendation service. By checking the agreement box, you confirm that you have read and accepted these terms.
'''

def _password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt.encode('utf-8'),310000).hex()
    return f'pbkdf2_sha256$310000${salt}${digest}'

def _verify_password(password,stored):
    if isinstance(stored,str) and stored.startswith('pbkdf2_sha256$'):
        try:
            _,iterations,salt,digest=stored.split('$',3)
            candidate=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt.encode('utf-8'),int(iterations)).hex()
            return secrets.compare_digest(candidate,digest)
        except (ValueError,TypeError):
            return False
    # Support accounts created by the earlier prototype and upgrade them at login.
    return isinstance(stored,str) and secrets.compare_digest(stored,hashlib.sha256(password.encode('utf-8')).hexdigest())

def _init_accounts():
    if 'sim_accounts' not in st.session_state:
        try:
            store_exists=SUBSCRIBER_STORE_PATH.exists()
            saved=_decrypt_store()
            if store_exists and saved is None:
                st.session_state['subscriber_store_error']='Existing encrypted subscriber records could not be opened. Check SUBSCRIBER_STORE_KEY in Streamlit Secrets; the file was not overwritten.'
            if isinstance(saved,dict):
                if isinstance(saved,dict) and 'accounts' in saved:
                    st.session_state['sim_accounts']=saved.get('accounts',{}) if isinstance(saved.get('accounts',{}),dict) else {}
                    st.session_state['forum_posts']=saved.get('forum_posts',[]) if isinstance(saved.get('forum_posts',[]),list) else []
                else:
                    st.session_state['sim_accounts']=saved if isinstance(saved,dict) else {}
            else:
                st.session_state['sim_accounts']={}
        except Exception:
            if SUBSCRIBER_STORE_PATH.exists():
                st.session_state['subscriber_store_error']='Existing subscriber records could not be loaded. The stored file was not overwritten.'
            st.session_state['sim_accounts']={}
    if 'current_user' not in st.session_state:
        st.session_state['current_user']=None
    if 'forum_posts' not in st.session_state:
        st.session_state['forum_posts']=[]
    # Do not expose historical login usernames in public forum posts.
    for _post in st.session_state['forum_posts']:
        if isinstance(_post,dict) and not str(_post.get('author','')).startswith('Subscriber-'):
            _post['author']='Subscriber'

def _save_subscriber_records():
    """Persist subscriber records only as authenticated encrypted data."""
    temporary_path=None
    try:
        if Fernet is None:
            raise RuntimeError('cryptography is not installed')
        key=_storage_key()
        if not key:
            raise RuntimeError('SUBSCRIBER_STORE_KEY is not configured')
        SUBSCRIBER_STORE_PATH.parent.mkdir(parents=True,exist_ok=True)
        payload={'accounts':st.session_state.get('sim_accounts',{}),'forum_posts':st.session_state.get('forum_posts',[]),'saved_at':datetime.now(timezone.utc).isoformat()}
        encrypted=Fernet(key.encode('utf-8')).encrypt(json.dumps(payload).encode('utf-8'))
        # Complete the encrypted write before replacing the prior store. This
        # avoids leaving a partially written account file after an interruption.
        temporary_path=SUBSCRIBER_STORE_PATH.with_name(SUBSCRIBER_STORE_PATH.name+'.tmp')
        temporary_path.write_bytes(b'SVAI-ENCRYPTED-1\n'+encrypted)
        os.replace(temporary_path,SUBSCRIBER_STORE_PATH)
        st.session_state.pop('subscriber_store_error',None)
    except Exception:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        # Do not expose secret/configuration details in the public UI.
        st.session_state['subscriber_store_error']='Subscriber records could not be saved securely. Check the encrypted storage configuration; no plaintext copy was written.'

def _account():
    username=st.session_state.get('current_user')
    return st.session_state['sim_accounts'].get(username) if username else None

def _create_account(username,password,terms_accepted=False):
    username=username.strip().lower()
    if not terms_accepted:
        return False,'You must read and accept the StockValue AI subscriber terms before creating an account.'
    if len(username)<3 or len(password)<6:
        return False,'Use a username with at least 3 characters and a password with at least 6 characters.'
    if username in st.session_state['sim_accounts']:
        return False,'That simulated account already exists. Please log in.'
    st.session_state['sim_accounts'][username]={
        'password_hash':_password_hash(password),
        'display_alias':f'Subscriber-{secrets.token_hex(4).upper()}',
        'cash':STARTING_VIRTUAL_CASH,
        'holdings':{},
        'open_orders':[],
        'watchlist':{},
        'transactions':[],
        'terms_version':TERMS_VERSION,
        'terms_accepted_at':datetime.now(timezone.utc).isoformat(),
        'created_at':datetime.now(timezone.utc).isoformat()
    }
    st.session_state['current_user']=username
    _save_subscriber_records()
    return True,'Account created with $100,000 virtual cash.'

def _validate_forum_post(title,body):
    text=f'{title} {body}'.strip().lower()
    if len(title.strip())<5:
        return False,'Please provide a descriptive title of at least five characters.'
    if len(body.strip())<20:
        return False,'Please provide at least 20 characters so other subscribers can understand your thought.'
    if len(title)>120 or len(body)>3000:
        return False,'Please keep the title under 120 characters and the post under 3,000 characters.'
    matched=[term for term in FORUM_EXTREME_TERMS if term in text]
    if matched:
        return False,'This post uses an extreme or guaranteed bullish/bearish claim. Please rewrite it as balanced, evidence-based analysis.'
    exclamations=text.count('!')
    uppercase_letters=sum(1 for char in f'{title} {body}' if char.isalpha() and char.isupper())
    letters=sum(1 for char in f'{title} {body}' if char.isalpha())
    if exclamations>=4 or (letters>=30 and uppercase_letters/max(letters,1)>.65):
        return False,'Please avoid extremely promotional or alarmist formatting. Use measured language and explain the evidence.'
    return True,''

def _login(username,password):
    username=username.strip().lower()
    record=st.session_state['sim_accounts'].get(username)
    if record and _verify_password(password,record.get('password_hash')):
        if not str(record.get('password_hash','')).startswith('pbkdf2_sha256$'):
            record['password_hash']=_password_hash(password)
            _save_subscriber_records()
        st.session_state['current_user']=username
        return True

def _execute_simulated_order(account,side,ticker,shares,execution_price,order_type):
    """Execute a paper order at the simulated current price."""
    shares=float(shares); execution_price=float(execution_price)
    if side=='Buy':
        cost=shares*execution_price
        if cost>account['cash']:
            return False,f'Order not executed: insufficient virtual cash for ${cost:,.2f}.'
        position=account['holdings'].setdefault(ticker,{'shares':0.0,'avg_cost':0.0,'last_price':execution_price})
        new_shares=position['shares']+shares
        position['avg_cost']=(position['shares']*position['avg_cost']+cost)/new_shares
        position['shares']=new_shares
        position['last_price']=execution_price
        account['cash']-=cost
    else:
        position=account['holdings'].get(ticker)
        if position is None or shares>position['shares']:
            return False,'Order not executed: insufficient virtual shares to sell.'
        account['cash']+=shares*execution_price
        position['shares']-=shares
        position['last_price']=execution_price
        if position['shares']<=1e-12:
            del account['holdings'][ticker]
    account['transactions'].append({'time':datetime.now(timezone.utc).isoformat(),'side':side.upper(),'ticker':ticker,'shares':shares,'price':execution_price,'order_type':order_type})
    return True,f'{order_type} {side.lower()} order executed: {shares:g} share(s) of {ticker} at {execution_price:,.2f}.'

def _order_triggered(order,current_price):
    side=order['side']; order_type=order['order_type']; current_price=float(current_price)
    if order_type=='Limit order':
        return current_price<=order['limit_price'] if side=='Buy' else current_price>=order['limit_price']
    if order_type=='Stop-loss order':
        return current_price<=order['stop_price']
    if order_type=='Stop-limit order':
        return current_price<=order['stop_price'] and current_price>=order['limit_price']
    return True

def _process_open_orders(account,ticker,current_price):
    messages=[]
    remaining=[]
    for order in account.setdefault('open_orders',[]):
        if order['ticker']!=ticker or not _order_triggered(order,current_price):
            remaining.append(order)
            continue
        ok,message=_execute_simulated_order(account,order['side'],ticker,order['shares'],current_price,order['order_type'])
        messages.append(message)
        if not ok:
            remaining.append(order)
    account['open_orders']=remaining
    if messages:
        _save_subscriber_records()
    return messages
    return False

_init_accounts()
if not st.session_state.get('current_user'):
    st.info('**Try the free paper-trading prototype:** create a simulated account to receive **$100,000 in virtual cash**, analyze stocks and ETFs, and place practice trades. No payment or real money is involved. Use the sidebar to subscribe free / create an account.')
with st.sidebar:
    st.markdown('### Research workspace')
    st.caption('Enter a company name or ticker to begin a structured equity-research review.')
    st.markdown('### Free paper-trading prototype')
    st.caption('Create a simulated account to receive $100,000 in virtual cash. No real money is used.')
    st.warning('Privacy: never enter your real name, email address, brokerage credentials, account numbers, Social Security number, or other confidential information in this prototype.')
    if st.session_state.get('current_user'):
        _user_record=_account()
        st.success(f"Signed in as **{st.session_state['current_user']}**")
        st.metric('Virtual cash',f"${_user_record['cash']:,.2f}")
        if st.button('Log out',use_container_width=True):
            st.session_state['current_user']=None
            st.rerun()
    else:
        _account_mode=st.radio('Account action',['Create account','Log in'],horizontal=True)
        _account_name=st.text_input('Username',key='account_name')
        _account_password=st.text_input('Password',type='password',key='account_password')
        if _account_mode=='Create account':
            with st.expander('Read subscriber terms and agreement',expanded=False):
                st.markdown(TERMS_AND_AGREEMENT)
            _terms_accepted=st.checkbox('I have read and agree to the subscriber terms and agreement.',key='terms_accepted')
            if st.button('Subscribe free / create account',use_container_width=True):
                _ok,_message=_create_account(_account_name,_account_password,_terms_accepted)
                (st.success if _ok else st.error)(_message)
                if _ok: st.rerun()
        else:
            if st.button('Log in',use_container_width=True):
                if _login(_account_name,_account_password): st.rerun()
                else: st.error('Invalid simulated username or password.')
    if Fernet is not None and _storage_key():
        st.caption('Subscriber records are encrypted before writing. For reboot persistence on Streamlit Cloud, point SUBSCRIBER_STORE_PATH at a durable external or mounted store; the default local filesystem may reset.')
    else:
        st.warning('Encrypted subscriber storage is not configured. Records remain session-only and are not written to disk.')
    if st.session_state.get('subscriber_store_error'):
        st.error(st.session_state['subscriber_store_error'])
    if st.button('Refresh live market data',use_container_width=True,key='refresh_live_data'):
        st.cache_data.clear()
        st.session_state['last_refresh_at']=datetime.now(timezone.utc).isoformat()
        st.rerun()
    security_query=st.text_input('Company name or ticker','MSFT',key='sidebar_security_query').strip()
    sidebar_load=st.button('Analyze stock',type='primary',use_container_width=True,key='sidebar_analyze_button')
    st.markdown('**Model settings**')
    growth=st.number_input('Annual FCF growth (%)',-90.0,100.0,7.0,0.5)/100
    discount=st.number_input('Discount rate / WACC (%)',0.1,60.0,10.0,0.5)/100
    terminal_growth=st.number_input('Terminal growth (%)',-5.0,15.0,2.5,0.5)/100
    years=st.slider('Forecast years',3,15,5)
    rf=st.number_input('Risk-free rate (%)',0.0,25.0,4.0,0.25)/100
    erp=st.number_input('Equity risk premium (%)',0.0,20.0,5.0,0.25)/100
    st.caption('Defaults are illustrative assumptions, not company-specific forecasts.')
lookup_clicked=bool(sidebar_load or main_load)
lookup_query=(main_security_query if main_load else security_query).strip()
if lookup_clicked:
    with st.spinner('Retrieving public market data...'):
        try:
            if not lookup_query:
                raise ValueError('Enter a company name or ticker symbol.')
            ticker=resolve_ticker_cached(lookup_query)
            st.session_state['result']=(ticker,load_stock_cached(ticker))
            st.session_state['search_query']=lookup_query
            st.session_state['last_lookup_source']='main page' if main_load else 'sidebar'
            st.session_state['last_data_retrieved_at']=datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            st.error(f'Live data unavailable: {exc}. Please try another ticker or retry later.')
            st.stop()
if 'result' not in st.session_state:
    st.info('Enter a stock ticker and click **Analyze stock** to retrieve available live financial data.')
    st.stop()
_stored_ticker,_stored_data=st.session_state['result']
if len(_stored_data)==5:  # compatibility with an already-running pre-growth session
    info,hist,market,cashflow,balance=_stored_data
    income=pd.DataFrame()
else:
    info,hist,market,cashflow,balance,income=_stored_data
ticker=_stored_ticker
search_query=st.session_state.get('search_query',ticker)
active_account=_account()
_order_messages=[]
if active_account is not None:
    active_account.setdefault('open_orders',[])
    _order_messages=_process_open_orders(active_account,ticker,float(hist['Close'].iloc[-1]))
for _order_message in _order_messages:
    st.success(_order_message)
if active_account is not None and not hist.empty:
    _latest=hist.iloc[-1]
    active_account['watchlist'][ticker]={
        'Ticker':ticker,
        'Open':float(_latest.get('Open',float('nan'))),
        'High':float(_latest.get('High',float('nan'))),
        'Low':float(_latest.get('Low',float('nan'))),
        'Close':float(_latest.get('Close',float('nan'))),
        'Volume':float(_latest.get('Volume',float('nan'))),
        'Date':str(hist.index[-1].date()),
        'Warning above':active_account['watchlist'].get(ticker,{}).get('Warning above'),
        'Warning below':active_account['watchlist'].get(ticker,{}).get('Warning below')
    }
    _save_subscriber_records()
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
    st.info('ETF paper trading is available in the Paper portfolio tab below. Equity valuation models may be unavailable for funds.')

price=float(hist['Close'].iloc[-1]); currency=info.get('currency','USD')
st.markdown('<div class="section-kicker">Company overview</div>',unsafe_allow_html=True)
st.subheader(f"{info.get('longName') or ticker} ({ticker})")
if search_query.strip().upper()!=ticker:
    st.caption(f'Search input: {search_query} | Resolved ticker: {ticker}')
st.markdown(f'''<div class="portfolio-balance-card"><div class="label">Current market price</div><div class="amount">{price:,.2f} {currency}</div><div class="detail">Latest available adjusted close · {hist.index[-1].date()} · {"ETF" if security_route(info)=="ETF" else "Stock"}</div></div>''',unsafe_allow_html=True)
_retrieved_at=st.session_state.get('last_data_retrieved_at')
_retrieved_label='unknown time'
if _retrieved_at:
    try:
        _retrieved_label=datetime.fromisoformat(_retrieved_at).strftime('%Y-%m-%d %H:%M UTC')
    except ValueError:
        pass
st.caption(f'Latest available adjusted price: {hist.index[-1].date()} | Currency: {currency} | Source: Yahoo Finance (unofficial) | Retrieved: {_retrieved_label}')
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
st.markdown('<div class="source-note">Market snapshot · Latest available quote and company summary fields</div>',unsafe_allow_html=True)
news_df,dates_df=load_news_dates_cached(ticker)
insider_df,institutional_df=load_transaction_activity_cached(ticker)
technical_df=pd.DataFrame(); technical_signals=[]
valuation,news_technical,risk,fundamentals,portfolio,forum,notes=st.tabs(['Intrinsic valuation','News & technical analysis','Risk & return','Financial fundamentals','Paper portfolio','Subscriber forum','Methods & caveats'])
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

    st.markdown('### First: primary valuation from Free Cash Flow to Equity (FCFE)')
    st.caption('FCFE is presented first because it estimates equity value directly. It discounts cash flow available to shareholders at the cost of equity and does not subtract net debt again.')
    primary_parts=extract_fcfe_components(cashflow)
    primary_fcfe=None
    primary_result=None
    if primary_parts['cfo'] is not None and primary_parts['capex'] is not None and primary_parts['net_borrowing'] is not None and shares_b:
        try:
            primary_fcfe=fcfe_from_components(primary_parts['cfo'],primary_parts['capex'],primary_parts['net_borrowing'])
            primary_result=fcfe_per_share(primary_fcfe,growth,discount,terminal_growth,years,shares_b*1e9)
            p1,p2,p3=st.columns(3)
            p1.metric('Primary FCFE estimated value / share',f"{primary_result['per_share']:,.2f} {currency}")
            p2.metric('FCFE upside / downside',f"{(primary_result['per_share']/price-1)*100:+.1f}%")
            p3.metric('Normalized FCFE',f"{primary_fcfe/1e9:,.3f}B")
            st.caption(f"Primary FCFE uses {growth:.1%} growth, {discount:.1%} cost of equity, {terminal_growth:.1%} perpetual growth, and a {years}-year forecast. Terminal value share: {primary_result['terminal_fraction']:.1%}.")
        except ValueError as exc:
            st.info(f'Primary FCFE estimate unavailable: {exc}')
    else:
        st.warning('Primary FCFE estimate is unavailable until operating cash flow, capital expenditures, net borrowing, and shares outstanding are available. Verify net borrowing before interpreting FCFE.')

    sec_growth_table=None
    saved_sec=st.session_state.get('sec_research')
    if isinstance(saved_sec,tuple) and len(saved_sec)>=2 and saved_sec[0]==ticker:
        sec_growth_table=saved_sec[1]
    eps_growth_data=estimate_eps_growth(income,sec_growth_table)
    constant_growth_value=None
    if eps_growth_data:
        eps_growth_rate,eps_growth_years,latest_eps,start_eps,eps_start_date,eps_end_date,eps_growth_source=eps_growth_data
        try:
            growth_beta=risk_metrics(hist['Close'],market['Close'],rf)['beta']
        except Exception:
            growth_beta=float('nan')
        growth_ke=rf+growth_beta*erp if math.isfinite(growth_beta) else discount
        if latest_eps>0 and growth_ke>eps_growth_rate and growth_ke>0:
            constant_growth_value=latest_eps*(1+eps_growth_rate)/(growth_ke-eps_growth_rate)
        

    st.markdown('### Second: DCF value per share')
    st.caption('This DCF value is shown second as a cross-check. It uses the selected cash-flow basis and applies net debt only when FCFF is selected.')
    try:
        dcf=dcf_per_share(fcf_b*1e9,growth,discount,terminal_growth,years,effective_net_debt,shares_b*1e9)
        intrinsic=dcf['per_share']
        a,b,c=st.columns(3)
        a.metric('Secondary DCF / FCFF value / share',f'{intrinsic:,.2f} {currency}')
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
    st.markdown('### Third: intrinsic value from the constant-growth EPS model')
    st.caption('The estimated recent EPS growth rate is used as the future annual growth rate. The model is V₀ = EPS₁ / (cost of equity − growth), where EPS₁ = latest EPS × (1 + growth).')
    if eps_growth_data and constant_growth_value is not None:
        g1,g2,g3=st.columns(3)
        g1.metric('Constant-growth intrinsic value / share',f'{constant_growth_value:,.2f} {currency}')
        g2.metric('Upside / downside vs price',f'{(constant_growth_value/price-1)*100:+.1f}%')
        g3.metric('Estimated annual EPS growth',f'{eps_growth_rate:.2%}')
        st.caption(f'Growth period: most recent {eps_growth_years} years ({eps_start_date.date()} to {eps_end_date.date()}); EPS changed from {start_eps:.2f} to {latest_eps:.2f}. Source: {eps_growth_source}. Cost of equity used: {growth_ke:.2%}.')
    elif eps_growth_data:
        st.warning(f'Constant-growth valuation is unavailable because cost of equity ({growth_ke:.2%}) must exceed estimated EPS growth ({eps_growth_rate:.2%}) and latest EPS must be positive.')
    else:
        st.warning('A 10-, 5-, or 3-year positive diluted-EPS history was not available. The constant-growth EPS valuation cannot be calculated without valid positive endpoint EPS observations.')
    st.markdown('### Detailed FCFE assumptions and sensitivity analysis')
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
    _primary_result=locals().get('primary_result')
    _primary_fcfe_value=locals().get('fcfe_value')
    if not isinstance(_primary_fcfe_value,(int,float)) and isinstance(_primary_result,dict):
        _primary_fcfe_value=_primary_result.get('per_share')
    for method, value in [('FCFE',_primary_fcfe_value), ('Constant-growth EPS',locals().get('constant_growth_value')), ('DCF / FCFF',locals().get('intrinsic')), ('DDM',locals().get('ddm_value'))]:
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            summary_rows.append({'Method':method,'Estimated value / share':float(value),'Current price':price,'Upside / downside':float(value/price-1)})
    if summary_rows:
        summary_df=pd.DataFrame(summary_rows)
        st.dataframe(summary_df.style.format({'Estimated value / share':'{:.2f}','Current price':'{:.2f}','Upside / downside':'{:.1%}'}),hide_index=True,use_container_width=True)
        st.download_button('Download valuation summary CSV',summary_df.to_csv(index=False).encode('utf-8'),file_name=f'{ticker}_valuation_summary.csv',mime='text/csv')
        st.caption('These estimates are not directly comparable when they use different cash-flow definitions or discount rates. Review the assumptions and data basis for each method.')

with news_technical:
    st.markdown('### Major news and key dates')
    if not news_df.empty:
        st.dataframe(news_df,hide_index=True,use_container_width=True,column_config={'Link':st.column_config.LinkColumn('Source article',display_text='Open article')})
    else:
        st.info('No recent news was returned by the public data provider.')
    if not dates_df.empty:
        st.markdown('#### Upcoming and reported dates')
        st.dataframe(dates_df,hide_index=True,use_container_width=True,column_config={'Source':st.column_config.LinkColumn('Source',display_text='Yahoo Finance')})
    else:
        st.info('No earnings or corporate-event dates were returned by the public data provider.')
    st.markdown('### Insider and institutional activity')
    st.caption('The tables below separate reported insider records from institutional holding disclosures. A reported institutional holding is not proof of a purchase or sale, and an implied value/share is not necessarily the actual transaction price.')
    if not insider_df.empty:
        st.markdown('#### Insider transactions')
        st.dataframe(insider_df,hide_index=True,use_container_width=True,column_config={'Source':st.column_config.LinkColumn('Source',display_text='Yahoo Finance')})
    else:
        st.info('No provider-reported insider transactions were returned.')
    if not institutional_df.empty:
        st.markdown('#### Institutional holdings reported')
        st.dataframe(institutional_df,hide_index=True,use_container_width=True,column_config={'Source':st.column_config.LinkColumn('Source',display_text='Yahoo Finance')})
    else:
        st.info('No provider-reported institutional holdings were returned.')
    st.warning('Truthfulness and timing check: these records come from a public provider and may be delayed, incomplete, restated, or mapped incorrectly. Before making a decision, open the source link and verify insider transactions against SEC Form 4 and institutional holdings against the institution\'s SEC filing (such as Form 13F).')
    st.caption('News, event dates, and prices come from public Yahoo Finance data and may be delayed, incomplete, or unavailable.')

    st.markdown('### Technical analysis')
    chart_frequency=st.radio('Chart frequency',['Daily','Intraday / day trading'],horizontal=True,key='ta_chart_frequency')
    analysis_history=hist
    selected_interval=None
    if chart_frequency=='Intraday / day trading':
        selected_interval=st.selectbox('Intraday interval',['1m','2m','5m','15m','30m','60m'],index=2,key='ta_intraday_interval')
        selected_period={'1m':'1d','2m':'5d','5m':'5d','15m':'5d','30m':'5d','60m':'1mo'}[selected_interval]
        st.caption(f'Intraday mode uses {selected_interval} bars over approximately {selected_period}. Yahoo Finance limits the history available for minute data; quotes may be delayed and are not suitable as a sole basis for live trading.')
        try:
            analysis_history=load_intraday_cached(ticker,selected_interval,selected_period)
        except Exception as exc:
            analysis_history=pd.DataFrame()
            st.error(f'Intraday data unavailable: {exc}')
    else:
        st.caption('Adjust the settings below to examine different daily or intraday technical-analysis horizons. The warnings and charts update using your selected periods.')
    ta1,ta2,ta3=st.columns(3)
    with ta1:
        chart_max=max(60,min(len(analysis_history),1500))
        chart_window_label='Chart lookback (bars)' if chart_frequency=='Intraday / day trading' else 'Chart lookback (days)'
        chart_window=st.slider(chart_window_label,60,chart_max,min(260,chart_max),10,key='ta_chart_window')
        ma_fast=st.number_input('Fast moving average',2,100,20,1,key='ta_ma_fast')
    with ta2:
        ma_medium=st.number_input('Medium moving average',2,250,50,1,key='ta_ma_medium')
        ma_long=st.number_input('Long moving average',2,500,200,1,key='ta_ma_long')
    with ta3:
        bollinger_period=st.number_input('Bollinger period',2,200,20,1,key='ta_bb_period')
        bollinger_std=st.number_input('Bollinger deviations',0.5,5.0,2.0,0.1,key='ta_bb_std')
    ta4,ta5=st.columns(2)
    with ta4:
        rsi_period=st.number_input('RSI period',2,100,14,1,key='ta_rsi_period')
    with ta5:
        macd_fast=st.number_input('MACD fast period',2,50,12,1,key='ta_macd_fast')
        macd_slow=st.number_input('MACD slow period',3,100,26,1,key='ta_macd_slow')
        macd_signal=st.number_input('MACD signal period',2,50,9,1,key='ta_macd_signal')
    try:
        technical_df,technical_signals=technical_indicators(analysis_history,(ma_fast,ma_medium,ma_long),bollinger_period,bollinger_std,rsi_period,(macd_fast,macd_slow,macd_signal))
    except ValueError as exc:
        st.error(str(exc))
        technical_df=pd.DataFrame(); technical_signals=[]
    if technical_df.empty:
        st.warning('Technical indicators are unavailable because sufficient OHLC data was not returned.')
    else:
        if technical_signals:
            st.markdown('#### Signal warnings')
            for level,message in technical_signals:
                (st.warning if level=='warning' else st.info)(message)
        else:
            st.success('No configured high-priority technical signals were detected on the latest observations.')
        ma_columns=[f'MA{ma_fast}',f'MA{ma_medium}',f'MA{ma_long}']
        chart_columns=['Close']+ma_columns+['BB_Upper','BB_Lower']
        rsi_column=f'RSI{rsi_period}'
        chart_df=technical_df.tail(chart_window).reset_index()
        chart_df=chart_df.rename(columns={chart_df.columns[0]:'Date'})
        try:
            import altair as alt
            base=alt.Chart(chart_df).encode(x=alt.X('Date:T',title='Date'))
            wick=base.mark_rule().encode(y=alt.Y('Low:Q',title='Price'),y2='High:Q',color=alt.condition(alt.datum.Close>=alt.datum.Open,alt.value('#159957'),alt.value('#d64545')))
            body=base.mark_bar(size=5).encode(y='Open:Q',y2='Close:Q',color=alt.condition(alt.datum.Close>=alt.datum.Open,alt.value('#159957'),alt.value('#d64545')))
            bands=base.transform_fold(ma_columns+['BB_Upper','BB_Lower'],as_=['Indicator','Value']).mark_line().encode(y='Value:Q',color='Indicator:N')
            st.altair_chart((wick+body+bands).interactive(),use_container_width=True)
        except Exception:
            st.line_chart(technical_df[chart_columns].tail(chart_window))
            st.caption('Candlestick rendering was unavailable in this environment; the fallback chart still shows price, moving averages, and Bollinger Bands.')
        latest_tech=technical_df.iloc[-1]
        q1,q2,q3=st.columns(3)
        q1.metric(f'RSI ({rsi_period})',f"{latest_tech[rsi_column]:.1f}" if pd.notna(latest_tech[rsi_column]) else 'N/A')
        q2.metric('MACD',f"{latest_tech['MACD']:.2f}" if pd.notna(latest_tech['MACD']) else 'N/A')
        q3.metric('MACD signal',f"{latest_tech['MACD_Signal']:.2f}" if pd.notna(latest_tech['MACD_Signal']) else 'N/A')
        st.markdown('#### RSI and MACD')
        st.line_chart(technical_df[[rsi_column]].tail(chart_window))
        st.line_chart(technical_df[['MACD','MACD_Signal','MACD_Hist']].tail(chart_window))
        st.caption('Technical signals are screening indicators, not standalone buy or sell recommendations. Candlestick patterns use approximate rules and should be confirmed with price, volume, trend, and fundamental analysis.')

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
with portfolio:
    if active_account is None:
        st.info('Create a simulated subscriber account in the sidebar to receive $100,000 virtual cash and use paper trading.')
    else:
        st.caption('Prototype paper trading only. Orders use the latest available adjusted close and are not real trades.')
        current_holdings=active_account['holdings']
        valuation_rows=[]
        total_holdings_value=0.0
        for holding_ticker,position in list(current_holdings.items()):
            try:
                _holding_data=load_stock_cached(holding_ticker)
                _holding_price=float(_holding_data[1]['Close'].iloc[-1])
            except Exception:
                _holding_price=float(position.get('last_price',0.0))
            market_value=position['shares']*_holding_price
            total_holdings_value+=market_value
            valuation_rows.append({'Ticker':holding_ticker,'Shares':position['shares'],'Average cost':position['avg_cost'],'Latest price':_holding_price,'Market value':market_value,'Unrealized P/L':market_value-position['shares']*position['avg_cost']})
        p1,p2,p3=st.columns(3)
        p1.metric('Virtual cash',f"${active_account['cash']:,.2f}")
        p2.metric('Holdings value',f"${total_holdings_value:,.2f}")
        p3.metric('Paper account value',f"${active_account['cash']+total_holdings_value:,.2f}")
        st.markdown(f'''<div class="portfolio-balance-card"><div class="label">Paper portfolio balance</div><div class="amount">${active_account['cash']+total_holdings_value:,.2f}</div><div class="detail">Virtual cash: ${active_account['cash']:,.2f} · Holdings: ${total_holdings_value:,.2f}</div></div>''',unsafe_allow_html=True)
        if valuation_rows:
            st.dataframe(pd.DataFrame(valuation_rows),hide_index=True,use_container_width=True)
        else:
            st.info('No paper positions yet. Analyze a stock or ETF, then place a simulated order below.')
        st.markdown('#### Simulated order')
        with st.expander('Order types explained',expanded=False):
            st.markdown('''
            - **Market order:** executes immediately at the latest simulated price. The exact execution price may differ from the displayed quote in real markets.
            - **Limit order:** executes only at your limit price or a more favorable price. A buy limit executes at or below the limit; a sell limit executes at or above it. Unfilled orders remain open.
            - **Stop-loss order:** a simulated sell order that activates when the price reaches or falls below your stop price. It is designed to limit losses but cannot guarantee an execution price in a real market.
            - **Stop-limit order:** activates at the stop price and then requires the current simulated price to meet your limit price. It offers price control but may remain unfilled.

            These are educational paper-trading simulations. They do not model intraday prices, market gaps, order-book depth, commissions, taxes, or slippage.
            ''')
        order_side=st.radio('Side',['Buy','Sell'],horizontal=True,key='paper_order_side')
        order_type=st.selectbox('Order type',['Market order','Limit order','Stop-loss order','Stop-limit order'],key='paper_order_type')
        order_shares=st.number_input(f'{order_side} shares of {ticker}',min_value=0.0,value=0.0,step=1.0,key='paper_order_shares')
        limit_price=None; stop_price=None
        if order_type=='Limit order':
            limit_price=st.number_input('Limit price',min_value=0.01,value=float(price),step=0.01,key='paper_limit_price')
        elif order_type=='Stop-loss order':
            if order_side!='Sell':
                st.info('A stop-loss order is a sell order. Choose Sell, or use a market/limit order to buy.')
            stop_price=st.number_input('Stop price',min_value=0.01,value=float(price),step=0.01,key='paper_stop_price')
        elif order_type=='Stop-limit order':
            if order_side!='Sell':
                st.info('This prototype supports stop-limit orders as sell orders. Choose Sell.')
            stop_price=st.number_input('Stop price',min_value=0.01,value=float(price),step=0.01,key='paper_stop_limit_stop')
            limit_price=st.number_input('Limit price after stop triggers',min_value=0.01,value=float(price),step=0.01,key='paper_stop_limit_price')
        if st.button(f'Place {order_type} · {order_side} {ticker}',type='primary',key='paper_order_button'):
            if order_shares<=0:
                st.error('Enter a number of shares greater than zero.')
            elif order_type in ('Stop-loss order','Stop-limit order') and order_side!='Sell':
                st.error(f'{order_type} is available as a sell order in this prototype.')
            else:
                order={'ticker':ticker,'side':order_side,'shares':float(order_shares),'order_type':order_type,'created_at':datetime.now(timezone.utc).isoformat()}
                if limit_price is not None: order['limit_price']=float(limit_price)
                if stop_price is not None: order['stop_price']=float(stop_price)
                if order_type=='Market order' or _order_triggered(order,price):
                    _ok,_message=_execute_simulated_order(active_account,order_side,ticker,order_shares,price,order_type)
                    if _ok:
                        _save_subscriber_records(); st.success(_message); st.rerun()
                    else:
                        st.error(_message)
                else:
                    active_account.setdefault('open_orders',[]).append(order)
                    _save_subscriber_records()
                    st.success(f'{order_type} accepted and kept open. It will be checked when a new simulated price is retrieved for {ticker}.')
                    st.rerun()
        if active_account.get('open_orders'):
            st.markdown('#### Open simulated orders')
            st.dataframe(pd.DataFrame(active_account['open_orders']),hide_index=True,use_container_width=True)
        if active_account.get('transactions'):
            st.markdown('#### Paper transaction history')
            transaction_df=pd.DataFrame(active_account['transactions'])
            st.dataframe(transaction_df.sort_values('time',ascending=False).head(100),hide_index=True,use_container_width=True)
            st.download_button('Download paper transaction history',transaction_df.to_csv(index=False).encode('utf-8'),file_name=f'{ticker}_paper_transactions.csv',mime='text/csv',key=f'download_transactions_{ticker}')
        else:
            st.caption('Executed paper transactions will appear here.')
        st.markdown('#### Automatic watchlist')
        watch_rows=list(active_account['watchlist'].values())
        if watch_rows:
            watch_df=pd.DataFrame(watch_rows)
            st.dataframe(watch_df[['Ticker','Date','Open','High','Low','Close','Volume','Warning above','Warning below']],hide_index=True,use_container_width=True)
            st.caption('A ticker is added automatically when you analyze it while signed in. OHLCV values are from the latest available trading day returned by the data provider.')
            st.markdown('##### Set a price warning for the analyzed ticker')
            current_watch=active_account['watchlist'][ticker]
            warn_above=st.number_input('Warn when price reaches or exceeds',min_value=0.0,value=float(current_watch.get('Warning above') or 0.0),step=0.01,key=f'warn_above_{ticker}')
            warn_below=st.number_input('Warn when price falls to or below',min_value=0.0,value=float(current_watch.get('Warning below') or 0.0),step=0.01,key=f'warn_below_{ticker}')
            if st.button(f'Save {ticker} price warnings',key=f'save_warnings_{ticker}'):
                current_watch['Warning above']=warn_above if warn_above>0 else None
                current_watch['Warning below']=warn_below if warn_below>0 else None
                _save_subscriber_records()
                st.success('Price warnings saved for this simulated account.')
            if current_watch.get('Warning above') and current_watch['Close']>=current_watch['Warning above']:
                st.warning(f"{ticker} is at or above your warning price of ${current_watch['Warning above']:,.2f}.")
            if current_watch.get('Warning below') and current_watch['Close']<=current_watch['Warning below']:
                st.warning(f"{ticker} is at or below your warning price of ${current_watch['Warning below']:,.2f}.")
        else:
            st.info('Your watchlist will populate automatically when you analyze a stock or ETF.')

with forum:
    st.markdown('### Subscriber stock and ETF forum')
    st.caption('Share research observations, questions, news, and balanced risk discussions. Forum posts are educational opinions—not recommendations.')
    st.info('Extremely bullish or bearish claims, guaranteed outcomes, alarmist language, market manipulation, spam, and confidential personal information are prohibited.')
    if active_account is None:
        st.warning('Create an account and accept the subscriber terms to participate in the forum.')
    else:
        with st.form('forum_post_form',clear_on_submit=True):
            forum_ticker=st.text_input('Stock or ETF ticker',value=ticker,max_chars=16).strip().upper()
            forum_title=st.text_input('Post title',max_chars=120,placeholder='Example: What risks should investors monitor?')
            forum_type=st.selectbox('Discussion type',['Balanced analysis','Question','News or filing discussion','Risk discussion'])
            forum_body=st.text_area('Your information or thoughts',max_chars=3000,height=150,placeholder='Describe the evidence, assumptions, uncertainty, and possible risks. Avoid guaranteed or extreme claims.')
            forum_submit=st.form_submit_button('Publish post',type='primary')
        if forum_submit:
            _valid,_forum_message=_validate_forum_post(forum_title,forum_body)
            if not forum_ticker or not all(char.isalnum() or char in '.-^' for char in forum_ticker):
                _valid=False
                _forum_message='Enter a valid stock or ETF ticker.'
            if _valid:
                st.session_state['forum_posts'].append({
                    'ticker':forum_ticker,
                    'title':forum_title.strip(),
                    'type':forum_type,
                    'body':forum_body.strip(),
                    'author':active_account.get('display_alias','Subscriber'),
                    'created_at':datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
                })
                _save_subscriber_records()
                st.success('Your balanced discussion post was published.')
            else:
                st.error(_forum_message)
    st.markdown('#### Recent community posts')
    if not st.session_state['forum_posts']:
        st.info('No posts yet. Be the first subscriber to start a balanced discussion.')
    else:
        for _post in reversed(st.session_state['forum_posts'][-50:]):
            with st.container(border=True):
                st.markdown(f"**{_post['title']}** · `{_post['ticker']}`")
                st.caption(f"{_post['type']} · Posted by {_post['author']} · {_post['created_at']}")
                st.write(_post['body'])
    st.caption('Forum moderation is an automated prototype filter and cannot detect every problematic post. Report or avoid relying on any user contribution as financial advice.')

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
