import streamlit as st
import sqlite3
import hashlib
import time
import threading
import pygame
from yfinance import Ticker
import pandas as pd
import plotly.express as px
import requests
from newsapi import NewsApiClient
import os
from pathlib import Path
import cv2
import numpy as np
import base64

# Constants
INITIAL_BALANCE = 10000
UPDATE_INTERVAL = 60
DEFAULT_CURRENCY = 'USD'
STOCK_LIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "BRK-B", "V", "JPM"]
TIME_RANGES = ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max']
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD"]

# Initialize NewsAPI Client
NEWS_API_KEY = 'your_newsapi_key_here'
newsapi = NewsApiClient(api_key=NEWS_API_KEY)

# Initialize pygame for music
def initialize_music():
    if 'music_initialized' not in st.session_state:
        pygame.mixer.init()
        pygame.mixer.music.load('trade.mp3')
        pygame.mixer.music.play(-1)
        st.session_state['music_initialized'] = True

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
        currency TEXT DEFAULT 'USD'
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS portfolios (
        username TEXT,
        ticker TEXT,
        shares REAL,
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

conn = setup_database()

# Function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Function to fetch the current price of stocks
def get_stock_data(ticker, period='1y'):
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

# Price data dictionary
price_data = {}

# Function to update prices regularly
def update_prices():
    global price_data
    while True:
        for ticker in STOCK_LIST:
            df = get_stock_data(ticker, period='1d')
            if df is not None:
                price_data[ticker] = df['Close'].iloc[-1]
        time.sleep(UPDATE_INTERVAL)

# Start price update thread
price_thread = threading.Thread(target=update_prices, daemon=True)
price_thread.start()

# Initialize music
initialize_music()

def get_user_data(username, conn):
    c = conn.cursor()
    c.execute("SELECT balance, currency FROM users WHERE username = ?", (username,))
    balance, currency = c.fetchone()
    
    c.execute("SELECT ticker, shares FROM portfolios WHERE username = ?", (username,))
    portfolio = dict(c.fetchall())
    
    return balance, currency, portfolio

def calculate_total_value(username, conn):
    balance, currency, portfolio = get_user_data(username, conn)
    total_value = balance
    stock_value = 0
    for ticker, shares in portfolio.items():
        if shares > 0:
            stock_data = get_stock_data(ticker, '1d')
            if stock_data is not None:
                last_close = stock_data['Close'].iloc[-1]
                stock_value += last_close * shares
    total_value += stock_value
    total_value = convert_currency(total_value, 'USD', currency)
    stock_value = convert_currency(stock_value, 'USD', currency)
    cash_value = convert_currency(balance, 'USD', currency)
    return total_value, cash_value, stock_value

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
        c.execute("UPDATE portfolios SET shares = ? WHERE username = ? AND ticker = ?", (new_shares, username, ticker))
    else:
        c.execute("INSERT INTO portfolios (username, ticker, shares) VALUES (?, ?, ?)", (username, ticker, amount))
    
    c.execute("INSERT INTO transactions (username, action, ticker, amount, price) VALUES (?, ?, ?, ?, ?)", 
              (username, 'Buy', ticker, amount, current_price['Close'].iloc[-1]))
    
    conn.commit()
    return f"Successfully bought {amount} shares of {ticker} for ${total_cost_in_user_currency:.2f} {user_currency}"

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

# Function to fetch news for a given stock ticker
def get_stock_news(ticker):
    try:
        all_articles = newsapi.get_everything(q=ticker,
                                              language='en',
                                              sort_by='publishedAt',
                                              page_size=5)
        articles = all_articles['articles']
        return articles
    except Exception as e:
        print(f"Error fetching news: {str(e)}")
        return []

def set_background_image(image_path, alpha=0.5):
    if Path(image_path).exists():
        img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if img is not None:
            if img.shape[2] == 4:
                img[:, :, 3] = (img[:, :, 3] * alpha).astype(img.dtype)
            else:
                alpha_channel = np.ones((img.shape[0], img.shape[1]), dtype=img.dtype) * int(255 * alpha)
                img = cv2.merge((img, alpha_channel))
            is_success, im_buf_arr = cv2.imencode(".png", img)
            if is_success:
                byte_im = im_buf_arr.tobytes()
                encoded_img = base64.b64encode(byte_im).decode('utf-8')
                bg_image = f"data:image/png;base64,{encoded_img}"
                st.markdown(
                    f"""
                    <style>
                    .stApp {{
                        background-image: url({bg_image});
                        background-size: cover;
                    }}
                    </style>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.error('Failed to encode the image.')
        else:
            st.error('Failed to read the image. Please ensure the image is valid.')
    else:
        st.error('Image not found. Please check the file name and path.')

# Initialize session state if not already done
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None

# Use relative path for background image
background_image_path = os.path.join(os.path.dirname(__file__), 'trade.png')

# Set the background image
set_background_image(background_image_path, alpha=0.5)

st.markdown(
    """
    <style>
    .main-content {
        background-color: rgba(255, 255, 255, 0.9);
        padding: 20px;
        border-radius: 10px;
    }
    .split-screen {
        display: flex;
        justify-content: space-between;
    }
    .news-section {
        width: 45%;
    }
    .trading-section {
        width: 45%;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Charging Bull Trader")

# Sidebar for login and account creation
st.sidebar.header("Account Management")

username_input = st.sidebar.text_input("Username")
password_input = st.sidebar.text_input("Password", type="password")

if st.sidebar.button("Create Account"):
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, balance, currency) VALUES (?, ?, ?, ?)", 
                  (username_input, hash_password(password_input), INITIAL_BALANCE, DEFAULT_CURRENCY))
        for ticker in STOCK_LIST:
            c.execute("INSERT INTO portfolios (username, ticker, shares) VALUES (?, ?, 0)", (username_input, ticker))
        conn.commit()
        st.sidebar.success("Account created successfully!")
    except sqlite3.IntegrityError:
        st.sidebar.error("Username already exists.")

if st.sidebar.button("Login"):
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username_input, hash_password(password_input)))
    if c.fetchone():
        st.session_state.logged_in = True
        st.session_state.username = username_input
        st.sidebar.success("Logged in successfully!")
    else:
        st.sidebar.error("Invalid username or password")

