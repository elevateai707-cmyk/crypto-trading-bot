"""
Dashboard layout definitions — Dash Bootstrap Components with dark theme.

5 Tabs:
1. Overview — KPI cards, portfolio value chart, PnL curve, open positions
2. Agent Activity — scrolling decision feed + gauge scores
3. Trade History — sortable data table
4. Technical Analysis — candlestick chart with overlays
5. Logs & Settings — terminal log viewer + bot configuration
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from config import TRADING_PAIR


# ─── Color Constants ────────────────────────────────────────────────────────

DARK_BG = "#1a1d23"
DARKER_BG = "#14171c"
CARD_BG = "#22262b"
HEADER_BG = "#0d0f12"
TEXT_PRIMARY = "#e0e0e0"
TEXT_SECONDARY = "#8a8f95"
GREEN = "#00c853"
RED = "#ff1744"
YELLOW = "#ffd600"
BLUE = "#2979ff"
ORANGE = "#ff9100"
PURPLE = "#7c4dff"
TEAL = "#00bfa5"


# ─── Theme ──────────────────────────────────────────────────────────────────

def dark_figure_layout() -> dict:
    """Return a base layout dict for dark-themed Plotly figures."""
    return {
        "paper_bgcolor": DARKER_BG,
        "plot_bgcolor": DARKER_BG,
        "font": {"color": TEXT_PRIMARY, "family": "Inter, sans-serif"},
        "xaxis": {
            "gridcolor": "#2a2d33",
            "showgrid": True,
            "zerolinecolor": "#333",
        },
        "yaxis": {
            "gridcolor": "#2a2d33",
            "showgrid": True,
            "zerolinecolor": "#333",
        },
        "margin": {"l": 50, "r": 20, "t": 30, "b": 40},
        "legend": {"font": {"color": TEXT_PRIMARY}},
        "hovermode": "x unified",
    }


# ─── Navbar / Header ────────────────────────────────────────────────────────

header = dbc.Navbar(
    dbc.Container(
        [
            # Left: Title + Status
            dbc.Row(
                [
                    dbc.Col(
                        html.H3(
                            "🤖 Quantum Trading Terminal",
                            className="fw-bold mb-0",
                            style={"color": TEXT_PRIMARY},
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Badge(
                            "● RUNNING",
                            id="bot-status-badge",
                            color="success",
                            className="ms-2",
                            style={"fontSize": "0.8rem"},
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Badge(
                            "PAPER TRADING",
                            id="paper-badge",
                            color="warning",
                            className="ms-1",
                            style={"fontSize": "0.8rem"},
                        ),
                        width="auto",
                    ),
                ],
                align="center",
            ),
            # Center: Portfolio value + PnL
            dbc.Row(
                [
                    dbc.Col(
                        html.Span(
                            [
                                html.Small("Portfolio: ", style={"color": TEXT_SECONDARY}),
                                html.Strong("$10,000.00", id="portfolio-value", style={"color": TEXT_PRIMARY}),
                            ],
                            className="me-3",
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        html.Span(
                            [
                                html.Small("PnL: ", style={"color": TEXT_SECONDARY}),
                                html.Strong("+$0.00", id="pnl-display", style={"color": GREEN}),
                            ],
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        html.Span(
                            [
                                html.Small("Regime: ", style={"color": TEXT_SECONDARY}),
                                html.Strong("UNKNOWN", id="regime-display", style={"color": YELLOW}),
                            ],
                        ),
                        width="auto",
                    ),
                ],
                align="center",
            ),
            # Right: Control buttons
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "▶ Start",
                            id="btn-start",
                            color="success",
                            size="sm",
                            className="me-1",
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Button(
                            "⏸ Pause",
                            id="btn-pause",
                            color="warning",
                            size="sm",
                            className="me-1",
                            disabled=True,
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Button(
                            "⏹ Stop",
                            id="btn-stop",
                            color="danger",
                            size="sm",
                            disabled=True,
                        ),
                        width="auto",
                    ),
                ],
                align="center",
            ),
        ],
        fluid=True,
        className="d-flex justify-content-between align-items-center",
    ),
    color=HEADER_BG,
    dark=True,
    sticky="top",
    className="shadow-sm",
)


# ─── Tab 1: Overview ────────────────────────────────────────────────────────

kpi_cards = dbc.Row(
    [
        dbc.Col(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Small("Total Trades", style={"color": TEXT_SECONDARY}),
                        html.H3("0", id="kpi-total-trades", className="mb-0 fw-bold"),
                    ]
                ),
                color=DARK_BG,
                className="border-0 shadow-sm",
                style={"backgroundColor": CARD_BG},
            ),
            width=3,
        ),
        dbc.Col(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Small("Win Rate", style={"color": TEXT_SECONDARY}),
                        html.H3("--", id="kpi-win-rate", className="mb-0 fw-bold"),
                    ]
                ),
                color=DARK_BG,
                className="border-0 shadow-sm",
                style={"backgroundColor": CARD_BG},
            ),
            width=3,
        ),
        dbc.Col(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Small("Current Regime", style={"color": TEXT_SECONDARY}),
                        html.H3("--", id="kpi-regime", className="mb-0 fw-bold"),
                    ]
                ),
                color=DARK_BG,
                className="border-0 shadow-sm",
                style={"backgroundColor": CARD_BG},
            ),
            width=3,
        ),
        dbc.Col(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Small("Active Agents", style={"color": TEXT_SECONDARY}),
                        html.H3("0/4", id="kpi-active-agents", className="mb-0 fw-bold"),
                    ]
                ),
                color=DARK_BG,
                className="border-0 shadow-sm",
                style={"backgroundColor": CARD_BG},
            ),
            width=3,
        ),
    ],
    className="mb-4",
)

portfolio_chart = dcc.Graph(
    id="portfolio-chart",
    figure={
        "data": [
            go.Scatter(
                x=[], y=[],
                mode="lines",
                name="Portfolio Value",
                line={"color": BLUE, "width": 2},
                fill="tozeroy",
                fillcolor=f"rgba(41, 121, 255, 0.1)",
            )
        ],
        "layout": {
            **dark_figure_layout(),
            "title": {"text": "Portfolio Value Over Time", "font": {"size": 14}},
            "yaxis": {"ticksuffix": "$"},
        },
    },
    config={"displayModeBar": False},
)

pnl_chart = dcc.Graph(
    id="pnl-chart",
    figure={
        "data": [
            go.Scatter(
                x=[], y=[],
                mode="lines",
                name="PnL",
                line={"color": GREEN, "width": 2},
                fill="tozeroy",
                fillcolor="rgba(0, 200, 83, 0.1)",
            )
        ],
        "layout": {
            **dark_figure_layout(),
            "title": {"text": "Profit & Loss Curve", "font": {"size": 14}},
            "yaxis": {"ticksuffix": "$"},
        },
    },
    config={"displayModeBar": False},
)

open_positions_table = dbc.Table(
    id="positions-table",
    bordered=False,
    hover=True,
    striped=False,
    dark=True,
    size="sm",
    style={"fontSize": "0.85rem"},
)

tab1_overview = dbc.Container(
    [
        html.H5("Dashboard Overview", className="mb-3", style={"color": TEXT_PRIMARY}),
        kpi_cards,
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(portfolio_chart),
                        className="border-0 shadow-sm",
                        style={"backgroundColor": CARD_BG},
                    ),
                    width=6,
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(pnl_chart),
                        className="border-0 shadow-sm",
                        style={"backgroundColor": CARD_BG},
                    ),
                    width=6,
                ),
            ],
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H6(
                                    "Open Positions",
                                    style={"color": TEXT_PRIMARY, "marginBottom": "10px"},
                                ),
                                open_positions_table,
                            ]
                        ),
                        className="border-0 shadow-sm",
                        style={"backgroundColor": CARD_BG},
                    ),
                    width=12,
                ),
            ]
        ),
    ],
    fluid=True,
    className="p-3",
)


# ─── Tab 2: Agent Activity ──────────────────────────────────────────────────

agent_feed = html.Div(
    id="agent-feed",
    style={
        "maxHeight": "600px",
        "overflowY": "auto",
        "backgroundColor": DARKER_BG,
        "padding": "10px",
        "borderRadius": "8px",
        "fontSize": "0.8rem",
        "fontFamily": "monospace",
    },
    children=[html.Div("Waiting for agent activity...", style={"color": TEXT_SECONDARY})],
)

gauge_charts = html.Div(
    [
        dbc.Card(
            dbc.CardBody(
                [
                    html.H6("Social Sentiment", className="text-center", style={"color": TEXT_SECONDARY}),
                    dcc.Graph(
                        id="gauge-sentiment",
                        figure=create_gauge_figure("Sentiment", 0.0, GREEN, RED),
                        config={"displayModeBar": False},
                    ),
                ]
            ),
            className="border-0 shadow-sm mb-3",
            style={"backgroundColor": CARD_BG},
        ),
        dbc.Card(
            dbc.CardBody(
                [
                    html.H6("Macro / Geopolitical", className="text-center", style={"color": TEXT_SECONDARY}),
                    dcc.Graph(
                        id="gauge-macro",
                        figure=create_gauge_figure("Macro", 0.0, TEAL, RED),
                        config={"displayModeBar": False},
                    ),
                ]
            ),
            className="border-0 shadow-sm mb-3",
            style={"backgroundColor": CARD_BG},
        ),
        dbc.Card(
            dbc.CardBody(
                [
                    html.H6("Crypto Industry", className="text-center", style={"color": TEXT_SECONDARY}),
                    dcc.Graph(
                        id="gauge-industry",
                        figure=create_gauge_figure("Industry", 0.0, PURPLE, RED),
                        config={"displayModeBar": False},
                    ),
                ]
            ),
            className="border-0 shadow-sm",
            style={"backgroundColor": CARD_BG},
        ),
    ]
)

tab2_activity = dbc.Container(
    [
        html.H5("Agent Activity", className="mb-3", style={"color": TEXT_PRIMARY}),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H6("Live Agent Feed", style={"color": TEXT_PRIMARY, "marginBottom": "10px"}),
                                agent_feed,
                            ]
                        ),
                        className="border-0 shadow-sm",
                        style={"backgroundColor": CARD_BG},
                    ),
                    width=8,
                ),
                dbc.Col(gauge_charts, width=4),
            ]
        ),
    ],
    fluid=True,
    className="p-3",
)


# ─── Tab 3: Trade History ───────────────────────────────────────────────────

tab3_trades = dbc.Container(
    [
        html.H5("Trade History", className="mb-3", style={"color": TEXT_PRIMARY}),
        dbc.Card(
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Input(
                                    id="trade-search",
                                    placeholder="🔍 Search trades...",
                                    type="text",
                                    className="mb-3",
                                    style={"backgroundColor": DARKER_BG, "color": TEXT_PRIMARY, "border": "1px solid #333"},
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                dbc.RadioItems(
                                    id="trade-filter",
                                    inline=True,
                                    options=[
                                        {"label": "All", "value": "all"},
                                        {"label": "Executed", "value": "EXECUTED"},
                                        {"label": "Simulated", "value": "SIMULATED"},
                                        {"label": "Aborted", "value": "ABORTED"},
                                    ],
                                    value="all",
                                    style={"color": TEXT_PRIMARY},
                                ),
                                width=8,
                            ),
                        ]
                    ),
                    html.Div(id="trade-table-container"),
                ]
            ),
            className="border-0 shadow-sm",
            style={"backgroundColor": CARD_BG},
        ),
    ],
    fluid=True,
    className="p-3",
)


# ─── Tab 4: Technical Analysis ──────────────────────────────────────────────

candlestick_chart = dcc.Graph(
    id="candlestick-chart",
    figure={
        "data": [],
        "layout": {
            **dark_figure_layout(),
            "title": {"text": f"{TRADING_PAIR} — Candlestick + Indicators", "font": {"size": 14}},
            "xaxis": {"rangeslider": {"visible": False}},
            "yaxis": {"ticksuffix": "$"},
            "dragmode": "zoom",
        },
    },
    config={"displayModeBar": False},
)

rsi_chart = dcc.Graph(
    id="rsi-chart",
    figure={
        "data": [],
        "layout": {
            **dark_figure_layout(),
            "title": {"text": "RSI (14)", "font": {"size": 12}},
            "yaxis": {"range": [0, 100]},
            "height": 150,
        },
    },
    config={"displayModeBar": False},
)

adx_chart = dcc.Graph(
    id="adx-chart",
    figure={
        "data": [],
        "layout": {
            **dark_figure_layout(),
            "title": {"text": "ADX (14)", "font": {"size": 12}},
            "height": 150,
        },
    },
    config={"displayModeBar": False},
)

tab4_technical = dbc.Container(
    [
        html.H5("Technical Analysis", className="mb-3", style={"color": TEXT_PRIMARY}),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.Select(
                                                id="ta-pair-select",
                                                options=[
                                                    {"label": "BTC-USD", "value": "BTC-USD"},
                                                    {"label": "ETH-USD", "value": "ETH-USD"},
                                                    {"label": "SOL-USD", "value": "SOL-USD"},
                                                ],
                                                value=TRADING_PAIR,
                                                style={"backgroundColor": DARKER_BG, "color": TEXT_PRIMARY, "border": "1px solid #333"},
                                            ),
                                            width=3,
                                        ),
                                        dbc.Col(
                                            dbc.Select(
                                                id="ta-granularity",
                                                options=[
                                                    {"label": "5 min", "value": "FIVE_MINUTE"},
                                                    {"label": "15 min", "value": "FIFTEEN_MINUTE"},
                                                    {"label": "1 hour", "value": "ONE_HOUR"},
                                                ],
                                                value="FIVE_MINUTE",
                                                style={"backgroundColor": DARKER_BG, "color": TEXT_PRIMARY, "border": "1px solid #333"},
                                            ),
                                            width=2,
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                                candlestick_chart,
                                dbc.Row(
                                    [
                                        dbc.Col(rsi_chart, width=6),
                                        dbc.Col(adx_chart, width=6),
                                    ]
                                ),
                            ]
                        ),
                        className="border-0 shadow-sm",
                        style={"backgroundColor": CARD_BG},
                    ),
                    width=12,
                ),
            ]
        ),
    ],
    fluid=True,
    className="p-3",
)


# ─── Tab 5: Logs & Settings ─────────────────────────────────────────────────

log_viewer = html.Div(
    id="log-viewer",
    style={
        "maxHeight": "400px",
        "overflowY": "auto",
        "backgroundColor": "#0a0c0f",
        "padding": "10px",
        "borderRadius": "8px",
        "fontSize": "0.75rem",
        "fontFamily": "'Cascadia Code', 'Fira Code', monospace",
        "color": "#a0a8b0",
        "whiteSpace": "pre-wrap",
    },
    children=[html.Div("// Bot initialized. Waiting for logs...")],
)

settings_panel = dbc.Card(
    dbc.CardBody(
        [
            html.H6("Bot Settings", style={"color": TEXT_PRIMARY, "marginBottom": "15px"}),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Trading Pair", style={"color": TEXT_SECONDARY, "fontSize": "0.85rem"}),
                            dbc.Select(
                                id="settings-pair",
                                options=[
                                    {"label": "BTC-USD", "value": "BTC-USD"},
                                    {"label": "ETH-USD", "value": "ETH-USD"},
                                    {"label": "SOL-USD", "value": "SOL-USD"},
                                ],
                                value=TRADING_PAIR,
                                style={"backgroundColor": DARKER_BG, "color": TEXT_PRIMARY, "border": "1px solid #333"},
                            ),
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            html.Label("Loop Interval (min)", style={"color": TEXT_SECONDARY, "fontSize": "0.85rem"}),
                            dbc.Input(
                                id="settings-interval",
                                type="number",
                                value=5,
                                min=1,
                                max=60,
                                style={"backgroundColor": DARKER_BG, "color": TEXT_PRIMARY, "border": "1px solid #333"},
                            ),
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            html.Label("Risk per Trade (%)", style={"color": TEXT_SECONDARY, "fontSize": "0.85rem"}),
                            dbc.Input(
                                id="settings-risk",
                                type="number",
                                value=2.0,
                                min=0.5,
                                max=10.0,
                                step=0.5,
                                style={"backgroundColor": DARKER_BG, "color": TEXT_PRIMARY, "border": "1px solid #333"},
                            ),
                        ],
                        width=4,
                    ),
                ],
                className="mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Label("Order Size (USD)", style={"color": TEXT_SECONDARY, "fontSize": "0.85rem"}),
                            dbc.Input(
                                id="settings-order-size",
                                type="number",
                                value=50.0,
                                min=10,
                                step=10,
                                style={"backgroundColor": DARKER_BG, "color": TEXT_PRIMARY, "border": "1px solid #333"},
                            ),
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            html.Label("Paper Trading", style={"color": TEXT_SECONDARY, "fontSize": "0.85rem"}),
                            dbc.Switch(
                                id="settings-paper-trading",
                                label="Simulate trades (no real money)",
                                value=True,
                                style={"color": TEXT_PRIMARY},
                            ),
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            html.Label("", style={"color": TEXT_SECONDARY}),
                            dbc.Button(
                                "Apply Settings",
                                id="btn-apply-settings",
                                color="primary",
                                className="mt-2",
                                style={"width": "100%"},
                            ),
                        ],
                        width=4,
                    ),
                ],
            ),
        ]
    ),
    className="border-0 shadow-sm",
    style={"backgroundColor": CARD_BG},
)

tab5_logs = dbc.Container(
    [
        html.H5("Logs & Settings", className="mb-3", style={"color": TEXT_PRIMARY}),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H6("Bot Logs", style={"color": TEXT_PRIMARY, "marginBottom": "10px"}),
                                log_viewer,
                            ]
                        ),
                        className="border-0 shadow-sm",
                        style={"backgroundColor": CARD_BG},
                    ),
                    width=7,
                ),
                dbc.Col(settings_panel, width=5),
            ]
        ),
    ],
    fluid=True,
    className="p-3",
)


# ─── Main Layout ────────────────────────────────────────────────────────────

tabs = dbc.Tabs(
    [
        dbc.Tab(tab1_overview, label="📊 Overview", tab_id="tab-overview"),
        dbc.Tab(tab2_activity, label="🤖 Agent Activity", tab_id="tab-activity"),
        dbc.Tab(tab3_trades, label="📝 Trade History", tab_id="tab-trades"),
        dbc.Tab(tab4_technical, label="📈 Technical Analysis", tab_id="tab-technical"),
        dbc.Tab(tab5_logs, label="⚙️ Logs & Settings", tab_id="tab-logs"),
    ],
    id="main-tabs",
    active_tab="tab-overview",
    className="mb-0",
    style={"backgroundColor": DARK_BG, "color": TEXT_PRIMARY},
)


def create_layout():
    """Return the full dashboard layout."""
    return html.Div(
        [
            dcc.Store(id="bot-state", data={"running": False, "paused": False}),
            dcc.Interval(
                id="dashboard-interval",
                interval=5000,  # 5 seconds
                n_intervals=0,
            ),
            dcc.Interval(
                id="candlestick-interval",
                interval=30000,  # 30 seconds
                n_intervals=0,
            ),
            header,
            html.Div(
                tabs,
                style={"backgroundColor": DARK_BG, "minHeight": "calc(100vh - 60px)"},
            ),
        ],
        style={"backgroundColor": DARK_BG},
    )


def create_gauge_figure(title: str, value: float, pos_color: str, neg_color: str) -> dict:
    """Create a gauge chart for qualitative scores (-1.0 to 1.0)."""
    # Map -1..1 to 0..1 for the gauge
    gauge_val = (value + 1) / 2

    # Determine color based on value
    if value > 0.3:
        color = pos_color
    elif value < -0.3:
        color = neg_color
    else:
        color = YELLOW

    return {
        "data": [
            go.Indicator(
                mode="gauge+number",
                value=gauge_val * 100,
                number={
                    "suffix": "%",
                    "font": {"color": color, "size": 28},
                    "valueformat": ".0f",
                },
                gauge={
                    "axis": {
                        "range": [0, 100],
                        "tickvals": [0, 25, 50, 75, 100],
                        "ticktext": ["-1.0", "-0.5", "0", "0.5", "1.0"],
                        "tickfont": {"color": TEXT_SECONDARY, "size": 10},
                    },
                    "bar": {"color": color, "thickness": 0.4},
                    "bgcolor": DARKER_BG,
                    "borderwidth": 0,
                    "steps": [
                        {"range": [0, 30], "color": f"rgba(255, 23, 68, 0.15)"},
                        {"range": [30, 70], "color": f"rgba(255, 214, 0, 0.1)"},
                        {"range": [70, 100], "color": f"rgba(0, 200, 83, 0.15)"},
                    ],
                    "threshold": {
                        "line": {"color": color, "width": 4},
                        "thickness": 0.75,
                        "value": gauge_val * 100,
                    },
                },
                domain={"x": [0, 1], "y": [0, 1]},
            )
        ],
        "layout": {
            "paper_bgcolor": CARD_BG,
            "font": {"color": TEXT_PRIMARY},
            "height": 180,
            "margin": {"l": 20, "r": 20, "t": 10, "b": 10},
        },
    }