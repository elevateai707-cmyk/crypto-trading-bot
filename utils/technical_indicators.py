"""
Technical indicator calculations for the regime-switching trading bot.

Provides standalone, tested functions for:
- ADX (Average Directional Index) — trend strength
- EMA (Exponential Moving Average) — trend direction
- RSI (Relative Strength Index) — momentum / overbought-oversold
- Bollinger Bands — volatility / mean-reversion levels

All functions expect pandas DataFrames with 'close', 'high', 'low' columns.
"""

import pandas as pd
import pandas_ta as ta
from typing import Optional


def add_adx(
    df: pd.DataFrame, length: int = 14
) -> pd.DataFrame:
    """Add ADX, +DI, -DI columns to the DataFrame.

    ADX > 25 = trending market.
    ADX < 20 = sideways / ranging market.
    ADX 20-25 = transitional zone.
    """
    adx_result = ta.adx(df["high"], df["low"], df["close"], length=length)
    if adx_result is not None:
        df["adx"] = adx_result.iloc[:, 0]
        df["plus_di"] = adx_result.iloc[:, 1]
        df["minus_di"] = adx_result.iloc[:, 2]
    return df


def add_ema(df: pd.DataFrame, length: int = 9) -> pd.DataFrame:
    """Add an EMA column of the specified length."""
    df[f"ema_{length}"] = ta.ema(df["close"], length=length)
    return df