if st.session_state.logged_in:
    st.sidebar.write(f"Welcome, {st.session_state.username}!")

    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.sidebar.success("Logged out successfully!")

    username = st.session_state.username

    # Top panel for balance and refresh button
    st.subheader("Your Financial Overview")
    if st.button("Refresh Balance"):
        total_value, cash_value, stock_value = calculate_total_value(username, conn)
        st.metric("Total Value (Including Investments)", f"${total_value:.2f}")
        st.metric("Cash Balance", f"${cash_value:.2f}")
        st.metric("Invested in Stocks", f"${stock_value:.2f}")
    else:
        balance, currency, _ = get_user_data(username, conn)
        st.metric("Current Cash Balance", f"${balance:.2f} {currency}")

    # Split screen layout
    col1, col2 = st.columns(2)

    with col1:
        st.header("Trading Interface")
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
        
        # Display portfolio
        st.header("Your Portfolio")
        _, _, portfolio = get_user_data(username, conn)
        portfolio_df = pd.DataFrame(list(portfolio.items()), columns=["Ticker", "Shares"])
        st.table(portfolio_df)

        # Display transaction history
        st.header("Transaction History")
        c = conn.cursor()
        c.execute('''SELECT action, ticker, amount, price, timestamp FROM transactions WHERE username=? ORDER BY timestamp DESC''', (username,))
        transactions = c.fetchall()
        transaction_df = pd.DataFrame(transactions, columns=["Action", "Ticker", "Amount", "Price", "Timestamp"])
        st.table(transaction_df)
        
        # Plot portfolio performance
        st.header("Portfolio Performance")

        # Display tiny plots of owned stocks in a grid
        if portfolio:
            for ticker in portfolio:
                st.subheader(f"{ticker} Performance")
                df = get_stock_data(ticker, period='1y')
                
                if df is not None and not df.empty:
                    fig = px.line(df, x='Date', y='Close', title=f"{ticker} - 1 Year")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.write("No data available for this ticker.")
        else:
            st.write("No stocks in your portfolio.")

        # Stock chart generation
        st.header("Generate Stock Chart")
        stock_ticker = st.text_input("Enter Stock Ticker")
        time_range = st.selectbox("Select Time Range", TIME_RANGES)

        if st.button("Generate Chart"):
            if stock_ticker:
                df = get_stock_data(stock_ticker, period=time_range)
                if df is not None and not df.empty:
                    fig = px.line(df, x='Date', y='Close', title=f"{stock_ticker} - {time_range}")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.write("No data available for this ticker.")
            else:
                st.write("Please enter a stock ticker.")

    # News Section
    st.header("Stock News")
    news_ticker = st.text_input("Enter Stock Ticker for News")
    if st.button("Get News"):
        if news_ticker:
            articles = get_stock_news(news_ticker)
            if articles:
                for article in articles:
                    st.subheader(article['title'])
                    st.write(article['description'])
                    st.write(f"[Read more]({article['url']})")
            else:
                st.write("No news available for this ticker.")
        else:
            st.write("Please enter a stock ticker.")

else:
    st.write("Please log in to access your trading account.")
