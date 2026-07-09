"""
Dash application entry point.

Initializes the Dash app with dark theming and registers all callbacks.
"""

import logging

import dash
import dash_bootstrap_components as dbc

from dashboard.layouts import create_layout
from dashboard.callbacks import register_callbacks

logger = logging.getLogger(__name__)


def create_dash_app() -> dash.Dash:
    """Create and configure the Dash application."""
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.DARKLY],
        suppress_callback_exceptions=True,
        title="Quantum Trading Terminal",
        update_title=None,
    )

    app.layout = create_layout()

    # Register all callbacks
    register_callbacks(app)

    logger.info("Dash dashboard initialized with dark theme (DARKLY)")
    logger.info("Dashboard will be available at http://localhost:8050")

    return app