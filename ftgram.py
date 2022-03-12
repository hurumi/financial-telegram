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

from yahooquery import Ticker

# -------------------------------------------------------------------------------------------------
# Globals
# -------------------------------------------------------------------------------------------------

_TELE_TOKEN      = '5294777877:AAHh-x5mD5Pi9fOOl48LLRteH-OHP0snS6Y'
_TELE_CHAT_ID    = '5234829808'

_DEFAULT_PORT    = [ 'MSFT', 'AAPL', 'SPLG', 'QQQ', 'JEPI', 'TSLA' ]
_RSI_THRESHOLD_L = 35
_RSI_THRESHOLD_H = 65
_DAY_THRESHOLD_L = -0.02
_DAY_THRESHOLD_H = 0.02

params = {
    'port'   : _DEFAULT_PORT,
    'RSI_L'  : _RSI_THRESHOLD_L,
    'RSI_H'  : _RSI_THRESHOLD_H,
    'DAY_L'  : _DAY_THRESHOLD_L,
    'DAY_H'  : _DAY_THRESHOLD_H,
}

# -------------------------------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------------------------------

def get_source( _port ):

    tick = Ticker( _port, verify=False )

    info = {}
    info[ 'price'   ] = tick.price
    info[ 'history' ] = tick.history( period='1mo', interval='1d' )

    return info

def get_metric( _info, _port ):
    
    metric   = {}
    rsi_list = []
    day_list = []

    # for each ticker
    for option in _port:
        rsi_list.append( ta.RSI( _info['history']['close'][option] )[-1] )
        day_list.append( _info['price'][option]['regularMarketChangePercent'] )

    metric[ 'RSI' ] = rsi_list
    metric[ 'DAY' ] = day_list

    return metric

def get_description( _metric, _port ):

    desc = []

    # for each ticker
    for idx, option in enumerate( _port ):

        # check RSI downside
        if _metric['RSI'][idx] < params['RSI_L']:
            value = _metric['RSI'][idx]
            thres  = params['RSI_L']
            desc.append( f'[{option:4}]&#8595; RSI({value:.1f})&lt;{thres:.1f}')

        # check DAY downside
        if _metric['DAY'][idx] < params['DAY_L']:
            value = _metric['DAY'][idx]*100
            thres  = params['DAY_L']*100
            desc.append( f'[{option:4}]&#8595; DAY({value:.1f}%)&lt;{thres:.1f}%')

        # check RSI upside
        if _metric['RSI'][idx] > params['RSI_H']:
            value = _metric['RSI'][idx]
            thres  = params['RSI_H']
            desc.append( f'[{option:4}]&#8593; RSI({value:.1f})&gt;{thres:.1f}')

        # check DAY upside
        if _metric['DAY'][idx] > params['DAY_H']:
            value = _metric['DAY'][idx]*100
            thres  = params['DAY_H']*100
            desc.append( f'[{option:4}]&#8593; DAY({value:.1f}%)&gt;{thres:.1f}%')

    return desc

def desc_diff( _prev, _new ):

    _temp = [ elem[:elem.index('(')] for elem in _new ]
    if _prev == _temp: return False
    return True

# -------------------------------------------------------------------------------------------------
# Commandline arguments
# -------------------------------------------------------------------------------------------------

parser = argparse.ArgumentParser( description='Financial Stream' )
parser.add_argument( '--int', '-i', type=int, default=-1, help='loop interval (seconds)' )
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
    metric = get_metric( info, params['port'] )

    # get description
    desc = get_description( metric, params['port'] )

    # output when only entry changes
    if desc_diff( prev_desc, desc ):
        
        # display
        for elem in desc:
            print( elem )

        # telegram
        text = '<code>'+'\n'.join( desc )+'</code>'
        bot.sendMessage( chat_id = _TELE_CHAT_ID, text = text, parse_mode = "HTML" )
    
    # update previous description
    prev_desc = [ elem[:elem.index('(')] for elem in desc ]

    # break condition
    if args.int == -1: break

    # otherwise
    time.sleep( args.int )