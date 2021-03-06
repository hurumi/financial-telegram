#
# Financial alert
#

# disable SSL warnings
import urllib3
urllib3.disable_warnings( urllib3.exceptions.InsecureRequestWarning )

# -------------------------------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------------------------------

import talib as ta
import pandas as pd
import os
import json
import requests
import re

import matplotlib as mat

# use agg backend to suppress warnings
mat.use('agg')

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

from yahooquery import Ticker
from numpy import isnan
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

# -------------------------------------------------------------------------------------------------
# Globals
# -------------------------------------------------------------------------------------------------

_TOKEN_PATH      = './token.txt'
_PARAM_FILE      = './param.json'

_DEFAULT_PORT    = [ 'SPY', 'QQQ' ]
_RSI_THRESHOLD_L = 35
_RSI_THRESHOLD_H = 65
_DAY_THRESHOLD_L = -0.02
_DAY_THRESHOLD_H = 0.02

attr_list = { 
    'regularMarketChangePercent':'DAY', 
    'regularMarketPrice':'PRICE',
    'preMarketChangePercent':'DAY', 
    'preMarketPrice':'PRICE',
    'postMarketChangePercent':'DAY', 
    'postMarketPrice':'PRICE',
}
params = {
    'port'   : _DEFAULT_PORT,
    'RSI_L'  : _RSI_THRESHOLD_L,
    'RSI_H'  : _RSI_THRESHOLD_H,
    'DAY_L'  : _DAY_THRESHOLD_L,
    'DAY_H'  : _DAY_THRESHOLD_H,
}
# filtername: [ measure, threshold, pos/neg factor, percentage factor ]
filter_dict = {
    'DailyChangeUp': [ 'regularMarketChangePercent', 'DAY_H',  1, 100 ],
    'DailyChangeDn': [ 'regularMarketChangePercent', 'DAY_L', -1, 100 ],
    'RSIUp'        : [ 'RSI',                        'RSI_H',  1,   1 ],
    'RSIDn'        : [ 'RSI',                        'RSI_L', -1,   1 ],
}
sector_tickers = {
    'XLK': 'Techno',
    'XLC': 'Commun',
    'XLY': 'Cyclic',
    'XLF': 'Financ',
    'XLV': 'Health',
    'XLP': 'Defens',
    'XLI': 'Indust',
    'XLRE':'RealEs',
    'XLE': 'Energy', 
    'XLU': 'Utilit', 
    'XLB': 'Materi',
    'SPY': 'S&P500',
}
index_tickers = {
    '^IXIC': 'Nasdaq', 
    '^GSPC': 'S&P500', 
    '^DJI':  'DowJon',
    'NQ=F':  'Nas(F)',
    'ES=F':  'S&P(F)',
    'YM=F':  'DOW(F)',
}
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) \
            AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36"
}
finviz_info = {
    'RSI_OVERSOLD(40)':   'https://finviz.com/screener.ashx?v=171&f=ta_rsi_os40&ft=3&o=-marketcap',
    'RSI_OVERBOUGHT(60)': 'https://finviz.com/screener.ashx?v=171&f=ta_rsi_ob60&ft=3&o=-marketcap',   
}

prev_desc = []

# -------------------------------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------------------------------

def escape_markdown( text ):
    # Use {} and reverse markdown carefully.
    parse = re.sub(r"([_*\[\]()~`>\#\+\-=|\.!])", r"\\\1", text)
    reparse = re.sub(r"\\\\([_*\[\]()~`>\#\+\-=|\.!])", r"\1", parse)
    return reparse

def save_params( _params ):

    # save to file
    with open( _PARAM_FILE, 'w' ) as fp:
        json.dump( _params, fp, indent=4 )

    return

def load_params():

    # load from file
    with open( _PARAM_FILE, 'r' ) as fp:
        ret = json.load( fp )

    return ret

def get_source( _port ):

    tick = Ticker( _port, verify=False, asynchronous=True )

    info = {}
    info[ 'ticker'  ] = tick
    info[ 'price'   ] = tick.price
    info[ 'history' ] = tick.history( period='1y', interval='1d' )

    return info

