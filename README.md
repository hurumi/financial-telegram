# financial-telegram
Simple financial metric report tool via telegram

```bash
python ftgram.py
```

## Note

**You have to make "token.txt" which includes your telegram token.**

You can refer to [How to create a telegram bot.](https://www.codementor.io/@karandeepbatra/part-1-how-to-create-a-telegram-bot-in-python-in-under-10-minutes-19yfdv4wrq)

## Available Commands

### Help Commands

#### /help: shows usages (= /start)

```
Help
/help: show usages

Ticker
/ticker: show tickers
/add <tickers>: add tickers
/del <tickers>: del tickers

Filter
/run <seconds>: run filter
/stop: stop filter
/filter: run filter once
/thres: show thresholds
/set <rsi|day> <L> <H>: set thres.
/job: show remaining time

Information
/price [<tickers>]: show prices
/pre [<tickers>]: show pre-prices
/post [<tickers>]: show post-prices
/rsi [<tickers>]: show rsi values
/draw [<tickers>] <months>: chart
/index: show index stat
/sector: show sector stat

Screener
/oversold: show 10 RSI<40 tickers
/overbought: show 10 RSI>60 tickers
```

### Ticker Commands

#### /ticker: shows current tickers

Example:
```
/ticker

MSFT AAPL SPLG QQQ JEPI TSLA DBC IAU
```

#### /add \<tickers\>: add tickers

Example:
```
/add NVDA O JPM

MSFT AAPL SPLG QQQ JEPI TSLA DBC IAU NVDA O JPM
```

#### /del \<tickers\>: delete tickers

Example:
```
/del MSFT AAPL

SPLG QQQ JEPI TSLA DBC IAU NVDA O JPM
```
Note: if all tickers are removed, SPY is automatically added

### Filter Commands

#### /run \<seconds\>: run periodic filter

* Run filter function periodically
* Filter checks RSI and daily changes, then notifies if pre-defined conditions are satisfied
* The conditions are defined by two numbers, low threshold and high threshold
* If the metric is lower than low threshold or higher than high threshold, it is notified
* Filter results are displayed only when they are different from previous ones

#### /stop: stop periodic filter

#### /filter: run filter once immediately

Example:
```
/filter

[AAPL]↓ DAY(-2.7)<-2.0
[AAPL]↓ RSI(32.5)<35.0
[TSLA]↓ DAY(-3.6)<-2.0
[DBC ]↓ DAY(-2.9)<-2.0
```

#### /thres: shows current thresholds

Example:
```
/thres

RSI  35.0  65.0
DAY  -2.0   2.0
```

#### /set \<rsi|day\> \<L\> \<H\>: set threshold for rsi or daily change

Example:
```
/set rsi 30 70

RSI  30.0  70.0
DAY  -2.0   2.0
```

#### /job: show remaining time (seconds) if any filter is running

Example:
```
/job

Job will be executed after 840 seconds
```

### Information Commands

#### /price [\<tickers\>]: shows latest prices

Example 1 (for current ticker):
```
/price

[JEPI ]    58.7 ( +0.1%)
[SPLG ]    49.1 ( -0.7%)
[MSFT ]   276.4 ( -1.3%)
[IAU  ]    37.1 ( -1.5%)
[QQQ  ]   318.2 ( -1.9%)
[AAPL ]   150.6 ( -2.7%)
[DBC  ]    25.2 ( -2.9%)
[TSLA ]   766.4 ( -3.6%)
```

Example 2 (for arguments):
```
/price NVDA O

[NVDA ]   245.0 ( +6.6%)
[O    ]    65.6 ( +0.7%)
```

#### /pre [\<tickers\>]: shows latest pre-prices

#### /post [\<tickers\>]: shows latest post-prices

#### /rsi [\<tickers\>]: shows latest rsi

Example 1 (for current ticker):
```
/rsi

[IAU ] 55.9
[DBC ] 54.9
[JEPI] 43.0
[MSFT] 38.6
[SPLG] 38.0
[TSLA] 37.8
[QQQ ] 35.0
[AAPL] 32.5
```

Example 2 (for arguments):
```
/rsi PYPL XOM

[PYPL ] 45.7
[XOM  ] 43.7
```

#### /draw [\<tickers\>] \<month\>: draw relative gain chart

Example 1 (draw msft and aapl chart for 3 month)
```
/draw msft aapl 3
```
<img src="/images/draw-example.jpg" width="50%">

Example 2 (draw current tickers for 6 month)
```
/draw 6
```

Example 3 (draw current tickers for 1 month)
```
/draw
```

#### /index: shows index statistics

Example:
```
/index

[Nasdaq] 12581.2 ( -2.0%)
[S&P500]  4173.1 ( -0.7%)
[DowJon] 32945.2 ( +0.0%)
[Nas(F)] 13045.5 ( +0.0%)
[S&P(F)]  4166.0 ( -0.1%)
[DOW(F)] 32869.0 ( -0.2%)
```

#### /sector: shows sector statistics

Example:
```
/sector

[Financ]    36.9 ( +1.3%)
[Health]   129.8 ( +0.7%)
[Defens]    71.8 ( +0.5%)
[Indust]    98.3 ( +0.3%)
[Utilit]    70.3 ( -0.1%)
[Materi]    81.7 ( -0.1%)
[RealEs]    45.6 ( -0.6%)
[S&P500]   417.0 ( -0.7%)
[Commun]    63.6 ( -1.2%)
[Cyclic]   163.9 ( -1.7%)
[Techno]   141.4 ( -1.9%)
[Energy]    74.5 ( -3.0%)
```

#### /oversold: shows 10 RSI<40 tickers

Example:
```
/oversold

[HD   ] 37.9
[VZ   ] 34.4
[PM   ] 39.2
[UL   ] 36.9
[C    ] 40.0
[MDLZ ] 39.0
[TJX  ] 38.8
[CL   ] 39.5
[KMB  ] 34.6
[BAX  ] 35.7
```

#### /overbought: shows 10 RSI>60 tickers

Example:
```
/overbought

[AAPL ] 62.7
[GOOG ] 60.3
[GOOGL] 61.0
[AMZN ] 62.1
[TSLA ] 66.1
[BRK-B] 73.6
[BRK-A] 72.8
[NVDA ] 64.1
[UNH  ] 64.5
[CVX  ] 66.0
```
