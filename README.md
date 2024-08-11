
# Charging Bull Trader

## Overview

Welcome to **Charging Bull Trader**, a trading simulation game where you start with a balance of $10,000 and engage in buying and selling stocks. The game also allows you to seek news about stocks and tracks your performance over time.

## Features

- **Trade Stocks:** Buy and sell stocks from a predefined list.
- **Track Performance:** View your current cash balance, portfolio, and overall financial status.
- **Stock News:** Get the latest news about specific stocks.
- **Portfolio Performance:** Analyze the historical performance of stocks in your portfolio.
- **Database Tracking:** Each player's activity is recorded in a SQLite database, tracking transactions and performance.

## Getting Started

### Prerequisites

Ensure you have Python 3.8 or higher installed on your system. You'll also need to install the required Python packages, which can be done using the `requirements.txt` file.

### Installation

1. Clone this repository to your local machine:
   ```sh
   git clone https://github.com/anttiluode/chargingbulltrader.git
   cd chargingbulltrader
   ```

2. Create a virtual environment (optional but recommended):

   Use what ever software like anaconda or do not use virtual environment. 

3. Install the required packages:
   ```sh
   pip install -r requirements.txt
   ```

4. Place your image (`trade.png`) in the project directory.

5. Obtain a NewsAPI key: (Works without it but if you want to use the news feature)
   - Visit [NewsAPI](https://newsapi.org/) to sign up and get your API key.
   - Insert your API key into the `NEWS_API_KEY` variable in the `app.py` file:
     ```python
     NEWS_API_KEY = 'your_newsapi_key_here'
     ```

6. Run the Streamlit app:
   ```sh
   streamlit run app.py
   ```

## Usage

1. **Create an Account:** Use the sidebar to create an account with a username and password.
2. **Login:** Once registered, log in using your credentials.
3. **Trade Stocks:** Buy and sell stocks through the trading interface.
4. **Check Performance:** View your current balance, portfolio, and transaction history.
5. **Explore News:** Get the latest news for stocks of interest.
6. **Analyze Portfolio:** View and analyze the historical performance of stocks in your portfolio.

## Credits

- **Author:** Created by Antti Luode with assistance from ChatGPT.
- **Image:** Generated by Flux.1 AI.
- **Music:** Composed by Udio.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For any questions or issues, please contact [your email address].

---

Enjoy trading and tracking your stock performance with **Charging Bull Trader**!