def get_metric( _info ):

    # from Ticker.price
    df = pd.DataFrame( _info['price'] )
    rm_index = [ x for x in df.index if x not in attr_list ]
    df.drop( rm_index, inplace=True )

    # compute RSI & CCI
    rsi_list = {}
    cci_list = {}
    for key in df.columns:
        
        # compute RSI
        rsi = ta.RSI( _info['history']['close'][ key ] )[-1]   
        rsi_list[ key ] = rsi
        
        # compute CCI
        cci = ta.CCI( _info['history']['high'][ key ], _info['history']['low'][ key ], _info['history']['close'][ key ] )[-1] 
        cci_list[ key ] = cci

    # add rows
    df.loc[ 'RSI' ] = rsi_list
    df.loc[ 'CCI' ] = cci_list

    # column reordering
    df = df[ _info['ticker'].symbols ]

    return df

def apply_filter( _metric ):

    desc = []

    # for each ticker
    for option in _metric.columns:

        # for each filter
        for elem in filter_dict.keys():

            # get filter method
            col = filter_dict[elem][0]              # measure
            thr = params[ filter_dict[elem][1] ]    # threshold
            mul = filter_dict[elem][2]              # positive or negative
            pct = filter_dict[elem][3]              # percentage conversion

            # check
            if _metric[option][col]*mul > thr*mul:
                name  = attr_list[col] if col in attr_list else col
                value = _metric[option][col]*pct
                thres = thr*pct
                if mul < 0:
                    desc.append( f'<code>[{option:5}]&#8595; {name}({value:.1f})&lt;{thres:.1f}</code>')
                else:
                    desc.append( f'<code>[{option:5}]&#8593; {name}({value:.1f})&gt;{thres:.1f}</code>')

    return desc

def check_diff( _prev, _new ):

    _temp = [ elem[:elem.index('(')] for elem in _new ]
    if _prev == _temp: return False
    return True

def get_price( _metric ):

    temp = []

    # for each ticker
    for option in _metric.columns:
        price = _metric[option]['regularMarketPrice']
        delta = _metric[option]['regularMarketChangePercent']*100
        temp.append( [ delta, option, price ] )
    
    temp.sort( reverse=True )
    desc = [ f'<code>[{option:5}] {price:7.1f} ({delta:+5.1f}%)</code>' for delta, option, price in temp ]

    return desc

def get_pre( _metric ):

    temp = []

    # for each ticker
    for option in _metric.columns:
        if isnan( _metric[option]['preMarketPrice'] ) == False:
            price = _metric[option]['preMarketPrice']
            delta = _metric[option]['preMarketChangePercent']*100
        else:
            price = _metric[option]['regularMarketPrice']
            delta = 0.0
        temp.append( [ delta, option, price ] )
    
    temp.sort( reverse=True )
    desc = [ f'<code>[{option:5}] {price:7.1f} ({delta:+5.1f}%)</code>' for delta, option, price in temp ]

    return desc

def get_post( _metric ):

    temp = []

    # for each ticker
    for option in _metric.columns:
        if isnan( _metric[option]['postMarketPrice'] ) == False:
            price = _metric[option]['postMarketPrice']
            delta = _metric[option]['postMarketChangePercent']*100       
        else:
            price = _metric[option]['regularMarketPrice']
            delta = 0.0             
        temp.append( [ delta, option, price ] )
    
    temp.sort( reverse=True )
    desc = [ f'<code>[{option:5}] {price:7.1f} ({delta:+5.1f}%)</code>' for delta, option, price in temp ]

    return desc

def get_index( _metric ):

    temp = []

    # for each ticker
    for option in _metric.columns:
        price = _metric[option]['regularMarketPrice']
        delta = _metric[option]['regularMarketChangePercent']*100
        name  = index_tickers[ option ]
        temp.append( [ delta, name, price ] )

    # temp.sort( reverse=True )
    desc = [ f'<code>[{name:6}] {price:7.1f} ({delta:+5.1f}%)</code>' for delta, name, price in temp ]

    return desc

def get_sector( _metric ):

    temp = []

    # for each ticker
    for option in _metric.columns:
        price = _metric[option]['regularMarketPrice']
        delta = _metric[option]['regularMarketChangePercent']*100
        name  = sector_tickers[ option ]
        temp.append( [ delta, name, price ] )

    temp.sort( reverse=True )
    desc = [ f'<code>[{name:6}] {price:7.1f} ({delta:+5.1f}%)</code>' for delta, name, price in temp ]

    return desc

def get_rsi( _metric ):

    temp = []

    # for each ticker
    for option in _metric.columns:
        rsi = _metric[option]['RSI']
        temp.append( [ rsi, option ] )
    
    temp.sort( reverse=True )
    desc = [ f'<code>[{option:5}] {rsi:.1f}</code>' for rsi, option in temp ]

    return desc

