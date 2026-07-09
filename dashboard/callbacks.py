"""
Dashboard callbacks — real-time polling, chart updates, bot control.

Uses dcc.Interval to poll the SQLite database every 5 seconds and
update all dashboard components without page refresh.
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, no_update, html, dcc, callback_context

from config import TRADING_PAIR
from database.db_manager import DatabaseManager
from dashboard.layouts import dark_figure_layout, GREEN, RED, YELLOW, BLUE, PURPLE, ORANGE, TEAL, TEXT_PRIMARY, TEXT_SECONDARY

logger = logging.getLogger(__name__)

# Store references set from main.py
_db: Optional[DatabaseManager] = None
_bot_thread: Optional[threading.Thread] = None
_bot_engine: Optional[object] = None
_bot_running = False
_bot_paused = False


def set_db(db: DatabaseManager):
    """Inject the database manager reference (called from main.py)."""
    global _db
    _db = db


def set_bot_thread(thread: threading.Thread):
    """Inject the bot thread reference."""
    global _bot_thread
    _bot_thread = thread


def set_bot_engine(engine):
    """Inject the bot engine reference for control callbacks."""
    global _bot_engine
    _bot_engine = engine


def set_bot_state(running: bool, paused: bool = False):
    """Update the bot state flags."""
    global _bot_running, _bot_paused
    _bot_running = running
    _bot_paused = paused


# ─── Helper Functions ───────────────────────────────────────────────────────

def get_color_for_score(score: float) -> str:
    """Return a color based on score value (-1 to 1)."""
    if score > 0.3:
        return GREEN
    elif score < -0.3:
        return RED
    return YELLOW


def get_agent_color(agent_name: str) -> str:
    """Return a consistent color for each agent."""
    colors = {
        "Social Sentiment Agent": ORANGE,
        "Macro & Geopolitical Agent": TEAL,
        "Crypto Industry & Platform Agent": PURPLE,
        "Master Quant Execution Agent": BLUE,
    }
    return colors.get(agent_name, TEXT_SECONDARY)


# ─── Register Callbacks ─────────────────────────────────────────────────────

def register_callbacks(app):
    """Register all dashboard callbacks."""

    # ── Tab 1: Overview — KPI cards ──
    @app.callback(
        [
            Output("kpi-total-trades", "children"),
            Output("kpi-win-rate", "children"),
            Output("kpi-regime", "children"),
            Output("kpi-active-agents", "children"),
            Output("portfolio-value", "children"),
            Output("pnl-display", "children"),
            Output("pnl-display", "style"),
            Output("regime-display", "children"),
            Output("regime-display", "style"),
            Output("bot-status-badge", "children"),
            Output("bot-status-badge", "color"),
            Output("portfolio-chart", "figure"),
            Output("pnl-chart", "figure"),
            Output("positions-table", "children"),
        ],
        Input("dashboard-interval", "n_intervals"),
    )
    def update_overview(n):
        if not _db:
            return (no_update,) * 14

        # KPI Cards
        trade_stats = _db.get_trade_stats()
        total_trades = trade_stats.get("total_trades", 0)
        total_buys = trade_stats.get("buys", 0)
        total_sells = trade_stats.get("sells", 0)
        win_rate = "--"

        # Simple win rate: sells that were executed (proxy until we have proper PnL tracking on sells)
        if total_sells > 0:
            # This is a proxy — real win rate needs PnL tracking per trade
            win_rate = f"{total_sells}/{total_buys}"

        # Regime
        status = _db.get_latest_status()
        regime = status.get("current_regime", "UNKNOWN") if status else "UNKNOWN"
        regime_color = GREEN if regime == "UP_TREND" else (RED if regime == "DOWN_TREND" else YELLOW)
        kpi_regime = regime.replace("_", " ").title() if regime != "UNKNOWN" else "--"

        # Active agents
        recent = _db.get_recent_decisions(limit=50)
        active_agents = len(set(d.get("agent_name") for d in recent if d.get("agent_name")))
        kpi_agents = f"{active_agents}/4"

        # Bot status
        bot_status_text = status.get("status", "STOPPED") if status else "STOPPED"
        badge_text = f"● {bot_status_text}"
        badge_color = (
            "success" if bot_status_text == "RUNNING"
            else "warning" if bot_status_text == "PAUSED"
            else "danger" if bot_status_text == "ERROR"
            else "secondary"
        )

        # Portfolio value
        latest_portfolio = _db.get_latest_portfolio()
        if latest_portfolio:
            portfolio_val = f"${latest_portfolio.get('total_value_usd', 0):,.2f}"
        else:
            portfolio_val = "$10,000.00"

        # PnL
        latest_pnl = _db.get_latest_pnl()
        if latest_pnl:
            total_pnl = latest_pnl.get("total_pnl", 0)
            pnl_text = f"{'+' if total_pnl >= 0 else ''}${total_pnl:,.2f}"
            pnl_color = GREEN if total_pnl >= 0 else RED
        else:
            pnl_text = "+$0.00"
            pnl_color = GREEN

        # Portfolio chart
        portfolio_history = _db.get_portfolio_history(limit=200)
        portfolio_fig = {
            "data": [
                go.Scatter(
                    x=[d.get("timestamp") for d in portfolio_history],
                    y=[d.get("total_value_usd", 0) for d in portfolio_history],
                    mode="lines",
                    name="Portfolio",
                    line={"color": BLUE, "width": 2},
                    fill="tozeroy",
                    fillcolor="rgba(41, 121, 255, 0.1)",
                )
            ],
            "layout": {
                **dark_figure_layout(),
                "title": {"text": "Portfolio Value Over Time", "font": {"size": 14}},
                "yaxis": {"ticksuffix": "$"},
            },
        }

        # PnL chart
        pnl_history = _db.get_pnl_history(limit=200)
        pnl_values = [d.get("total_pnl", 0) for d in pnl_history]
        pnl_fig = {
            "data": [
                go.Scatter(
                    x=[d.get("timestamp") for d in pnl_history],
                    y=pnl_values,
                    mode="lines",
                    name="PnL",
                    line={"color": GREEN if pnl_values and pnl_values[-1] >= 0 else RED, "width": 2},
                    fill="tozeroy",
                    fillcolor=f"rgba(0, 200, 83, 0.1)" if (pnl_values and pnl_values[-1] >= 0) else "rgba(255, 23, 68, 0.1)",
                )
            ],
            "layout": {
                **dark_figure_layout(),
                "title": {"text": "Profit & Loss Curve", "font": {"size": 14}},
                "yaxis": {"ticksuffix": "$"},
            },
        }

        # Positions table
        open_positions = [
            d for d in recent
            if d.get("agent_name") == "Master Quant Execution Agent"
            and "BUY" in d.get("decision", "")
        ]
        if open_positions:
            last = open_positions[0]
            rows = html.Table(
                [
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Pair", style={"color": TEXT_SECONDARY}),
                                html.Th("Side", style={"color": TEXT_SECONDARY}),
                                html.Th("Amount", style={"color": TEXT_SECONDARY}),
                                html.Th("Entry Price", style={"color": TEXT_SECONDARY}),
                                html.Th("Status", style={"color": TEXT_SECONDARY}),
                            ]
                        )
                    ),
                    html.Tbody(
                        [
                            html.Tr(
                                [
                                    html.Td(TRADING_PAIR, style={"color": TEXT_PRIMARY}),
                                    html.Td("BUY", style={"color": GREEN}),
                                    html.Td(f"${50:.2f}"),  # placeholder
                                    html.Td(f"${10000:.2f}"),  # placeholder
                                    html.Td("Open", style={"color": YELLOW}),
                                ]
                            )
                        ]
                    ),
                ],
                bordered=False,
                hover=True,
                dark=True,
                size="sm",
                style={"fontSize": "0.85rem"},
            )
        else:
            rows = html.Div(
                "No open positions. Bot is flat.",
                style={"color": TEXT_SECONDARY, "padding": "20px", "textAlign": "center"},
            )

        return (
            str(total_trades),
            str(win_rate),
            kpi_regime,
            kpi_agents,
            portfolio_val,
            pnl_text,
            {"color": pnl_color},
            regime.replace("_", " ").title() if regime != "UNKNOWN" else "UNKNOWN",
            {"color": regime_color},
            badge_text,
            badge_color,
            portfolio_fig,
            pnl_fig,
            rows,
        )

    # ── Tab 2: Agent Activity ──
    @app.callback(
        [
            Output("agent-feed", "children"),
            Output("gauge-sentiment", "figure"),
            Output("gauge-macro", "figure"),
            Output("gauge-industry", "figure"),
        ],
        Input("dashboard-interval", "n_intervals"),
    )
    def update_agent_activity(n):
        if not _db:
            return (no_update,) * 4

        decisions = _db.get_recent_decisions(limit=50)

        # Agent feed
        feed_items = []
        for d in decisions:
            agent_color = get_agent_color(d.get("agent_name", ""))
            score = d.get("score")
            score_str = f" [{score:+.2f}]" if score is not None else ""
            ts = d.get("timestamp", "")[11:19] if d.get("timestamp") else ""  # HH:MM:SS

            feed_items.append(
                html.Div(
                    [
                        html.Span(f"[{ts}] ", style={"color": TEXT_SECONDARY}),
                        html.Span(
                            f"{d.get('agent_name', 'Unknown')} ",
                            style={"color": agent_color, "fontWeight": "bold"},
                        ),
                        html.Span(
                            f"→ {d.get('decision', '')}{score_str}",
                            style={"color": TEXT_PRIMARY},
                        ),
                        html.Br(),
                        html.Span(
                            f"  {d.get('rationale', '')[:200]}",
                            style={"color": TEXT_SECONDARY, "fontSize": "0.7rem"},
                        ),
                    ],
                    style={"marginBottom": "8px", "borderLeft": f"3px solid {agent_color}", "paddingLeft": "8px"},
                )
            )

        if not feed_items:
            feed_items = [html.Div("Waiting for agent activity...", style={"color": TEXT_SECONDARY})]

        # Gauge scores from latest decisions per agent
        sentiment_score = 0.0
        macro_score = 0.0
        industry_score = 0.0

        for d in decisions:
            name = d.get("agent_name", "")
            score = d.get("score") or 0.0
            if "Sentiment" in name:
                sentiment_score = score
            elif "Macro" in name:
                macro_score = score
            elif "Industry" in name or "Crypto" in name:
                industry_score = score

        from dashboard.layouts import create_gauge_figure

        return (
            feed_items,
            create_gauge_figure("Sentiment", sentiment_score, GREEN, RED),
            create_gauge_figure("Macro", macro_score, TEAL, RED),
            create_gauge_figure("Industry", industry_score, PURPLE, RED),
        )

    # ── Tab 3: Trade History ──
    @app.callback(
        Output("trade-table-container", "children"),
        [Input("dashboard-interval", "n_intervals"), Input("trade-filter", "value")],
    )
    def update_trade_table(n, filter_val):
        if not _db:
            return no_update

        trades = _db.get_trades(limit=200)

        if filter_val != "all":
            trades = [t for t in trades if t.get("status") == filter_val]

        if not trades:
            return html.Div(
                "No trades recorded yet.",
                style={"color": TEXT_SECONDARY, "padding": "20px", "textAlign": "center"},
            )

        table = dbc.Table(
            [
                html.Thead(
                    html.Tr(
                        [
                            html.Th("Time", style={"color": TEXT_SECONDARY, "fontSize": "0.8rem"}),
                            html.Th("Pair", style={"color": TEXT_SECONDARY, "fontSize": "0.8rem"}),
                            html.Th("Side", style={"color": TEXT_SECONDARY, "fontSize": "0.8rem"}),
                            html.Th("Amount", style={"color": TEXT_SECONDARY, "fontSize": "0.8rem"}),
                            html.Th("Price", style={"color": TEXT_SECONDARY, "fontSize": "0.8rem"}),
                            html.Th("Status", style={"color": TEXT_SECONDARY, "fontSize": "0.8rem"}),
                            html.Th("Mode", style={"color": TEXT_SECONDARY, "fontSize": "0.8rem"}),
                        ]
                    )
                ),
                html.Tbody(
                    [
                        html.Tr(
                            [
                                html.Td(t.get("timestamp", "")[11:19], style={"color": TEXT_PRIMARY, "fontSize": "0.8rem"}),
                                html.Td(t.get("pair", ""), style={"color": TEXT_PRIMARY, "fontSize": "0.8rem"}),
                                html.Td(
                                    t.get("side", ""),
                                    style={
                                        "color": GREEN if t.get("side") == "BUY" else RED,
                                        "fontWeight": "bold",
                                        "fontSize": "0.8rem",
                                    },
                                ),
                                html.Td(
                                    f"{t.get('amount', 0):.6f}" if t.get("amount") else "--",
                                    style={"color": TEXT_PRIMARY, "fontSize": "0.8rem"},
                                ),
                                html.Td(
                                    f"${t.get('price', 0):.2f}" if t.get("price") else "--",
                                    style={"color": TEXT_PRIMARY, "fontSize": "0.8rem"},
                                ),
                                html.Td(
                                    t.get("status", ""),
                                    style={
                                        "color": GREEN if t.get("status") == "EXECUTED" else (YELLOW if t.get("status") == "SIMULATED" else RED),
                                        "fontSize": "0.8rem",
                                    },
                                ),
                                html.Td(
                                    "PAPER" if t.get("paper_trading") else "LIVE",
                                    style={"color": TEXT_SECONDARY, "fontSize": "0.8rem"},
                                ),
                            ]
                        )
                        for t in trades
                    ]
                ),
            ],
            bordered=False,
            hover=True,
            dark=True,
            size="sm",
        )

        return table

    # ── Tab 4: Technical Analysis ──
    @app.callback(
        [
            Output("candlestick-chart", "figure"),
            Output("rsi-chart", "figure"),
            Output("adx-chart", "figure"),
        ],
        [Input("candlestick-interval", "n_intervals"), Input("ta-pair-select", "value")],
    )
    def update_technical_charts(n, pair):
        if not _db:
            return (no_update,) * 3

        # We need the master quant agent's coinbase client reference
        # For now, generate a placeholder chart with simulated data
        from utils.coinbase_client import CoinbaseClient
        client = CoinbaseClient()
        df = client.get_candles(product_id=pair, granularity="FIVE_MINUTE", limit=200)

        if df.empty:
            return (no_update,) * 3

        # Calculate indicators
        from utils.technical_indicators import add_ema, add_bollinger_bands, add_rsi, add_adx
        df = add_ema(df, 9)
        df = add_ema(df, 21)
        df = add_bollinger_bands(df)
        df = add_rsi(df)
        df = add_adx(df)

        # Candlestick chart
        candlestick_fig = {
            "data": [
                go.Candlestick(
                    x=df["timestamp"],
                    open=df["open"],
                    high=df["high"],
                    low=df["low"],
                    close=df["close"],
                    name="Price",
                    increasing_line_color=GREEN,
                    decreasing_line_color=RED,
                ),
                go.Scatter(
                    x=df["timestamp"],
                    y=df.get("ema_9", [None] * len(df)),
                    mode="lines",
                    name="EMA 9",
                    line={"color": BLUE, "width": 1.5},
                ),
                go.Scatter(
                    x=df["timestamp"],
                    y=df.get("ema_21", [None] * len(df)),
                    mode="lines",
                    name="EMA 21",
                    line={"color": ORANGE, "width": 1.5},
                ),
                go.Scatter(
                    x=df["timestamp"],
                    y=df.get("bb_upper", [None] * len(df)),
                    mode="lines",
                    name="BB Upper",
                    line={"color": "rgba(255,255,255,0.3)", "width": 1, "dash": "dash"},
                ),
                go.Scatter(
                    x=df["timestamp"],
                    y=df.get("bb_lower", [None] * len(df)),
                    mode="lines",
                    name="BB Lower",
                    line={"color": "rgba(255,255,255,0.3)", "width": 1, "dash": "dash"},
                    fill="tonexty",
                    fillcolor="rgba(255,255,255,0.05)",
                ),
            ],
            "layout": {
                **dark_figure_layout(),
                "title": {"text": f"{pair} — Candlestick + EMA 9/21 + Bollinger Bands", "font": {"size": 14}},
                "xaxis": {"rangeslider": {"visible": False}},
                "yaxis": {"ticksuffix": "$"},
            },
        }

        # RSI chart
        rsi_values = df.get("rsi", [None] * len(df))
        rsi_fig = {
            "data": [
                go.Scatter(
                    x=df["timestamp"],
                    y=rsi_values,
                    mode="lines",
                    name="RSI (14)",
                    line={"color": PURPLE, "width": 1.5},
                ),
                # Overbought/oversold lines
                go.Scatter(
                    x=df["timestamp"],
                    y=[70] * len(df),
                    mode="lines",
                    name="Overbought",
                    line={"color": RED, "width": 1, "dash": "dash"},
                ),
                go.Scatter(
                    x=df["timestamp"],
                    y=[30] * len(df),
                    mode="lines",
                    name="Oversold",
                    line={"color": GREEN, "width": 1, "dash": "dash"},
                ),
            ],
            "layout": {
                **dark_figure_layout(),
                "title": {"text": "RSI (14)", "font": {"size": 12}},
                "yaxis": {"range": [0, 100]},
                "height": 150,
                "showlegend": False,
            },
        }

        # ADX chart
        adx_values = df.get("adx", [None] * len(df))
        adx_fig = {
            "data": [
                go.Scatter(
                    x=df["timestamp"],
                    y=adx_values,
                    mode="lines",
                    name="ADX (14)",
                    line={"color": TEAL, "width": 1.5},
                ),
                # Trend threshold lines
                go.Scatter(
                    x=df["timestamp"],
                    y=[25] * len(df),
                    mode="lines",
                    name="Trending (ADX > 25)",
                    line={"color": YELLOW, "width": 1, "dash": "dash"},
                ),
                go.Scatter(
                    x=df["timestamp"],
                    y=[20] * len(df),
                    mode="lines",
                    name="Sideways (ADX < 20)",
                    line={"color": TEXT_SECONDARY, "width": 1, "dash": "dash"},
                ),
            ],
            "layout": {
                **dark_figure_layout(),
                "title": {"text": "ADX (14)", "font": {"size": 12}},
                "yaxis": {"range": [0, max(adx_values) * 1.2 if any(adx_values) else 50]},
                "height": 150,
                "showlegend": False,
            },
        }

        return candlestick_fig, rsi_fig, adx_fig

    # ── Bot Control Buttons ──
    @app.callback(
        [
            Output("btn-start", "disabled"),
            Output("btn-pause", "disabled"),
            Output("btn-stop", "disabled"),
            Output("bot-state", "data"),
        ],
        [
            Input("btn-start", "n_clicks"),
            Input("btn-pause", "n_clicks"),
            Input("btn-stop", "n_clicks"),
        ],
        [State("bot-state", "data")],
    )
    def control_bot(start_clicks, pause_clicks, stop_clicks, state):
        ctx = callback_context.triggered[0]["prop_id"] if callback_context.triggered else ""
        global _bot_running, _bot_paused

        if "btn-start" in ctx:
            _bot_running = True
            _bot_paused = False
            if _bot_engine and hasattr(_bot_engine, '_paused') and _bot_engine._paused:
                _bot_engine.resume()
            elif _bot_engine and not _bot_engine._running:
                _bot_engine.start()
            return True, False, False, {"running": True, "paused": False}
        elif "btn-pause" in ctx:
            _bot_paused = True
            if _bot_engine:
                _bot_engine.pause()
            return False, True, False, {"running": True, "paused": True}
        elif "btn-stop" in ctx:
            _bot_running = False
            _bot_paused = False
            if _bot_engine:
                _bot_engine.stop()
            return False, True, True, {"running": False, "paused": False}

        # Default state based on current flags
        return (
            _bot_running,
            not _bot_running or _bot_paused,
            not _bot_running,
            {"running": _bot_running, "paused": _bot_paused},
        )

    # ── Settings Apply ──
    @app.callback(
        Output("settings-pair", "value"),
        Input("btn-apply-settings", "n_clicks"),
        [
            State("settings-pair", "value"),
            State("settings-interval", "value"),
            State("settings-risk", "value"),
            State("settings-order-size", "value"),
            State("settings-paper-trading", "value"),
        ],
    )
    def apply_settings(n_clicks, pair, interval, risk, order_size, paper_trading):
        if not n_clicks:
            return no_update

        # Log settings change
        logger.info(
            f"Settings updated: pair={pair}, interval={interval}min, "
            f"risk={risk}%, order=${order_size}, paper={paper_trading}"
        )
        return pair