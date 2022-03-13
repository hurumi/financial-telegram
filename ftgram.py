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
import argparse
import time
import telegram
import pandas as pd

from yahooquery import Ticker
from numpy import NaN

# -------------------------------------------------------------------------------------------------
# Globals
# -------------------------------------------------------------------------------------------------

_TELE_TOKEN      = '5294777877:AAHh-x5mD5Pi9fOOl48LLRteH-OHP0snS6Y'
_TELE_CHAT_ID    = '5234829808'

_DEFAULT_PORT    = [ 'MSFT', 'AAPL', 'SPLG', 'QQQ', 'JEPI', 'TSLA', 'DBC', 'IAU' ]
_RSI_THRESHOLD_L = 35
_RSI_THRESHOLD_H = 65
_DAY_THRESHOLD_L = -0.02
_DAY_THRESHOLD_H = 0.02

attr_list = { 
    'regularMarketChangePercent':'DAY', 
    'regularMarketPrice':'PRICE',
    'trailingPE':'P/E',
    'fiftyTwoWeekHigh':'52H',
    'fiftyTwoWeekLow':'52L',
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
    'DailyChangeUp': [ 'regularMarketChangePercent', params['DAY_H'],  1, 100 ],
    'DailyChangeDn': [ 'regularMarketChangePercent', params['DAY_L'], -1, 100 ],
    'RSIUp'        : [ 'RSI',                        params['RSI_H'],  1,   1 ],
    'RSIDn'        : [ 'RSI',                        params['RSI_L'], -1,   1 ],
}
# -------------------------------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------------------------------

def get_source( _port ):

    tick = Ticker( _port, verify=False )

    info = {}
    info[ 'price'   ] = tick.price
    info[ 'summary' ] = tick.summary_detail
    info[ 'fund'    ] = tick.fund_holding_info
    info[ 'history' ] = tick.history( period='1mo', interval='1d' )

    return info

def get_metric( _info ):

    # from Ticker.price
    df1 = pd.DataFrame( _info['price'] )
    rm_index = [ x for x in df1.index if x not in attr_list ]
    df1.drop( rm_index, inplace=True )

    # from Ticker.summary_detail
    df2 = pd.DataFrame( _info['summary'] )
    rm_index = [ x for x in df2.index if x not in attr_list ]
    df2.drop( rm_index, inplace=True )

    # concat
    df = pd.concat( [ df1, df2 ] )
    
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

    # compute 52W_H & 52W_L
    for key in df.columns:
        # 52W_L
        try:
            new_entry  = df.loc[ 'regularMarketPrice'][ key ] - df.loc[ 'fiftyTwoWeekLow' ][ key ]
            new_entry /= df.loc[ 'fiftyTwoWeekLow' ][ key ]
            df.loc[ 'fiftyTwoWeekLow' ][ key ] = new_entry
        except:
            df.loc[ 'fiftyTwoWeekLow' ][ key ] = NaN
        
        # 52W_H
        try:
            new_entry  = df.loc[ 'regularMarketPrice'][ key ] - df.loc[ 'fiftyTwoWeekHigh' ][ key ]
            new_entry /= df.loc[ 'fiftyTwoWeekHigh' ][ key ]
            df.loc[ 'fiftyTwoWeekHigh' ][ key ] = new_entry
        except:
            df.loc[ 'fiftyTwoWeekHigh' ][ key ] = NaN

    # replace ETF P/E
    for key in df.columns:
        if _info[ 'price' ][ key ][ 'quoteType' ] != 'ETF': continue
        try:
            df.loc[ 'trailingPE' ][ key ] = _info[ 'fund' ][ key ][ 'equityHoldings' ][ 'priceToEarnings' ]
        except:
            df.loc[ 'trailingPE' ][ key ] = NaN

    # add rows
    df.loc[ 'RSI' ] = rsi_list
    df.loc[ 'CCI' ] = cci_list

    return df

def get_description( _metric ):

    desc = []

    # for each ticker
    for option in _metric.columns:

        # for each filter
        for elem in filter_dict.keys():

            # get filter method
            col = filter_dict[elem][0]  # measure
            thr = filter_dict[elem][1]  # threshold
            mul = filter_dict[elem][2]  # positive or negative
            pct = filter_dict[elem][3]  # percentage conversion

            # check
            if _metric[option][col]*mul > thr*mul:
                name  = attr_list[col]
                value = _metric[option][col]*pct
                thres = thr*pct
                if mul < 0:
                    desc.append( f'[{option:4}]&#8595; {name}({value:.1f})&lt;{thres:.1f}')
                else:
                    desc.append( f'[{option:4}]&#8593; {name}({value:.1f})&gt;{thres:.1f}')

    return desc

def desc_diff( _prev, _new ):

    _temp = [ elem[:elem.index('(')] for elem in _new ]
    if _prev == _temp: return False
    return True

# -------------------------------------------------------------------------------------------------
# Commandline arguments
# -------------------------------------------------------------------------------------------------

parser = argparse.ArgumentParser( description='Financial Stream', 
                                  formatter_class=argparse.ArgumentDefaultsHelpFormatter )
parser.add_argument( '--int', '-i', type=int, default=-1, help='loop interval (seconds) (-1 = no loop)' )
parser.add_argument( '--print', action='store_true', help='print output to screen' )
parser.add_argument( '--telegram', action='store_true', help='send output to telegram' )
args = parser.parse_args()

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------

# telegram bot
bot = telegram.Bot( token = _TELE_TOKEN )

# previous description
prev_desc = []

# infinite loop
while True:

    # get source
    info = get_source( params['port'] )

    # get metric
    metric = get_metric( info )

    # get description
    desc = get_description( metric )

    # output when only entry changes
    if desc_diff( prev_desc, desc ):
        
        # display
        if args.print:
            for elem in desc:
                print( elem )

        # telegram
        if args.telegram:
            text = '<code>'+'\n'.join( desc )+'</code>'
            bot.sendMessage( chat_id = _TELE_CHAT_ID, text = text, parse_mode = "HTML" )
    
    # update previous description
    prev_desc = [ elem[:elem.index('(')] for elem in desc ]

    # break condition
    if args.int == -1: break

    # otherwise
    time.sleep( args.int )