def get_info( _ticker ):

    # get information
    t = Ticker( _ticker, verify=False )
    p = t.price[_ticker]

    # quote type
    quoteType = p['quoteType']

    # prepare output
    desc = []

    # basic information
    desc.append( f'<code>Ticker   : {_ticker.upper()}</code>' )
    desc.append( f'<code>Name     : {p["shortName"]}</code>' )
    desc.append( f'<code>Type     : {quoteType}</code>' )

    # additional information
    if quoteType == 'EQUITY':
        sd = t.summary_detail [_ticker]
        sp = t.summary_profile[_ticker]
        if 'sector' in sp: 
            desc.append( f'<code>Sector   : {sp["sector"]}</code>' )
        if 'industry' in sp: 
            desc.append( f'<code>Industry : {sp["industry"]}</code>' )
        if 'marketCap' in p: 
            desc.append( f'<code>Marketcap: {p["marketCap"]/1000000000:.2f}B</code>' )
        if 'trailingPE' in sd: 
            desc.append( f'<code>P/E      : {sd["trailingPE"]:.2f}</code>' )
        if 'forwardPE' in sd: 
            desc.append( f'<code>Fwd P/E  : {sd["forwardPE"]:.2f}</code>' )            
        if 'dividendYield' in sd:
            desc.append( f'<code>Dividend : {sd["dividendYield"]*100:.2f}%</code>' )
    elif quoteType == 'ETF':
        sd = t.summary_detail   [_ticker]
        f  = t.fund_holding_info[_ticker]
        pr = t.fund_profile     [_ticker]
        if 'categoryName' in pr:
            desc.append( f'<code>Category : {pr["categoryName"]}</code>' )
        if 'equityHoldings' in f and 'priceToEarnings' in f['equityHoldings']:
            desc.append( f'<code>P/E      : {f["equityHoldings"]["priceToEarnings"]:.2f}</code>' )
        if 'yield' in sd:
            desc.append( f'<code>Dividend : {sd["yield"]*100:.2f}%</code>' )
        if 'holdings' in f:
            desc.append( f'<code>[ Top Holdings ]</code>' )
            for elem in f['holdings']:
                desc.append( f'<code>{elem["holdingName"][:15]:15} {elem["holdingPercent"]*100:6.2f}%</code>' )
        if 'sectorWeightings' in f:
            desc.append( f'<code>[ Sector Weightings ]</code>' )
            se_dict = {}
            for elem in f['sectorWeightings']: se_dict.update( elem )
            for sec, val in se_dict.items():
                desc.append( f'<code>{sec[:15]:15} {val*100:6.2f}%</code>' )              

    return desc

def get_num_points( index, dmonth ):

    last = index[-1]
    d    = relativedelta( months = dmonth )
    num_points = len( index [ index >= ( last - d ) ] )

    return num_points

def get_chart( _info, dmonth ):

    # data source
    source = _info['history']['close']

    # for all tickers
    sr_list = []
    for option in _info['ticker'].symbols:
        # compute number of points
        num_points = get_num_points( source[option].index, dmonth )

        # prepare data
        _data = source[option].rename(option)[-num_points:]
        _data = _data[ ~_data.index.duplicated() ]  # remove duplicated index before concat

        # normalize
        _data = ( ( _data / _data[0] ) - 1 ) * 100.

        # add to list
        sr_list.append( _data )

    df = pd.DataFrame( pd.concat( sr_list, axis=1 ) ).dropna()
    df.index = pd.to_datetime( df.index )

    # use matplotlib
    ax = df.plot( y=_info['ticker'].symbols )

    # customization
    mat.pyplot.xlabel( 'Date'       )
    mat.pyplot.ylabel( 'Change (%)' )
    mat.pyplot.grid  ( True         )
    ax.yaxis.set_major_formatter( mat.ticker.PercentFormatter() )

    # save to file
    mat.pyplot.savefig( '_tmp.png', bbox_inches='tight' )

    return '_tmp.png'

def crawl_finviz_df( url ):

    session = requests.Session()
    website = session.get(url, headers=headers, timeout=10, verify=False)

    soup = BeautifulSoup(website.text, "lxml")

    url_all1 = soup.find_all('a',  {'class':"screener-link-primary"})
    url_all2 = soup.find_all('a',  {'class':"screener-link"})
    td_col   = soup.find_all('td', {'class':"table-top cursor-pointer"})

    col_list  = [ elem.text for elem in td_col ]
    col_list  = col_list[1:] # remove No.
    tick_list = [ elem.text for elem in url_all1 ]
    n         = len( url_all2 )
    ncol      = len( col_list )

    df = pd.DataFrame()
    df[ col_list[0] ] = tick_list

    # for each column
    for idx, col in enumerate( col_list[1:] ):
        val_list = [ url_all2[i].text for i in range( idx+1, n, ncol ) ]
        df[ col ] = val_list
 
    return df

