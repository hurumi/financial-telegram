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
import pandas as pd

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

from yahooquery import Ticker
from numpy import NaN

# -------------------------------------------------------------------------------------------------
# Globals
# -------------------------------------------------------------------------------------------------

_TELE_TOKEN      = '5294777877:AAHh-x5mD5Pi9fOOl48LLRteH-OHP0snS6Y'
_TELE_CHAT_ID    = '5234829808'

_DEFAULT_PORT    = [ 'MSFT', 'AAPL', 'SPLG', 'QQQ', 'JEPI', 'TSLA', 'DBC', 'IAU', 'NQ=F', 'ES=F', 'YM=F' ]
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

prev_desc = []

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

def get_detection( _metric ):

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

def check_diff( _prev, _new ):

    _temp = [ elem[:elem.index('(')] for elem in _new ]
    if _prev == _temp: return False
    return True

def get_price( _metric ):

    desc = []

    # for each ticker
    for option in _metric.columns:
        price = _metric[option]['regularMarketPrice']
        delta = _metric[option]['regularMarketChangePercent']*100
        desc.append( f'[{option:4}] {price:.1f} ({delta:.1f}%)')

    return desc

def get_rsi( _metric ):

    desc = []

    # for each ticker
    for option in _metric.columns:
        rsi = _metric[option]['RSI']
        desc.append( f'[{option:4}] {rsi:.1f}')

    return desc

# -------------------------------------------------------------------------------------------------
# Callbacks
# -------------------------------------------------------------------------------------------------

def help(update: Update, context: CallbackContext) -> None:
    """Sends explanation on how to use the bot."""
    text  = '/help to show usage\n'
    text += '/start <seconds> to start detector\n'
    text += '/stop to stop detector\n'
    text += '/price to show latest price\n'
    text += '/rsi to show latest rsi\n'
    text += '/detect to run detector'
    update.message.reply_text( text )

def detector(context: CallbackContext) -> None:
    """Run detector."""
    global prev_desc

    job = context.job

    # get source
    info = get_source( params['port'] )

    # get metric
    metric = get_metric( info )

    # get detection
    desc = get_detection( metric )

    print( prev_desc, desc )

    # output when only entry changes
    if check_diff( prev_desc, desc ):
        text = '<code>'+'\n'.join( desc )+'</code>'
        context.bot.send_message( job.context, text, parse_mode = "HTML" )

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

def start(update: Update, context: CallbackContext) -> None:
    """Add a job to the queue."""
    chat_id = update.message.chat_id
    try:
        # args[0] should contain the time for the timer in seconds
        due = int(context.args[0])
        if due < 0:
            update.message.reply_text('Sorry we can not go back to future!')
            return

        job_removed = remove_job_if_exists(str(chat_id), context)
        context.job_queue.run_repeating( detector, due, context=chat_id, name=str(chat_id) )

        text = 'Timer successfully set!'
        if job_removed:
            text += ' Old one was removed.'
        update.message.reply_text(text)

    except (IndexError, ValueError):
        update.message.reply_text('Usage: /set <seconds>')

def stop(update: Update, context: CallbackContext) -> None:
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)
    text = 'Timer successfully cancelled!' if job_removed else 'You have no active timer.'
    update.message.reply_text(text)

def price(update: Update, context: CallbackContext) -> None:
    """Show latest price"""
    info   = get_source( params['port'] )
    metric = get_metric( info )    
    desc   = get_price ( metric )
    text = '<code>'+'\n'.join( desc )+'</code>'
    update.message.reply_text( text, parse_mode = "HTML" )

def rsi(update: Update, context: CallbackContext) -> None:
    """Show latest RSI"""
    info   = get_source( params['port'] )
    metric = get_metric( info )    
    desc   = get_rsi   ( metric )
    text = '<code>'+'\n'.join( desc )+'</code>'
    update.message.reply_text( text, parse_mode = "HTML" )

def detect(update: Update, context: CallbackContext) -> None:
    """Run detector"""
    info   = get_source( params['port'] )
    metric = get_metric( info )    
    desc   = get_detection( metric )
    text = '<code>'+'\n'.join( desc )+'</code>'
    update.message.reply_text( text, parse_mode = "HTML" )       

# -------------------------------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------------------------------

def main():

    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater( _TELE_TOKEN )

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler( CommandHandler("help",   help   ) )
    dispatcher.add_handler( CommandHandler("start",  start  ) )
    dispatcher.add_handler( CommandHandler("stop",   stop   ) )
    dispatcher.add_handler( CommandHandler("price",  price  ) )
    dispatcher.add_handler( CommandHandler("rsi",    rsi    ) )
    dispatcher.add_handler( CommandHandler("detect", detect ) )

    # Start the Bot
    updater.start_polling()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()