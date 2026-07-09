"""
Crypto Industry & Platform Agent — Crypto Tech Lead.

Monitors protocol upgrades, ETF news, hacks, regulatory changes,
and Coinbase Developer Platform (CDP) API updates.
"""

import json
import logging

from litellm import completion

from config import NOUS_API_BASE, NOUS_API_KEY, FAST_MODEL

logger = logging.getLogger(__name__)


CRYPTO_INDUSTRY_SYSTEM_PROMPT = """You are a Crypto Industry & Platform Lead for a crypto trading desk.
Your job is to scan for developments that structurally impact crypto markets.

Analyze the provided search results for:
1. Protocol upgrades (Bitcoin, Ethereum, Layer 2s)
2. ETF flows and approvals (BTC ETF, ETH ETF)
3. Major hacks, exploits, or security incidents
4. Regulatory changes (SEC, MiCA, etc.)
5. Coinbase-specific updates (CDP SDK changes, new features)
6. Major institutional adoption news

Return your analysis as a JSON object with exactly these fields:
{
    "structural_score": <float between -1.0 and 1.0>,
    "label": <"HIGHLY_NEGATIVE" | "NEGATIVE" | "NEUTRAL" | "POSITIVE" | "HIGHLY_POSITIVE">,
    "rationale": "<2-3 sentence explanation>",
    "coinbase_api_updates": "<any relevant Coinbase API changes or empty string>",
    "key_developments": ["<development 1>", "<development 2>", "<development 3>"]
}

- -1.0 = Highly Negative (major hack, regulatory crackdown)
- -0.5 = Negative (minor exploit, unfavorable regulation)
- 0.0 = Neutral (business as usual)
- 0.5 = Positive (ETF inflows, adoption, upgrade)
- 1.0 = Highly Positive (game-changing adoption, major upgrade)

Pay special attention to Coinbase CDP or API updates that could affect our bot."""


class CryptoIndustryAgent:
    """Analyzes crypto industry developments and platform changes."""

    def __init__(self, tavily_tool=None):
        self.tavily_tool = tavily_tool
        self.name = "Crypto Industry & Platform Agent"

    def analyze(self) -> dict:
        """Run crypto industry analysis and return a scored report.

        Returns:
            dict with: agent_name, decision, score, rationale, raw_output
        """
        logger.info(f"{self.name}: Scanning crypto industry developments...")

        search_results = ""
        if self.tavily_tool:
            try:
                queries = [
                    "Bitcoin ETF flows institutional adoption",
                    "Ethereum upgrade crypto news today",
                    "crypto hack security incident",
                    "Coinbase Developer Platform SDK update API",
                    "crypto regulation SEC news 2026",
                ]
                for q in queries:
                    result = self.tavily_tool.run(query=q, max_results=3)
                    if result:
                        search_results += f"\n--- Search: {q} ---\n{result}\n"
            except Exception as e:
                logger.warning(f"Tavily search error: {e}")
                search_results = (
                    f"No real-time industry data (error: {e}). "
                    "Provide a neutral baseline."
                )
        else:
            search_results = (
                "No search tool available. Provide neutral baseline analysis."
            )

        try:
            response = completion(
                model=f"openai/{FAST_MODEL}",
                api_key=NOUS_API_KEY,
                api_base=NOUS_API_BASE,
                messages=[
                    {"role": "system", "content": CRYPTO_INDUSTRY_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Search Results:\n{search_results}\n\n"
                            "Analyze industry developments and return your JSON analysis."
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
                "decision": f"Industry: {result.get('label', 'NEUTRAL')}",
                "score": result.get("structural_score", 0.0),
                "rationale": result.get("rationale", ""),
                "raw_output": raw_output,
                "key_developments": result.get("key_developments", []),
                "coinbase_api_updates": result.get("coinbase_api_updates", ""),
            }

        except Exception as e:
            logger.error(f"{self.name}: Analysis failed: {e}")
            return {
                "agent_name": self.name,
                "decision": "ERROR",
                "score": 0.0,
                "rationale": f"Analysis failed: {str(e)}",
                "raw_output": "",
                "key_developments": [],
                "coinbase_api_updates": "",
            }