# -------------------------------------------------------------------------------------------------
# Callbacks
# -------------------------------------------------------------------------------------------------

def help(update: Update, context: CallbackContext) -> None:
    """Sends explanation on how to use the bot."""
    
    text  = '*Help*\n'
    text += escape_markdown( '/help: show usages\n' )
    text += '\n'

    text += '*Ticker*\n'
    text += escape_markdown( '/ticker: show tickers\n' +
                             '/add <tickers>: add tickers\n' +
                             '/del <tickers>: del tickers\n' )
    text += '\n'
    
    text += '*Filter*\n'
    text += escape_markdown( '/run <seconds>: run filter\n' +
                             '/stop: stop filter\n' +
                             '/filter: run filter once\n' +
                             '/thres: show thresholds\n' +
                             '/set <rsi|day> <L> <H>: set thres.\n' +
                             '/job: show remaining time\n' )
    text += '\n'                             
    
    text += '*Information*\n'
    text += escape_markdown( '/price [<tickers>]: show prices\n' +
                             '/pre [<tickers>]: show pre-prices\n' +
                             '/post [<tickers>]: show post-prices\n' +
                             '/rsi [<tickers>]: show rsi values\n' +
                             '/info ticker: show information\n' +
                             '/draw [<tickers>] <months>: chart\n' +
                             '/index: show index stat\n' +
                             '/sector: show sector stat\n' )
    text += '\n'                             
    
    text += '*Screener*\n'
    text += escape_markdown( '/oversold: show 10 RSI<40 tickers\n' +
                             '/overbought: show 10 RSI>60 tickers\n' )

    update.message.reply_text( text, parse_mode="MarkdownV2" )

def ticker(update: Update, context: CallbackContext) -> None:
    """Show tickers"""
    desc   = params['port']
    text = '<code>'+' '.join( desc )+'</code>'
    update.message.reply_text( text, parse_mode = "HTML" )

def add(update: Update, context: CallbackContext) -> None:
    """Add tickers"""
    if len( context.args ) > 0:
        t = Ticker( context.args, verify=False, validate=True )
        for elem in context.args:
            if elem.upper() in t.symbols and elem.upper() not in params['port']:
                params['port'].append( elem.upper() )
        save_params( params )
        ticker( update, context )
    else:
        update.message.reply_text('Usage: /add <tickers> to add tickers')

def delete(update: Update, context: CallbackContext) -> None:
    """Del tickers"""
    if len( context.args ) > 0:
        for elem in context.args:
            params['port'].remove( elem.upper() )

        # at least one ticker should exist
        if len( params['port'] ) == 0:
            update.message.reply_text( 'At least one ticker should exist, SPY is added by default' )
            params['port'].append( 'SPY' )

        save_params( params )
        ticker( update, context )
    else:
        update.message.reply_text('Usage: /del <tickers> to del tickers')

def periodic_filter(context: CallbackContext) -> None:
    """Run filter."""
    global prev_desc

    job = context.job

    # get source
    info = get_source( params['port'] )

    # get metric
    metric = get_metric( info )

    # apply filter
    desc = apply_filter( metric )

    # output when only entry changes
    if check_diff( prev_desc, desc ):
        if desc != []:
            text = '\n'.join( desc )
            context.bot.send_message( job.context, text, parse_mode = "HTML" )
        else:
            context.bot.send_message( job.context, "No filtered results" )

    # update detection
    prev_desc = [ elem[:elem.index('(')] for elem in desc ]

def remove_job_if_exists(name: str, context: CallbackContext) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True

def runft(update: Update, context: CallbackContext) -> None:
    """Add a job to the queue."""
    chat_id = update.message.chat_id
    try:
        # args[0] should contain the time for the timer in seconds
        due = int(context.args[0])
        if due < 0:
            update.message.reply_text('Sorry we can not go back to future!')
            return

        job_removed = remove_job_if_exists(str(chat_id), context)
        context.job_queue.run_repeating( periodic_filter, due, context=chat_id, name=str(chat_id) )

        text = 'Timer successfully set!'
        if job_removed:
            text += ' Old one was removed.'
        update.message.reply_text(text)

    except (IndexError, ValueError):
        update.message.reply_text('Usage: /run <seconds>')

