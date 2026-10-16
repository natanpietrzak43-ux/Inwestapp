# Indicator sources and attribution

## B-Xtrender — QuantTherapy

B-Xtrender formula attribution: **© QuantTherapy**. The published Pine source
states **Mozilla Public License 2.0**. The independent Python adaptation in
[custom_indicators.py](custom_indicators.py) is made available under MPL 2.0;
its complete source is included in every source ZIP. The license text is in
[LICENSES/MPL-2.0.txt](LICENSES/MPL-2.0.txt). This notice does not change the
license of unrelated project files or claim QuantTherapy endorses this app.

Reference supplied by the user:
https://wild.pynesys.io/scripts/b-xtrender-backtest-edition-quanttherapy-uCWPAPT2

Verified public Pine copy, pinned to the inspected revision:
https://github.com/hasnocool/tradingview-pine-scripts/blob/69969aeaf271b2f7b5a7632a1bde43069a0cbe26/B-Xtrender%20%5BBacktest%20Edition%5D%20%40QuantTherapy.pine

The user-supplied site and TradingView could not be fetched directly in the
cloud environment. The public copy names QuantTherapy, includes the MPL 2.0
header and shows the two formulas and default parameters:

- short = RSI15(EMA5(close) − EMA20(close)) − 50;
- long = RSI15(EMA20(close)) − 50.

This app implements those formulas, histogram sign/slope colors and first-price
EMA initialization. RSI uses a Wilder SMA seed; no losses gives 100, including a
flat input. Old EMA20/50/200 and RSI14 keep their existing implementation.

The app additionally offers a standard Tillson T3(5, 0.7) smoothing line and
causally confirmed turning points, as visual context. This is an explicit app
addition to the linked Backtest Edition, not an assertion that every plot is
identical to that source. A public mathematical reference consulted for T3:
https://github.com/Zool-in/StockScreener/blob/1c565330b9beb2eacfa758338ca1212b614d1fc0/js/core/math.js

The app's five-group rules, strict all-selected confirmation, ADX/OBV/Bollinger
filters, ATR stops, next-open execution and history guard are its own model.
It does not reproduce the source strategy's percent trailing stop or short
orders. Exchange feeds, history start and initialization can produce different
numbers from a TradingView chart. No runtime TradingView connection is needed.

## EMA 21 / 89 / 200 — M1 / M2 / M3

The user specified these periods/colors under the name **EMA en 1 Indicador**
by **Jesús Mercado**. This app independently implements standard close-based
EMA21 (green), EMA89 (white with a dark readability outline) and EMA200 (red).
It uses the user's supplied configuration; the original Mercado script was
not available for direct code comparison. Attribution identifies the requested
configuration, not a claim of endorsement or copying of unavailable code.
