"""
Coinbase Advanced Trade API client wrapper.

Handles:
- Market data fetching (candles, product info)
- Order placement (market orders, limit orders)
- Account balance retrieval
- Paper trading simulation mode

Uses the official `coinbase-advanced-py` SDK.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from coinbase.rest import RESTClient

from config import (
    COINBASE_API_KEY,
    COINBASE_API_SECRET,
    PAPER_TRADING,
    ORDER_SIZE_USD,
)

logger = logging.getLogger(__name__)


class CoinbaseClient:
    """Wrapper around the Coinbase Advanced Trade REST API."""

    def __init__(self):
        self._client: Optional[RESTClient] = None
        self._paper_trading = PAPER_TRADING

    @property
    def client(self) -> RESTClient:
        """Lazy-initialize the REST client."""
        if self._client is None:
            if not COINBASE_API_KEY or not COINBASE_API_SECRET:
                logger.warning(
                    "Coinbase API keys not configured. "
                    "Paper trading mode will simulate prices."
                )
                self._client = None
            else:
                self._client = RESTClient(
                    api_key=COINBASE_API_KEY,
                    api_secret=COINBASE_API_SECRET,
                )
        return self._client

    def is_paper_trading(self) -> bool:
        """Return whether we're in paper trading mode."""
        return self._paper_trading

    def set_paper_trading(self, value: bool):
        """Toggle paper trading mode at runtime."""
        self._paper_trading = value
        logger.info(f"Paper trading mode set to: {value}")

    # ─── Market Data ────────────────────────────────────────────────────────

    def get_candles(
        self,
        product_id: str = "BTC-USD",
        granularity: str = "FIVE_MINUTE",
        limit: int = 200,
    ) -> pd.DataFrame:
        """Fetch historical candle data and return a pandas DataFrame.

        Granularity options: ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE,
        THIRTY_MINUTE, ONE_HOUR, SIX_HOUR, ONE_DAY
        """
        if self._paper_trading and self.client is None:
            # Generate simulated price data when no API keys are configured
            return self._simulate_candles(product_id, limit)

        try:
            response = self.client.get_candles(
                product_id=product_id,
                granularity=granularity,
                limit=limit,
            )
            candles = response.get("candles", [])
            if not candles:
                logger.warning(f"No candle data returned for {product_id}")
                return self._simulate_candles(product_id, limit)

            df = pd.DataFrame(candles)
            df["timestamp"] = pd.to_datetime(df["start"], unit="s")
            df = df.rename(
                columns={
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                }
            )
            # Convert string prices to float
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df

        except Exception as e:
            logger.error(f"Error fetching candles for {product_id}: {e}")
            return self._simulate_candles(product_id, limit)

    def _simulate_candles(
        self, product_id: str, limit: int
    ) -> pd.DataFrame:
        """Generate simulated candle data for paper trading.

        Uses a random walk starting from a realistic BTC price.
        """
        import random

        # Approximate BTC price as of mid-2026
        base_price = 75000.0
        np.random.seed(int(time.time()) % 10000)

        # Generate random walk with drift
        returns = np.random.randn(limit) * 0.002  # 0.2% volatility per 5min
        prices = [base_price]
        for r in returns:
            prices.append(prices[-1] * (1 + r))
        prices = prices[1:]  # trim initial

        now = datetime.now(timezone.utc)
        timestamps = [
            int((now.timestamp() - (limit - i) * 300)) for i in range(limit)
        ]

        candles = []
        for i in range(limit):
            close = prices[i]
            high = close * (1 + abs(np.random.randn() * 0.008))
            low = close * (1 - abs(np.random.randn() * 0.008))
            open_ = prices[i - 1] if i > 0 else close * 0.999
            volume = np.random.uniform(100, 500)

            candles.append(
                {
                    "start": timestamps[i],
                    "open": str(open_),
                    "high": str(high),
                    "low": str(low),
                    "close": str(close),
                    "volume": str(volume),
                }
            )

        df = pd.DataFrame(candles)
        df["timestamp"] = pd.to_datetime(df["start"], unit="s")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    def get_product_book(self, product_id: str = "BTC-USD") -> dict:
        """Get the current order book for a product."""
        if self._paper_trading and self.client is None:
            return {"price": "75000.00", "best_bid": "74980.00", "best_ask": "75020.00"}
        try:
            return self.client.get_product_book(product_id=product_id)
        except Exception as e:
            logger.error(f"Error fetching product book: {e}")
            return {}

    # ─── Account ────────────────────────────────────────────────────────────

    def get_accounts(self) -> list[dict]:
        """Get all accounts with non-zero balances."""
        if self._paper_trading and self.client is None:
            return [
                {
                    "currency": "BTC",
                    "balance": "0.01",
                    "value_usd": 750.0,
                },
                {
                    "currency": "USDC",
                    "balance": "5000.00",
                    "value_usd": 5000.0,
                },
            ]
        try:
            response = self.client.get_accounts()
            return response.get("accounts", [])
        except Exception as e:
            logger.error(f"Error fetching accounts: {e}")
            return []

    def get_portfolio_value(self) -> dict:
        """Calculate total portfolio value in USD.

        Returns dict with total_value, cash, crypto_value, btc_balance, usdc_balance.
        """
        accounts = self.get_accounts()
        total_crypto = 0.0
        total_cash = 0.0
        btc_balance = 0.0
        usdc_balance = 0.0

        for acct in accounts:
            currency = acct.get("currency", "")
            balance = float(acct.get("balance", 0))
            if balance <= 0:
                continue

            if currency == "USDC":
                total_cash += balance
                usdc_balance = balance
            elif currency == "USD":
                total_cash += balance
            elif currency == "BTC":
                btc_balance = balance
                try:
                    price = self.get_current_price("BTC-USD")
                    total_crypto += balance * price
                except Exception:
                    total_crypto += balance * 75000  # fallback

        total_value = total_cash + total_crypto
        return {
            "total_value": total_value,
            "cash": total_cash,
            "crypto_value": total_crypto,
            "btc_balance": btc_balance,
            "usdc_balance": usdc_balance,
        }

    def get_current_price(self, product_id: str = "BTC-USD") -> float:
        """Get the current market price for a product."""
        if self._paper_trading and self.client is None:
            # Use the latest simulated close
            df = self._simulate_candles(product_id, 1)
            return float(df.iloc[-1]["close"])

        try:
            book = self.get_product_book(product_id)
            # Use midpoint of best bid/ask
            best_bid = float(book.get("best_bid", 0))
            best_ask = float(book.get("best_ask", 0))
            if best_bid > 0 and best_ask > 0:
                return (best_bid + best_ask) / 2
            return float(book.get("price", 75000))
        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return 75000.0

    # ─── Orders ─────────────────────────────────────────────────────────────

    def place_market_buy(
        self, product_id: str = "BTC-USD", amount_usd: Optional[float] = None
    ) -> dict:
        """Place a market buy order for the specified USD amount.

        In paper trading mode, simulates the order and returns a mock result.
        """
        amount = amount_usd or ORDER_SIZE_USD
        current_price = self.get_current_price(product_id)
        btc_amount = amount / current_price

        logger.info(
            f"{'[PAPER]' if self._paper_trading else '[LIVE]'} "
            f"Market BUY {product_id}: ${amount:.2f} @ ~${current_price:.2f} "
            f"({btc_amount:.6f} BTC)"
        )

        if self._paper_trading:
            return {
                "success": True,
                "order_id": f"paper_buy_{int(time.time())}",
                "product_id": product_id,
                "side": "BUY",
                "size": str(btc_amount),
                "price": str(current_price),
                "status": "EXECUTED",
                "paper_trading": True,
            }

        try:
            order = self.client.market_order_buy(
                client_order_id=f"bot_buy_{int(time.time() * 1000)}",
                product_id=product_id,
                quote_size=str(amount),
            )
            return order
        except Exception as e:
            logger.error(f"Market buy failed: {e}")
            return {"success": False, "error": str(e), "status": "FAILED"}

    def place_market_sell(
        self,
        product_id: str = "BTC-USD",
        amount_btc: Optional[float] = None,
    ) -> dict:
        """Place a market sell order for the specified BTC amount.

        In paper trading mode, simulates the order.
        """
        amount = amount_btc or 0.001  # default small amount
        current_price = self.get_current_price(product_id)
        usd_value = amount * current_price

        logger.info(
            f"{'[PAPER]' if self._paper_trading else '[LIVE]'} "
            f"Market SELL {product_id}: {amount:.6f} BTC @ ~${current_price:.2f} "
            f"(${usd_value:.2f})"
        )

        if self._paper_trading:
            return {
                "success": True,
                "order_id": f"paper_sell_{int(time.time())}",
                "product_id": product_id,
                "side": "SELL",
                "size": str(amount),
                "price": str(current_price),
                "status": "EXECUTED",
                "paper_trading": True,
            }

        try:
            order = self.client.market_order_sell(
                client_order_id=f"bot_sell_{int(time.time() * 1000)}",
                product_id=product_id,
                base_size=str(amount),
            )
            return order
        except Exception as e:
            logger.error(f"Market sell failed: {e}")
            return {"success": False, "error": str(e), "status": "FAILED"}

    def place_limit_buy(
        self,
        product_id: str,
        amount_btc: float,
        limit_price: float,
    ) -> dict:
        """Place a limit buy order at the specified price."""
        logger.info(
            f"{'[PAPER]' if self._paper_trading else '[LIVE]'} "
            f"Limit BUY {product_id}: {amount_btc:.6f} BTC @ ${limit_price:.2f}"
        )

        if self._paper_trading:
            return {
                "success": True,
                "order_id": f"paper_limit_buy_{int(time.time())}",
                "product_id": product_id,
                "side": "BUY",
                "size": str(amount_btc),
                "price": str(limit_price),
                "status": "EXECUTED",
                "paper_trading": True,
            }

        try:
            order = self.client.limit_order_gtc_buy(
                client_order_id=f"bot_limit_buy_{int(time.time() * 1000)}",
                product_id=product_id,
                base_size=str(amount_btc),
                limit_price=str(limit_price),
            )
            return order
        except Exception as e:
            logger.error(f"Limit buy failed: {e}")
            return {"success": False, "error": str(e), "status": "FAILED"}