def add_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Add an RSI column."""
    df["rsi"] = ta.rsi(df["close"], length=length)
    return df


def add_bollinger_bands(
    df: pd.DataFrame, length: int = 20, std: int = 2
) -> pd.DataFrame:
    """Add Bollinger Bands columns (upper, middle SMA, lower)."""
    bb = ta.bbands(df["close"], length=length, std=std)
    if bb is not None:
        df["bb_upper"] = bb.iloc[:, 0]
        df["bb_middle"] = bb.iloc[:, 1]
        df["bb_lower"] = bb.iloc[:, 2]
    return df


def detect_regime(df: pd.DataFrame) -> tuple[str, str]:
    """Determine market regime based on ADX and EMA 200 position.

    Returns:
        (regime: str, rationale: str)
        regime is one of: 'UP_TREND', 'DOWN_TREND', 'SIDEWAYS', 'TRANSITIONAL'
    """
    latest = df.iloc[-1]
    adx = latest.get("adx", 0)
    price = latest["close"]
    ema_200 = latest.get("ema_200", price)  # fallback if no 200 EMA

    if pd.isna(adx) or adx == 0:
        return ("SIDEWAYS", "Insufficient ADX data — defaulting to neutral.")

    if adx > 25:
        if price > ema_200:
            return (
                "UP_TREND",
                f"ADX {adx:.1f} > 25 (strong trend), price {price:.2f} > "
                f"EMA 200 {ema_200:.2f} → Bullish trending market.",
            )
        else:
            return (
                "DOWN_TREND",
                f"ADX {adx:.1f} > 25 (strong trend), price {price:.2f} < "
                f"EMA 200 {ema_200:.2f} → Bearish trending market.",
            )
    elif adx < 20:
        return (
            "SIDEWAYS",
            f"ADX {adx:.1f} < 20 → Ranging / sideways market. "
            "Holding cash recommended.",
        )
    else:
        return (
            "TRANSITIONAL",
            f"ADX {adx:.1f} in 20-25 transitional zone. "
            "No new entries — maintain existing positions.",
        )


def check_up_market_signal(df: pd.DataFrame) -> tuple[bool, str]:
    """Check the momentum trend-following entry/exit rules for an Up Market.

    Entry: 9 EMA crosses above 21 EMA AND RSI > 50 (but < 70).
    Exit:  9 EMA crosses below 21 EMA OR RSI > 75.

    Returns:
        (signal: bool, action: str)
        signal = True means action is recommended.
        action is one of: 'BUY', 'EXIT_LONG', 'HOLD', 'INSUFFICIENT_DATA'
    """
    if len(df) < 22:
        return (False, "INSUFFICIENT_DATA")

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    ema_9_now = latest.get("ema_9", 0)
    ema_21_now = latest.get("ema_21", 0)
    ema_9_prev = prev.get("ema_9", 0)
    ema_21_prev = prev.get("ema_21", 0)
    rsi_now = latest.get("rsi", 50)

    if any(pd.isna(x) for x in [ema_9_now, ema_21_now, rsi_now]):
        return (False, "INSUFFICIENT_DATA")

    # Entry: 9 EMA crosses above 21 EMA + RSI in 50-70 range
    if ema_9_prev <= ema_21_prev and ema_9_now > ema_21_now:
        if 50 < rsi_now < 70:
            return (
                True,
                f"BUY — 9 EMA ({ema_9_now:.2f}) crossed above 21 EMA "
                f"({ema_21_now:.2f}), RSI {rsi_now:.1f} in bullish range.",
            )
        else:
            return (
                False,
                f"HOLD — EMA crossover detected but RSI {rsi_now:.1f} "
                f"outside 50-70 entry window.",
            )

    # Exit: 9 EMA crosses below 21 EMA OR RSI > 75
    if ema_9_prev >= ema_21_prev and ema_9_now < ema_21_now:
        return (
            True,
            f"EXIT_LONG — 9 EMA ({ema_9_now:.2f}) crossed below 21 EMA "
            f"({ema_21_now:.2f}). Trend weakening.",
        )
    if rsi_now > 75:
        return (
            True,
            f"EXIT_LONG — RSI {rsi_now:.1f} > 75, taking profit on overbought.",
        )

    return (False, "HOLD — No signal.")


def check_down_market_signal(df: pd.DataFrame) -> tuple[bool, str]:
    """Check the mean-reversion rules for a Down Market.

    Entry: Price touches/breaks lower Bollinger Band AND RSI < 30.
    Exit:  Price returns to middle Bollinger Band (20 SMA) OR RSI > 45.

    Returns:
        (signal: bool, action: str)
    """
    if len(df) < 21:
        return (False, "INSUFFICIENT_DATA")

    latest = df.iloc[-1]
    price = latest["close"]
    bb_lower = latest.get("bb_lower", 0)
    bb_middle = latest.get("bb_middle", 0)
    rsi_now = latest.get("rsi", 50)

    if any(pd.isna(x) for x in [bb_lower, bb_middle, rsi_now]):
        return (False, "INSUFFICIENT_DATA")

    # Entry: price at or below lower BB + RSI oversold
    if price <= bb_lower and rsi_now < 30:
        return (
            True,
            f"BUY_DIP — Price {price:.2f} at lower Bollinger Band "
            f"({bb_lower:.2f}), RSI {rsi_now:.1f} < 30 oversold. "
            "Anticipating mean-reversion bounce.",
        )

    # Exit: price back to middle band or RSI neutralized
    if price >= bb_middle:
        return (
            True,
            f"EXIT_SHORT — Price {price:.2f} returned to middle BB "
            f"({bb_middle:.2f}). Mean-reversion target reached.",
        )
    if rsi_now > 45:
        return (
            True,
            f"EXIT_SHORT — RSI {rsi_now:.1f} > 45, bounce played out.",
        )

    return (False, "HOLD — No mean-reversion signal.")


def calculate_all_indicators(df: pd.DataFrame, is_up_market: bool = True) -> pd.DataFrame:
    """Convenience: add all indicators needed by either strategy.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns.
        is_up_market: If True, includes EMA 9/21 for momentum strategy.
                       If False, includes Bollinger Bands for mean-reversion.

    Returns:
        DataFrame with all requested indicator columns added.
    """
    df = add_adx(df, length=14)
    df = add_rsi(df, length=14)
    df = add_ema(df, length=200)  # always needed for regime detection

    if is_up_market:
        df = add_ema(df, length=9)
        df = add_ema(df, length=21)
    else:
        df = add_bollinger_bands(df, length=20, std=2)

    return df