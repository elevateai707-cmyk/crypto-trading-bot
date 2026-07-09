"""
Social Sentiment Agent — Retail Sentiment Analyst.

Scans X (Twitter), Reddit, and crypto news outlets to gauge retail
sentiment for the target asset. Returns a score from -1.0 to 1.0.
"""

import json
import logging
from typing import Optional

from litellm import completion

from config import NOUS_API_BASE, NOUS_API_KEY, FAST_MODEL

logger = logging.getLogger(__name__)


SOCIAL_SENTIMENT_SYSTEM_PROMPT = """You are a Retail Sentiment Analyst for a crypto trading desk.
Your job is to analyze social media and news sentiment for Bitcoin/crypto.

Analyze the provided search results from X (Twitter), Reddit (r/cryptocurrency),
and crypto news sites.

Return your analysis as a JSON object with exactly these fields:
{
    "sentiment_score": <float between -1.0 and 1.0>,
    "label": <"EXTREME_FEAR" | "FEAR" | "NEUTRAL" | "GREED" | "EXTREME_GREED">,
    "rationale": "<2-3 sentence explanation of what drove this score>",
    "key_signals": ["<signal 1>", "<signal 2>", "<signal 3>"]
}

- -1.0 = Extreme Fear (panic selling, capitulation)
- -0.5 = Fear (anxiety, uncertainty)
- 0.0 = Neutral (mixed signals, low engagement)
- 0.5 = Greed (optimism, FOMO building)
- 1.0 = Extreme Greed (euphoria, unsustainable hype)

Score each signal independently and average them for the final score.
Do not fabricate data — base your analysis strictly on the search results."""


class SocialSentimentAgent:
    """Analyzes retail sentiment from social media and news."""

    def __init__(self, tavily_tool=None):
        self.tavily_tool = tavily_tool
        self.name = "Social Sentiment Agent"

    def analyze(self, target_asset: str = "Bitcoin") -> dict:
        """Run sentiment analysis and return a scored report.

        Returns:
            dict with: agent_name, decision, score, rationale, raw_output
        """
        logger.info(f"{self.name}: Analyzing sentiment for {target_asset}...")

        search_results = ""
        if self.tavily_tool:
            try:
                queries = [
                    f"{target_asset} crypto sentiment today",
                    f"{target_asset} market sentiment reddit",
                    f"{target_asset} news fear greed",
                ]
                for q in queries:
                    result = self.tavily_tool.run(query=q, max_results=3)
                    if result:
                        search_results += f"\n--- Search: {q} ---\n{result}\n"
            except Exception as e:
                logger.warning(f"Tavily search error: {e}")
                search_results = (
                    f"No real-time search results available (error: {e}). "
                    "Provide a neutral baseline analysis."
                )
        else:
            search_results = (
                "No search tool available. Provide a neutral "
                "baseline sentiment analysis."
            )

        try:
            response = completion(
                model=f"openai/{FAST_MODEL}",
                api_key=NOUS_API_KEY,
                api_base=NOUS_API_BASE,
                messages=[
                    {"role": "system", "content": SOCIAL_SENTIMENT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Target asset: {target_asset}\n\n"
                            f"Search Results:\n{search_results}\n\n"
                            "Analyze the sentiment and return your JSON analysis."
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
                "decision": f"Sentiment: {result.get('label', 'NEUTRAL')}",
                "score": result.get("sentiment_score", 0.0),
                "rationale": result.get("rationale", ""),
                "raw_output": raw_output,
                "key_signals": result.get("key_signals", []),
            }

        except Exception as e:
            logger.error(f"{self.name}: Analysis failed: {e}")
            return {
                "agent_name": self.name,
                "decision": "ERROR",
                "score": 0.0,
                "rationale": f"Analysis failed: {str(e)}",
                "raw_output": "",
                "key_signals": [],
            }