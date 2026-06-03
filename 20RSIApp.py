import streamlit as st
import pandas as pd
import requests
import time

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="Crypto RSI Scanner",
    layout="wide"
)

# -----------------------------
# CONFIG
# -----------------------------
COINGECKO_API = "https://api.coingecko.com/api/v3"

st.sidebar.header("Scanner Settings")

RSI_VALUE = st.sidebar.number_input(
    "Minimum RSI",
    min_value=0.0,
    max_value=100.0,
    value=30.0,
    step=1.0
)

MARKET_CAP_THRESHOLD = (
    st.sidebar.number_input(
        "Minimum Market Cap (Million USD)",
        min_value=0,
        value=1000,  # 1000M = 1B
        step=100
    )
    * 1_000_000
)

MAX_COINS = st.sidebar.number_input(
    "Coins To Scan",
    min_value=10,
    max_value=250,
    value=100,
    step=10
    )

st.title("🚀 Crypto RSI Scanner")

st.write(
    f"""
    Scans top crypto assets and filters coins where:
    
    - RSI(15m) > {RSI_VALUE}
    - RSI(4H) > {RSI_VALUE}
    - RSI(1D) > {RSI_VALUE}
    - Market Cap > ${MARKET_CAP_THRESHOLD / 1_000_000:,.0f}M
    """
)

# -----------------------------
# COINGECKO COINS
# -----------------------------
@st.cache_data(ttl=300)
def get_top_coins():

    url = (
        f"{COINGECKO_API}/coins/markets"
        "?vs_currency=usd"
        "&order=market_cap_desc"
        "&per_page=250"
        "&page=1"
        "&sparkline=false"
    )

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    df = pd.DataFrame(response.json())

    df = df[df["market_cap"] >= MARKET_CAP_THRESHOLD]

    return df.head(MAX_COINS)

#---------------------------
#gecko market source
#----------------------------
@st.cache_data(ttl=3600)
def get_market_chart(coin_id, days):

    url = (
        f"{COINGECKO_API}/coins/{coin_id}/market_chart"
        f"?vs_currency=usd&days={days}"
    )

    for attempt in range(5):

        response = requests.get(url, timeout=20)

        if response.status_code == 429:
            time.sleep(15)
            continue

        response.raise_for_status()

        return response.json()["prices"]

    raise Exception(
        f"CoinGecko rate limit exceeded for {coin_id}"
    )

    url = (
        f"{COINGECKO_API}/coins/{coin_id}/market_chart"
        f"?vs_currency=usd&days={days}"
    )

    for attempt in range(3):

        response = requests.get(url, timeout=20)

        if response.status_code == 429:

            time.sleep(10)   # wait and retry
            continue

        response.raise_for_status()

        return response.json()["prices"]

    raise Exception(
        f"CoinGecko rate limit exceeded for {coin_id}"
    )

    url = (
        f"{COINGECKO_API}/coins/{coin_id}/market_chart"
        f"?vs_currency=usd&days={days}"
    )

    response = requests.get(url, timeout=20)

    response.raise_for_status()

    return response.json()["prices"]
#------------------------------
# gecko source
#--------------------------------
def get_coingecko_rsi(coin_id):

    prices_15m = get_market_chart(coin_id, 1)
    prices_4h = get_market_chart(coin_id, 7)
    prices_1d = get_market_chart(coin_id, 90)

    closes_15m = [x[1] for x in prices_15m]
    closes_4h = [x[1] for x in prices_4h]
    closes_1d = [x[1] for x in prices_1d]

    return (
        calculate_rsi(closes_15m),
        calculate_rsi(closes_4h),
        calculate_rsi(closes_1d)
    )
# -----------------------------
# RSI CALCULATION
# -----------------------------
def calculate_rsi(closes, period=14):

    series = pd.Series(closes)

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return round(float(rsi.iloc[-1]), 2)


