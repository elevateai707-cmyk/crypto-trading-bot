"""
Macro & Geopolitical Agent — Global Macro Economist.

Monitors breaking geopolitical news, Fed/inflation data, stock market
movements, and assesses their impact on risk-on assets like crypto.
"""

import json
import logging

from litellm import completion

from config import NOUS_API_BASE, NOUS_API_KEY, FAST_MODEL

logger = logging.getLogger(__name__)


MACRO_SYSTEM_PROMPT = """You are a Global Macro Economist for a crypto trading desk.
Your job is to analyze macroeconomic and geopolitical events that impact
risk-on assets like Bitcoin and crypto markets.

Analyze the provided search results for:
1. Central bank decisions (Fed rates, ECB, BOJ)
2. Inflation data (CPI, PPI, PCE)
3. Geopolitical events (wars, sanctions, trade disputes)
4. Stock market movements (S&P 500, Nasdaq)
5. Dollar strength (DXY index)
6. Bond yields (10-year Treasury)

Return your analysis as a JSON object with exactly these fields:
{
    "macro_score": <float between -1.0 and 1.0>,
    "label": <"HIGHLY_BEARISH" | "BEARISH" | "NEUTRAL" | "BULLISH" | "HIGHLY_BULLISH">,
    "rationale": "<2-3 sentence explanation>",
    "key_factors": ["<factor 1>", "<factor 2>", "<factor 3>"]
}

- -1.0 = Highly Bearish (war, rate hikes, recession)
- -0.5 = Bearish (tightening, geopolitical tension)
- 0.0 = Neutral (mixed macro signals)
- 0.5 = Bullish (rate cuts, strong economy)
- 1.0 = Highly Bullish (accommodative policy, risk-on)

Base your analysis strictly on the provided search results."""


class MacroAgent:
    """Analyzes macro-economic and geopolitical conditions."""

    def __init__(self, tavily_tool=None):
        self.tavily_tool = tavily_tool
        self.name = "Macro & Geopolitical Agent"

    def analyze(self) -> dict:
        """Run macro analysis and return a scored report.

        Returns:
            dict with: agent_name, decision, score, rationale, raw_output
        """
        logger.info(f"{self.name}: Scanning global macro landscape...")

        search_results = ""
        if self.tavily_tool:
            try:
                queries = [
                    "Federal Reserve interest rate decision inflation 2026",
                    "geopolitical risk impact crypto markets today",
                    "stock market S&P 500 macro outlook",
                    "US dollar DXY index crypto impact",
                ]
                for q in queries:
                    result = self.tavily_tool.run(query=q, max_results=3)
                    if result:
                        search_results += f"\n--- Search: {q} ---\n{result}\n"
            except Exception as e:
                logger.warning(f"Tavily search error: {e}")
                search_results = (
                    f"No real-time macro data (error: {e}). "
                    "Provide a neutral baseline."
                )
        else:
            search_results = (
                "No search tool available. Provide neutral baseline macro analysis."
            )

        try:
            response = completion(
                model=f"openai/{FAST_MODEL}",
                api_key=NOUS_API_KEY,
                api_base=NOUS_API_BASE,
                messages=[
                    {"role": "system", "content": MACRO_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Search Results:\n{search_results}\n\n"
                            "Analyze the macro environment and return your JSON analysis."
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            raw_output = response.choices[0].message.content
            result = json.loads(raw_output)

            return {
                "agent_name": self.name,
                "decision": f"Macro: {result.get('label', 'NEUTRAL')}",
                "score": result.get("macro_score", 0.0),
                "rationale": result.get("rationale", ""),
                "raw_output": raw_output,
                "key_factors": result.get("key_factors", []),
            }

        except Exception as e:
            logger.error(f"{self.name}: Analysis failed: {e}")
            return {
                "agent_name": self.name,
                "decision": "ERROR",
                "score": 0.0,
                "rationale": f"Analysis failed: {str(e)}",
                "raw_output": "",
                "key_factors": [],
            }