def stop(update: Update, context: CallbackContext) -> None:
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)
    text = 'Timer successfully cancelled!' if job_removed else 'You have no active timer.'
    update.message.reply_text(text)

def price(update: Update, context: CallbackContext) -> None:
    """Show latest price"""
    if len( context.args ) > 0:
        port_list = Ticker( context.args, verify=False, validate=True ).symbols
        if port_list == []: port_list = params['port']
    else:
        port_list = params['port']

    info   = get_source( port_list )
    metric = get_metric( info      )
    desc   = get_price ( metric    )
    text   = '\n'.join ( desc      )
    update.message.reply_text( text, parse_mode = "HTML" )

def pre(update: Update, context: CallbackContext) -> None:
    """Show latest price"""
    if len( context.args ) > 0:
        port_list = Ticker( context.args, verify=False, validate=True ).symbols
        if port_list == []: port_list = params['port']
    else:
        port_list = params['port']

    info   = get_source( port_list )
    metric = get_metric( info      )
    desc   = get_pre   ( metric    )
    text   = '\n'.join ( desc      )
    update.message.reply_text( text, parse_mode = "HTML" )    

def post(update: Update, context: CallbackContext) -> None:
    """Show latest price"""
    if len( context.args ) > 0:
        port_list = Ticker( context.args, verify=False, validate=True ).symbols
        if port_list == []: port_list = params['port']
    else:
        port_list = params['port']

    info   = get_source( port_list )
    metric = get_metric( info      )
    desc   = get_post  ( metric    )
    text   = '\n'.join ( desc      )
    update.message.reply_text( text, parse_mode = "HTML" )  

def rsi(update: Update, context: CallbackContext) -> None:
    """Show latest rsi"""
    if len( context.args ) > 0:
        port_list = Ticker( context.args, verify=False, validate=True ).symbols
        if port_list == []: port_list = params['port']
    else:
        port_list = params['port']

    info   = get_source( port_list )
    metric = get_metric( info      )
    desc   = get_rsi   ( metric    )
    text   = '\n'.join ( desc      )
    update.message.reply_text( text, parse_mode = "HTML" )       

def info(update: Update, context: CallbackContext) -> None:
    """Show information of single ticker"""
    if len( context.args ) > 0:
        desc = get_info ( context.args[0] )
        text = '\n'.join( desc            )
        update.message.reply_text( text, parse_mode = "HTML" )
    else:
        update.message.reply_text( 'Usage: /info ticker: show information' )

def draw(update: Update, context: CallbackContext) -> None:
    """Draw chart"""
    try:
        if len( context.args ) > 1:
            port_list =      context.args[:-1]
            dmonth    = int( context.args[ -1] )
        elif len( context.args ) == 1:
            port_list =      params['port']
            dmonth    = int( context.args[ -1] )
        else:
            port_list = params['port']
            dmonth    = 1
        
        info   = get_source( port_list    )
        chart  = get_chart ( info, dmonth )

        update.message.reply_photo( photo=open( chart, 'rb') )
        os.remove( chart )
    except:
        update.message.reply_text( 'Usage: /draw [<tickers>] <months>: draw chart' )

def filter(update: Update, context: CallbackContext) -> None:
    """Run detector"""
    info   = get_source  ( params['port'] )
    metric = get_metric  ( info )    
    desc   = apply_filter( metric )

    if desc != []:
        text = '\n'.join( desc )
        update.message.reply_text( text, parse_mode = "HTML" )
    else:
        update.message.reply_text( "No filtered results" )

def thres(update: Update, context: CallbackContext) -> None:
    """Show thresholds."""
    r1 = params['RSI_L'];     r2 = params['RSI_H'];     text  = f'<code>RSI {r1:5.1f} {r2:5.1f}</code>\n'
    r1 = params['DAY_L']*100; r2 = params['DAY_H']*100; text += f'<code>DAY {r1:5.1f} {r2:5.1f}</code>'
    update.message.reply_text( text, parse_mode = "HTML" )

