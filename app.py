import streamlit as st
import sqlite3
import hashlib
import threading
import pygame
from yfinance import Ticker
import pandas as pd
import plotly.express as px
import requests
from newsapi import NewsApiClient
import os
from pathlib import Path
import base64
from datetime import datetime
import time

# Constants
INITIAL_BALANCE = 10000
UPDATE_INTERVAL = 60
DEFAULT_CURRENCY = 'USD'
STOCK_LIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "BRK-B", "V", "JPM"]
TIME_RANGES = {
    '1 Day': '1d',
    '5 Days': '5d',
    '1 Month': '1mo',
    '3 Months': '3mo',
    '6 Months': '6mo',
    '1 Year': '1y',
    '5 Years': '5y',
    '10 Years': '10y',
    'Max': 'max'
}
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD"]

# Initialize NewsAPI Client
NEWS_API_KEY = 'your_newsapi_key_here'
newsapi = NewsApiClient(api_key=NEWS_API_KEY)

# Initialize pygame for music
def initialize_music():
    if 'music_initialized' not in st.session_state:
        try:
            pygame.mixer.init()
            pygame.mixer.music.load('trade.mp3')
            pygame.mixer.music.play(-1)
            st.session_state['music_initialized'] = True
        except pygame.error as e:
            st.error(f"Failed to load or play the music: {str(e)}. Please check that 'trade.mp3' exists in the correct directory.")