# -----------------------------
# BINANCE KLINES
# -----------------------------
def get_binance_klines(symbol, interval, limit=200):

    url = "https://data-api.binance.vision/api/v3/klines"

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    response = requests.get(
        url,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    closes = [float(candle[4]) for candle in data]

    return closes


# -----------------------------
# RSI FOR COIN
# -----------------------------
def get_coin_rsi(binance_symbol):

    closes_15m = get_binance_klines(
        binance_symbol,
        "15m"
    )

    closes_4h = get_binance_klines(
        binance_symbol,
        "4h"
    )

    closes_1d = get_binance_klines(
        binance_symbol,
        "1d"
    )

    rsi_15m = calculate_rsi(closes_15m)
    rsi_4h = calculate_rsi(closes_4h)
    rsi_1d = calculate_rsi(closes_1d)

    return rsi_15m, rsi_4h, rsi_1d

    try:

        closes_15m = get_binance_klines(
            binance_symbol,
            "15m"
        )

        closes_4h = get_binance_klines(
            binance_symbol,
            "4h"
        )

        closes_1d = get_binance_klines(
            binance_symbol,
            "1d"
        )

        rsi_15m = calculate_rsi(closes_15m)
        rsi_4h = calculate_rsi(closes_4h)
        rsi_1d = calculate_rsi(closes_1d)

        return rsi_15m, rsi_4h, rsi_1d

    except Exception as e:
         st.write(f"{binance_symbol}: {str(e)}")
         return None, None, None


# -----------------------------
# SCAN BUTTON
# -----------------------------
if st.button("Scan Coins"):

    st.info("Fetching coins...")

    coins = get_top_coins()

    results = []

    success_count = 0
    fail_count = 0

    total = len(coins)

    progress = st.progress(0)

    SKIP_SYMBOLS = [
        "USDT",
        "USDC",
        "DAI",
        "FDUSD",
        "TUSD"
    ]

    
    for idx, (_, coin) in enumerate(coins.iterrows()):

        symbol = coin["symbol"].upper()

        if symbol in SKIP_SYMBOLS:
            continue

        # Binance pair
        binance_symbol = f"{symbol}USDT"
       # st.write(f"Testing: {binance_symbol}")  ##for testing which all coins are getting called 
        try:
            rsi_15m, rsi_4h, rsi_1d = get_coin_rsi(
                binance_symbol
            )
            source = "Binance"
        except Exception as binance_error:
        
         
            try:
                time.sleep(1)   # avoid CoinGecko throttling
                rsi_15m, rsi_4h, rsi_1d = get_coingecko_rsi(
                    coin["id"]
                )
        
                source = "CoinGecko"
        
#                st.success(
#                    f"{symbol}: CoinGecko fallback worked"
#                )
        
            except Exception as gecko_error:
        
                st.error(
                    f"{symbol}: CoinGecko failed -> {gecko_error}"
                )
        
                fail_count += 1
                continue
             
                fail_count += 1
                continue
        if rsi_15m is None:

            fail_count += 1

            progress.progress((idx + 1) / total)

            continue

        success_count += 1

        if (
            rsi_15m > RSI_VALUE
            and rsi_4h > RSI_VALUE
            and rsi_1d > RSI_VALUE
        ):

            results.append(
                {
                    "Rank": coin["market_cap_rank"],
                    "Coin": symbol,
                    "Name": coin["name"],
                    "Source": source,
                    "Market Cap (M$)": round(
                        coin["market_cap"] / 1_000_000,
                        2
                    ),
                    "RSI 15m": rsi_15m,
                    "RSI 4H": rsi_4h,
                    "RSI 1D": rsi_1d,
                }
            )

        progress.progress((idx + 1) / total)

        # Small pause
        time.sleep(0.05)

    st.success(
        f"Found {len(results)} matching coins"
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Successful RSI Calculations",
            success_count
        )

    with col2:
        st.metric(
            "Failed Coins",
            fail_count
        )

    if results:

        df = pd.DataFrame(results)

        df = df.sort_values(
            "Rank",
            ascending=True
        )

        st.dataframe(
            df,
            use_container_width=True
        )

        csv = df.to_csv(index=False)

        st.download_button(
            "Download CSV",
            csv,
            "crypto_rsi_scan.csv",
            "text/csv"
        )

    else:

        st.warning(
            "No coins matched the criteria."
        )
