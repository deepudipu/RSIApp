import streamlit as st
import pandas as pd
import requests
from ta.momentum import RSIIndicator
import time

# -----------------------------
# CONFIG
# -----------------------------
COINGECKO_API = "https://api.coingecko.com/api/v3"
MARKET_CAP_THRESHOLD = 1_000_000_000  # $1 Billion
RSI_PERIOD = 14
RSI_VALUE = st.sidebar.number_input(
    "Minimum RSI Value",
    min_value=0.0,
    max_value=100.0,
    value=20.0,
    step=1.0
)

st.set_page_config(page_title="Crypto RSI Scanner", layout="wide")

st.title("🚀 Crypto RSI Scanner")
st.write(
    "Filters coins with Market Cap > $1B and RSI > 20 on 15m, 4h and 1D timeframes."
)

# -----------------------------
# FUNCTIONS
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

    response = requests.get(url)
    response.raise_for_status()

    df = pd.DataFrame(response.json())

    return df[df["market_cap"] > MARKET_CAP_THRESHOLD]


def calculate_rsi(prices, period=14):
    df = pd.DataFrame(prices, columns=["timestamp", "price"])

    rsi = RSIIndicator(
        close=df["price"],
        window=period
    ).rsi()

    return float(rsi.iloc[-1])


def get_market_chart(coin_id, days):
    """
    CoinGecko provides historical prices.
    We use:
      1 day  -> approximate 15m RSI
      7 days -> approximate 4h RSI
      90 days -> daily RSI
    """

    url = (
        f"{COINGECKO_API}/coins/{coin_id}/market_chart"
        f"?vs_currency=usd&days={days}"
    )

    response = requests.get(url)
    response.raise_for_status()

    return response.json()["prices"]


def get_coin_rsi(coin_id):
    try:
        # Approximation because CoinGecko doesn't provide
        # direct 15m and 4h candles in free API.

        prices_15m = get_market_chart(coin_id, 1)
        prices_4h = get_market_chart(coin_id, 7)
        prices_1d = get_market_chart(coin_id, 90)

        rsi_15m = calculate_rsi(prices_15m)
        rsi_4h = calculate_rsi(prices_4h)
        rsi_1d = calculate_rsi(prices_1d)

        return rsi_15m, rsi_4h, rsi_1d

    except Exception:
        return None, None, None


# -----------------------------
# SCAN BUTTON
# -----------------------------
if st.button("Scan Coins"):

    progress = st.progress(0)

    st.info("Fetching large-cap coins...")

    coins = get_top_coins()

    results = []

    total = len(coins)

    for idx, row in enumerate(coins.iterrows()):

        _, coin = row

        coin_id = coin["id"]
        symbol = coin["symbol"].upper()

        rsi_15m, rsi_4h, rsi_1d = get_coin_rsi(coin_id)

        if (
            rsi_15m is not None
            and rsi_4h is not None
            and rsi_1d is not None
            and rsi_15m > RSI_VALUE
            and rsi_4h > RSI_VALUE
            and rsi_1d > RSI_VALUE
        ):
            results.append(
                {
                    "Rank": coin["market_cap_rank"],
                    "Coin": symbol,
                    "Name": coin["name"],
                    "Market Cap (M$)": f"{coin['market_cap'] / 1_000_000:,.2f} M",
                    "RSI 15m": round(rsi_15m, 2),
                    "RSI 4H": round(rsi_4h, 2),
                    "RSI 1D": round(rsi_1d, 2),
                }
            )

        progress.progress((idx + 1) / total)

        # Avoid API rate limits
        time.sleep(0.2)

    st.success(f"Found {len(results)} matching coins")

    if results:
        df = pd.DataFrame(results)

        st.dataframe(
            df.sort_values("Rank", ascending=True),
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
        st.warning("No coins matched the criteria.")