# Database setup
def setup_database():
    conn = sqlite3.connect('trading_game.db', check_same_thread=False)
    cursor = conn.cursor()

    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        balance REAL,
        initial_balance REAL,
        currency TEXT DEFAULT 'USD'
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS portfolios (
        username TEXT,
        ticker TEXT,
        shares REAL,
        initial_investment REAL,
        PRIMARY KEY (username, ticker),
        FOREIGN KEY (username) REFERENCES users (username)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS financial_logs (
        username TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        total_value REAL,
        FOREIGN KEY (username) REFERENCES users (username)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        username TEXT,
        action TEXT,
        ticker TEXT,
        amount REAL,
        price REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    return conn

# Ensure Database Schema
def ensure_database_schema():
    conn = sqlite3.connect('trading_game.db')
    c = conn.cursor()
    
    # Ensure the users table exists and has the required columns
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        balance REAL,
        initial_balance REAL,
        currency TEXT DEFAULT 'USD'
    )
    ''')

    # Check if the initial_balance column exists, if not, add it
    c.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in c.fetchall()]
    if 'initial_balance' not in columns:
        c.execute(f"ALTER TABLE users ADD COLUMN initial_balance REAL DEFAULT {INITIAL_BALANCE}")
        conn.commit()

    # Ensure the portfolios table exists and has the required columns
    c.execute('''
    CREATE TABLE IF NOT EXISTS portfolios (
        username TEXT,
        ticker TEXT,
        shares REAL,
        initial_investment REAL,
        PRIMARY KEY (username, ticker),
        FOREIGN KEY (username) REFERENCES users (username)
    )
    ''')

    # Check if the initial_investment column exists, if not, add it
    c.execute("PRAGMA table_info(portfolios)")
    columns = [column[1] for column in c.fetchall()]
    if 'initial_investment' not in columns:
        c.execute(f"ALTER TABLE portfolios ADD COLUMN initial_investment REAL")
        conn.commit()

    conn.close()

# Function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Function to set the background image
def set_background_image(image_path):
    if Path(image_path).exists():
        try:
            with open(image_path, "rb") as img_file:
                encoded_img = base64.b64encode(img_file.read()).decode('utf-8')
                st.markdown(
                    f"""
                    <style>
                    .stApp {{
                        position: relative;
                        background-image: url(data:image/png;base64,{encoded_img});
                        background-size: cover;
                        background-position: center;
                        background-repeat: no-repeat;
                    }}
                    .stApp::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        background-color: rgba(255, 255, 255, 0.8); /* White overlay with 0.8 opacity */
                        z-index: 0;
                    }}
                    .main-title, .sub-title, .metric-box, .blue-background {{
                        position: relative;
                        z-index: 1;
                    }}
                    </style>
                    """,
                    unsafe_allow_html=True
                )
        except Exception as e:
            st.error(f"Error loading image: {str(e)}")
    else:
        st.error('Image not found. Please check the file name and path.')

# Function to fetch the current price of stocks or currencies
def get_stock_data(ticker, period='1d'):
    try:
        stock = Ticker(ticker)
        df = stock.history(period=period)
        if not df.empty:
            df.reset_index(inplace=True)
            return df
        else:
            return None
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        return None

# Function to convert currency
def convert_currency(amount, from_currency, to_currency):
    if from_currency == to_currency:
        return amount
    try:
        response = requests.get(f'https://api.exchangerate-api.com/v4/latest/{from_currency}')
        rates = response.json()['rates']
        conversion_rate = rates.get(to_currency, 1)
        return amount * conversion_rate
    except Exception as e:
        print(f"Error converting currency: {str(e)}")
        return amount

# Function to get market status
def get_market_status():
    market_status = {}
    for ticker in STOCK_LIST:
        df = get_stock_data(ticker, period='1d')
        if df is not None:
            open_price = df['Open'].iloc[0]
            current_price = df['Close'].iloc[-1]
            change = (current_price - open_price) / open_price * 100
            market_status[ticker] = change
    return market_status

# Function to fetch and plot historical data for holdings
def plot_holdings(holdings, time_range):
    fig = px.line(title=f"Holdings - {time_range}")
    for ticker in holdings:
        df = get_stock_data(ticker, period=TIME_RANGES[time_range])
        if df is not None and not df.empty:
            initial_investment = holdings[ticker]['initial_investment']
            fig.add_scatter(x=df['Date'], y=df['Close'], mode='lines', name=f"{ticker} (Invested: ${initial_investment:.2f})")
    st.plotly_chart(fig, use_container_width=True)

# Function to display the market overview ticker
def market_overview_ticker(market_status):
    ticker_text = ''.join([
        f"<span style='color: {'green' if change > 0 else 'red'};'>{ticker}: {change:.2f}%</span> | "
        for ticker, change in market_status.items()
    ])
    st.markdown(f"""
    <style>
    .ticker {{
        overflow: hidden;
        white-space: nowrap;
        width: 100%;
        background-color: black;
        color: white;
        padding: 5px;
        font-size: 14px;
    }}
    .ticker span {{
        display: inline-block;
        animation: ticker 20s linear infinite;
    }}
    @keyframes ticker {{
        0% {{ transform: translateX(100%); }}
        100% {{ transform: translateX(-100%); }}
    }}
    </style>
    <div class="ticker">
        <span>{ticker_text}</span>
    </div>
    """, unsafe_allow_html=True)

# Function to fetch currency values
def get_currency_values():
    currencies = ['EUR', 'GBP', 'JPY', 'AUD']
    currency_data = {}
    for currency in currencies:
        rate = convert_currency(1, 'USD', currency)
        currency_data[currency] = rate
    return currency_data

# Function to fetch gold price from yfinance
def get_gold_price():
    gold_ticker = Ticker("GC=F")
    df = gold_ticker.history(period="1d")
    if not df.empty:
        return df['Close'].iloc[-1]
    else:
        st.error("Failed to fetch the gold price.")
        return None

# Function to display currency and gold values
def display_currency_and_gold():
    st.markdown('<div class="sub-title">Currency and Gold Values</div>', unsafe_allow_html=True)
    currency_data = get_currency_values()
    gold_price = get_gold_price()
    for currency, value in currency_data.items():
        st.markdown(f'<div class="metric-box">{currency}/USD: {value:.2f}</div>', unsafe_allow_html=True)
    if gold_price:
        st.markdown(f'<div class="metric-box">Gold/USD: ${gold_price:.2f}</div>', unsafe_allow_html=True)

# Function to display the user's financial overview
def display_financial_overview(username, conn):
    st.subheader("Your Financial Overview")
    total_value, invested_value, initial_balance = calculate_total_value(username, conn)
    st.markdown(f'<div class="metric-box">Total Value (Including Investments): ${total_value:.2f}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-box">Invested Value: ${invested_value:.2f}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-box">Initial Investment: ${initial_balance:.2f}</div>', unsafe_allow_html=True)

# Reintroducing get_user_data with initial_investment
def get_user_data(username, conn):
    c = conn.cursor()
    c.execute("SELECT balance, currency, initial_balance FROM users WHERE username = ?", (username,))
    balance, currency, initial_balance = c.fetchone()

    c.execute("SELECT ticker, shares, initial_investment FROM portfolios WHERE username = ?", (username,))
    portfolio_data = c.fetchall()
    portfolio = {ticker: {"shares": shares, "initial_investment": initial_investment} for ticker, shares, initial_investment in portfolio_data}

    return balance, currency, initial_balance, portfolio

# Function to calculate total value with comparison to initial investment
def calculate_total_value(username, conn):
    balance, currency, initial_balance, portfolio = get_user_data(username, conn)
    total_value = balance
    invested_value = 0
    for ticker, data in portfolio.items():
        if data['shares'] > 0:
            stock_data = get_stock_data(ticker, '1d')
            if stock_data is not None:
                last_close = stock_data['Close'].iloc[-1]
                invested_value += last_close * data['shares']
    total_value += invested_value
    total_value = convert_currency(total_value, 'USD', currency)
    invested_value = convert_currency(invested_value, 'USD', currency)
    initial_balance_converted = convert_currency(initial_balance, 'USD', currency)
    return total_value, invested_value, initial_balance_converted

# Function to buy stock
def buy_stock(username, ticker, amount, conn, currency):
    current_price = get_stock_data(ticker, period='1d')
    
    if current_price is None or current_price.empty:
        return "Invalid ticker symbol."
    
    total_cost = current_price['Close'].iloc[-1] * amount
    
    c = conn.cursor()
    c.execute("SELECT balance, currency FROM users WHERE username = ?", (username,))
    user_balance, user_currency = c.fetchone()
    
    total_cost_in_user_currency = convert_currency(total_cost, 'USD', user_currency)
    
    if user_balance < total_cost_in_user_currency:
        return "Insufficient funds."
    
    new_balance = user_balance - total_cost_in_user_currency
    c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, username))
    
    c.execute("SELECT shares FROM portfolios WHERE username = ? AND ticker = ?", (username, ticker))
    existing_shares = c.fetchone()
    
    if existing_shares:
        new_shares = existing_shares[0] + amount
        c.execute("UPDATE portfolios SET shares = ?, initial_investment = initial_investment + ? WHERE username = ? AND ticker = ?", (new_shares, total_cost, username, ticker))
    else:
        c.execute("INSERT INTO portfolios (username, ticker, shares, initial_investment) VALUES (?, ?, ?, ?)", (username, ticker, amount, total_cost))
    
    c.execute("INSERT INTO transactions (username, action, ticker, amount, price) VALUES (?, ?, ?, ?, ?)", 
              (username, 'Buy', ticker, amount, current_price['Close'].iloc[-1]))
    
    conn.commit()
    return f"Successfully bought {amount} shares of {ticker} for ${total_cost_in_user_currency:.2f} {user_currency}"

# Function to sell stock
def sell_stock(username, ticker, amount, conn, currency):
    current_price = get_stock_data(ticker, period='1d')
    
    if current_price is None or current_price.empty:
        return "Invalid ticker symbol."
    
    total_value = current_price['Close'].iloc[-1] * amount
    
    c = conn.cursor()
    c.execute("SELECT shares FROM portfolios WHERE username = ? AND ticker = ?", (username, ticker))
    existing_shares = c.fetchone()
    
    if not existing_shares or existing_shares[0] < amount:
        return "Insufficient shares to sell."
    
    new_shares = existing_shares[0] - amount
    if new_shares == 0:
        c.execute("DELETE FROM portfolios WHERE username = ? AND ticker = ?", (username, ticker))
    else:
        c.execute("UPDATE portfolios SET shares = ? WHERE username = ? AND ticker = ?", (new_shares, username, ticker))
    
    c.execute("SELECT balance, currency FROM users WHERE username = ?", (username,))
    user_balance, user_currency = c.fetchone()
    total_value_in_user_currency = convert_currency(total_value, 'USD', user_currency)
    new_balance = user_balance + total_value_in_user_currency
    c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, username))
    
    c.execute("INSERT INTO transactions (username, action, ticker, amount, price) VALUES (?, ?, ?, ?, ?)", 
              (username, 'Sell', ticker, amount, current_price['Close'].iloc[-1]))
    
    conn.commit()
    return f"Successfully sold {amount} shares of {ticker} for ${total_value_in_user_currency:.2f} {user_currency}"

# Main function with enhanced layout and features
def main():
    ensure_database_schema()
    initialize_music()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = None

    st.markdown('<div class="main-title" style="background-color: blue; color: white; padding: 10px;">Charging Bull Trader</div>', unsafe_allow_html=True)

    if not st.session_state.logged_in:
        st.markdown('<div class="sub-title">Login</div>', unsafe_allow_html=True)
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        if st.button("Login"):
            conn = setup_database()
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (username_input, hash_password(password_input)))
            if c.fetchone():
                st.session_state.logged_in = True
                st.session_state.username = username_input
            else:
                st.error("Invalid username or password")

        if st.button("Create Account"):
            conn = setup_database()
            c = conn.cursor()
            try:
                c.execute("INSERT INTO users (username, password, balance, initial_balance, currency) VALUES (?, ?, ?, ?, ?)",
                          (username_input, hash_password(password_input), INITIAL_BALANCE, INITIAL_BALANCE, DEFAULT_CURRENCY))
                for ticker in STOCK_LIST:
                    c.execute("INSERT INTO portfolios (username, ticker, shares, initial_investment) VALUES (?, ?, 0, 0)", (username_input, ticker))
                conn.commit()
                st.success("Account created successfully!")
            except sqlite3.IntegrityError:
                st.error("Username already exists.")
    else:
        username = st.session_state.username
        conn = setup_database()
        st.sidebar.write(f"Welcome, {username}!")
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None

        # Add the small Charging Bull image under the Logout button
        st.sidebar.image("trade.png", width=150)

        display_financial_overview(username, conn)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<div class="sub-title">Personal Holdings and Stocks</div>', unsafe_allow_html=True)
            time_range = st.selectbox("Select Time Range for Holdings", list(TIME_RANGES.keys()))
            _, _, _, portfolio = get_user_data(username, conn)
            if portfolio:
                plot_holdings(portfolio, time_range)
            else:
                st.write("No stocks in your portfolio.")

            st.markdown('<div class="sub-title">Buy/Sell Stocks</div>', unsafe_allow_html=True)
            action = st.selectbox("Choose Action", ["Buy", "Sell"])
            ticker = st.text_input("Ticker")
            amount = st.number_input("Amount", min_value=1, step=1)
            selected_currency = st.selectbox("Currency", CURRENCIES)
            
            if st.button(f"{action} Stocks"):
                if action == "Buy":
                    result = buy_stock(username, ticker, amount, conn, selected_currency)
                else:
                    result = sell_stock(username, ticker, amount, conn, selected_currency)
                st.write(result)

        with col2:
            market_status = get_market_status()
            market_overview_ticker(market_status)
            display_currency_and_gold()

        st.markdown('<div class="sub-title">Stock Lookup</div>', unsafe_allow_html=True)
        stock_ticker = st.text_input("Enter Stock Ticker for Lookup")
        time_range_lookup = st.selectbox("Select Time Range", list(TIME_RANGES.keys()), key="lookup")
        if st.button("Lookup"):
            df = get_stock_data(stock_ticker, period=TIME_RANGES[time_range_lookup])
            if df is not None and not df.empty:
                fig = px.line(df, x='Date', y='Close', title=f"{stock_ticker} - {time_range_lookup}")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("No data available for this ticker.")

        st.markdown('<div class="sub-title">Stock Market News</div>', unsafe_allow_html=True)
        news_ticker = st.text_input("Enter Stock Ticker for News")
        news_api_key = st.text_input("Enter NewsAPI Key")
        if st.button("Get News"):
            if news_api_key:
                newsapi = NewsApiClient(api_key=news_api_key)
                articles = newsapi.get_everything(q=news_ticker, language='en', sort_by='publishedAt', page_size=5)
                if articles:
                    for article in articles['articles']:
                        st.subheader(article['title'])
                        st.write(article['description'])
                        st.write(f"[Read more]({article['url']})")
                else:
                    st.write("No news available for this ticker.")
            else:
                st.write("Please enter a valid NewsAPI key.")

if __name__ == "__main__":
    main()
