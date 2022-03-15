# financial-telegram
Simple financial metric report tool via telegram

```bash
python ftgram.py
```

## Note

**You have to make "token.txt" which includes your telegram token.**

You can refer to <a href="https://www.codementor.io/@karandeepbatra/part-1-how-to-create-a-telegram-bot-in-python-in-under-10-minutes-19yfdv4wrq" target="_blank">How to create a telegram bot</a>.

## Available Commands

#### /help: shows usages

```
/help to show usages
/ticker to show tickers
/add <tickers> to add tickers
/del <tickers> to del tickers
/start <seconds> to run periodic filter
/stop to stop periodic filter
/filter to run filter once
/thres to show thresholds
/set <rsi | day> <L> <H> to set thres.
/stat <price | rsi> to show stat
/sector to show sector stat
/fear to show fear and greed chart
```

#### /ticker: shows current tickers

Example:
```
/ticker

MSFT AAPL SPLG QQQ JEPI TSLA DBC IAU NQ=F ES=F YM=F
```

#### /add \<tickers\>: add tickers

Example:
```
/add NVDA O JPM
```

#### /del \<tickers\>: delete tickers

Example:
```
/del MSFT AAPL
```
Note: if all tickers are removed, SPY is automatically added

#### /start \<seconds\>: starts periodic filter

* Starts filter function periodically
* Filter checks RSI and daily changes, then notifies if pre-defined conditions are satisfied
* The conditions are defined by two numbers, low threshold and high threshold
* If the metric is lower than low threshold or higher than high threshold, it is notified

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

#### /set \<rsi | day\> \<L\> \<H\>: sets thresholds

Example:
```
/set rsi 30 70
```

#### /stat \<price | rsi\>: shows statistics

Example:
```
/stat rsi

[IAU ] 55.9
[DBC ] 54.9
[JEPI] 43.0
[YM=F] 40.6
[ES=F] 39.1
[MSFT] 38.6
[SPLG] 38.0
[TSLA] 37.8
[NQ=F] 36.4
[QQQ ] 35.0
[AAPL] 32.5
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

#### /fear: shows fear and greed charts