def setthr(update: Update, context: CallbackContext) -> None:
    """Set thresholds."""
    try:
        if context.args[0].upper() == 'RSI':
            try:
                params['RSI_L'] = float( context.args[1] )
                params['RSI_H'] = float( context.args[2] )
            except:
                pass
        if context.args[0].upper() == 'DAY':
            try:
                params['DAY_L'] = float( context.args[1] )/100
                params['DAY_H'] = float( context.args[2] )/100
            except:
                pass

        # save parameter
        save_params( params )    

        # show current threshold
        thres( update, context )
    except:
        update.message.reply_text( 'Usage: /set <rsi | price> <low> <high>' )

def index(update: Update, context: CallbackContext) -> None:
    """Show index price"""
    info   = get_source( index_tickers )
    metric = get_metric( info )
    desc   = get_index ( metric )
    text   = '\n'.join( desc )
    update.message.reply_text( text, parse_mode = "HTML" )

def sector(update: Update, context: CallbackContext) -> None:
    """Show sector price"""
    info   = get_source( sector_tickers )
    metric = get_metric( info )
    desc   = get_sector( metric )
    text   = '\n'.join( desc )
    update.message.reply_text( text, parse_mode = "HTML" )

def job(update: Update, context: CallbackContext) -> None:
    """Show currently scheduled job"""
    chat_id  = update.message.chat_id
    job_list = context.job_queue.get_jobs_by_name( name=str(chat_id) )

    if len( job_list ) == 0:
        update.message.reply_text( "No currently scheduled job" )
    else:
        job    = job_list[0]
        date_n = job.next_t
        date_t = datetime.now( timezone.utc )
        remain = ( date_n - date_t ).seconds
        update.message.reply_text( f'Job will be executed after {remain} seconds' )

def oversold(update: Update, context: CallbackContext) -> None:
    """Show 10 RSI<40 tickers"""
    url    = finviz_info[ 'RSI_OVERSOLD(40)' ]
    result = crawl_finviz_df( url )
    rsi_dt = dict( zip( result['Ticker'], result['RSI'] ) )
    desc   = [ f'<code>[{key:5}] {float(val):.1f}</code>' for key, val in rsi_dt.items() ]
    text   = '\n'.join( desc[:10] )
    update.message.reply_text( text, parse_mode = "HTML" )

def overbought(update: Update, context: CallbackContext) -> None:
    """Show 10 RSI>60 tickers"""
    url    = finviz_info[ 'RSI_OVERBOUGHT(60)' ]
    result = crawl_finviz_df( url )
    rsi_dt = dict( zip( result['Ticker'], result['RSI'] ) )
    desc   = [ f'<code>[{key:5}] {float(val):.1f}</code>' for key, val in rsi_dt.items() ]
    text   = '\n'.join( desc[:10] )
    update.message.reply_text( text, parse_mode = "HTML" )

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------

def main():

    global params

    # load token
    try:
        token = open( _TOKEN_PATH, 'r' ).readline().rstrip()
    except:
        print( 'Make token.txt which includes your token value' )
        exit()

    # check if param file exists
    if os.path.isfile( _PARAM_FILE ): params=load_params()
    else: save_params( params )

    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater( token )

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler( CommandHandler("help",       help       ) )
    dispatcher.add_handler( CommandHandler("start",      help       ) )
    dispatcher.add_handler( CommandHandler("ticker",     ticker     ) )
    dispatcher.add_handler( CommandHandler("add",        add        ) )
    dispatcher.add_handler( CommandHandler("del",        delete     ) )
    dispatcher.add_handler( CommandHandler("run",        runft      ) )
    dispatcher.add_handler( CommandHandler("stop",       stop       ) )
    dispatcher.add_handler( CommandHandler("filter",     filter     ) )
    dispatcher.add_handler( CommandHandler("thres",      thres      ) )
    dispatcher.add_handler( CommandHandler("set",        setthr     ) )
    dispatcher.add_handler( CommandHandler("price",      price      ) )
    dispatcher.add_handler( CommandHandler("pre",        pre        ) )
    dispatcher.add_handler( CommandHandler("post",       post       ) )
    dispatcher.add_handler( CommandHandler("rsi",        rsi        ) )
    dispatcher.add_handler( CommandHandler("draw",       draw       ) )
    dispatcher.add_handler( CommandHandler("info",       info       ) )    
    dispatcher.add_handler( CommandHandler("index",      index      ) )
    dispatcher.add_handler( CommandHandler("sector",     sector     ) )
    dispatcher.add_handler( CommandHandler("job",        job        ) )
    dispatcher.add_handler( CommandHandler("oversold",   oversold   ) )
    dispatcher.add_handler( CommandHandler("overbought", overbought ) )

    # Start the Bot
    updater.start_polling()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()
