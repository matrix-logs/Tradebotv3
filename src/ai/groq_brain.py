"""
Groq AI Brain for trading decisions.
Uses Groq's free, ultra-fast LPU inference for real-time market analysis.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class AIDecision(Enum):
    """AI trading decisions."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"
    WAIT = "wait"  # Wait for better setup


@dataclass
class AIAnalysis:
    """Result of AI market analysis."""
    decision: AIDecision
    confidence: float  # 0-1
    reasoning: str
    key_observations: List[str]
    risk_level: str  # "low", "medium", "high"
    suggested_entry: Optional[float] = None
    suggested_stop: Optional[float] = None
    suggested_target: Optional[float] = None
    timeframe_analysis: Optional[Dict[str, str]] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class GroqBrain:
    """
    AI brain powered by Groq's ultra-fast inference.
    Analyzes market conditions and provides trading decisions.
    """

    # Groq API endpoint (OpenAI-compatible)
    GROQ_BASE_URL = "https://api.groq.com/openai/v1"

    # Available models on Groq (free tier)
    MODELS = {
        "llama3-70b": "llama-3.3-70b-versatile",  # Best reasoning
        "llama3-8b": "llama-3.1-8b-instant",      # Faster, lighter
        "mixtral": "mixtral-8x7b-32768",          # Good balance
        "gemma2": "gemma2-9b-it",                 # Google's model
    }

    def __init__(self, api_key: str = None, model: str = "llama3-70b", config: Dict = None):
        """
        Initialize Groq brain.

        Args:
            api_key: Groq API key (or set GROQ_API_KEY env var)
            model: Model to use (see MODELS dict)
            config: Additional configuration
        """
        if not GROQ_AVAILABLE:
            raise ImportError("openai package required. Install with: pip install openai")

        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key required. Set GROQ_API_KEY env var or pass api_key")

        self.model = self.MODELS.get(model, model)
        self.config = config or {}

        # Initialize OpenAI client pointing to Groq
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.GROQ_BASE_URL
        )

        # System prompt for TheStrat analysis
        self.system_prompt = self._build_system_prompt()

        # Cache for rate limiting
        self._last_analysis_time = None
        self._min_analysis_interval = config.get("min_interval_seconds", 5) if config else 5

    def _build_system_prompt(self) -> str:
        """Build the system prompt for TheStrat analysis."""
        return """You are an expert forex/gold trader specializing in TheStrat methodology by Rob Smith.

## TheStrat Core Concepts:

### Three Scenarios (Universal Truths):
- **Scenario 1 (Inside Bar)**: Current candle's high is lower than previous high AND low is higher than previous low. Indicates consolidation/coiling. Setup for breakout.
- **Scenario 2U (Up)**: Current candle takes out previous high but NOT the low. Bullish continuation.
- **Scenario 2D (Down)**: Current candle takes out previous low but NOT the high. Bearish continuation.
- **Scenario 3 (Outside Bar)**: Current candle takes out BOTH previous high and low. Reversal or expansion.

### Full Timeframe Continuity (FTFC):
- When Monthly, Weekly, Daily, and Hourly all show same direction (all 2U or all 2D)
- FTFC UP = All timeframes bullish = Strong long bias
- FTFC DOWN = All timeframes bearish = Strong short bias
- Partial continuity = Weaker signal, require more confirmation

### Key Setups:
1. **Inside Bar Breakout**: After Scenario 1, enter on break of the inside bar's high/low
2. **Failed 2U**: 2U that reverses = bearish signal
3. **Failed 2D**: 2D that reverses = bullish signal
4. **2-2 Reversal**: 2U followed by 2D (or vice versa) = reversal confirmation

## Your Task:
Analyze the provided market data and give a trading decision. Always consider:
1. Current scenario on each timeframe
2. Timeframe continuity/alignment
3. Key levels being tested
4. Risk/reward of potential entry

Respond in JSON format only:
{
    "decision": "strong_buy|buy|hold|sell|strong_sell|wait",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation",
    "key_observations": ["observation1", "observation2"],
    "risk_level": "low|medium|high",
    "suggested_entry": price or null,
    "suggested_stop": price or null,
    "suggested_target": price or null,
    "timeframe_analysis": {
        "monthly": "scenario and bias",
        "weekly": "scenario and bias",
        "daily": "scenario and bias",
        "hourly": "scenario and bias"
    }
}"""

    def analyze(
        self,
        current_price: float,
        timeframe_data: Dict[str, Dict],
        market_condition: Dict = None,
        additional_context: str = None
    ) -> AIAnalysis:
        """
        Analyze market conditions and provide trading decision.

        Args:
            current_price: Current market price
            timeframe_data: Dict with data for each timeframe
                {
                    "monthly": {"scenario": "2U", "bias": "bullish", "candles": [...]},
                    "weekly": {...},
                    "daily": {...},
                    "hourly": {...}
                }
            market_condition: Optional market condition data
            additional_context: Any additional context to provide

        Returns:
            AIAnalysis with decision and reasoning
        """
        # Build the analysis prompt
        prompt = self._build_analysis_prompt(
            current_price, timeframe_data, market_condition, additional_context
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower for more consistent analysis
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            # Parse response
            content = response.choices[0].message.content
            result = json.loads(content)

            return AIAnalysis(
                decision=AIDecision(result.get("decision", "hold")),
                confidence=float(result.get("confidence", 0.5)),
                reasoning=result.get("reasoning", ""),
                key_observations=result.get("key_observations", []),
                risk_level=result.get("risk_level", "medium"),
                suggested_entry=result.get("suggested_entry"),
                suggested_stop=result.get("suggested_stop"),
                suggested_target=result.get("suggested_target"),
                timeframe_analysis=result.get("timeframe_analysis")
            )

        except json.JSONDecodeError as e:
            return self._fallback_analysis(f"JSON parse error: {e}")
        except Exception as e:
            return self._fallback_analysis(f"API error: {e}")

    def _build_analysis_prompt(
        self,
        current_price: float,
        timeframe_data: Dict[str, Dict],
        market_condition: Dict = None,
        additional_context: str = None
    ) -> str:
        """Build the analysis prompt with market data."""
        prompt_parts = [
            f"## Current Market Data",
            f"**Symbol**: XAU/USD (Gold)",
            f"**Current Price**: ${current_price:.2f}",
            f"**Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Timeframe Analysis:"
        ]

        # Add timeframe data
        for tf_name, tf_data in timeframe_data.items():
            scenario = tf_data.get("scenario", "unknown")
            bias = tf_data.get("bias", "neutral")
            high = tf_data.get("high", "N/A")
            low = tf_data.get("low", "N/A")
            close = tf_data.get("close", "N/A")

            prompt_parts.append(f"### {tf_name.upper()}")
            prompt_parts.append(f"- Scenario: {scenario}")
            prompt_parts.append(f"- Bias: {bias}")
            prompt_parts.append(f"- High: {high}, Low: {low}, Close: {close}")
            prompt_parts.append("")

        # Add market condition if available
        if market_condition:
            prompt_parts.append("## Market Condition:")
            prompt_parts.append(f"- Regime: {market_condition.get('regime', 'unknown')}")
            prompt_parts.append(f"- Volatility: {market_condition.get('volatility', 'normal')}")
            prompt_parts.append(f"- Session: {market_condition.get('session', 'unknown')}")
            prompt_parts.append("")

        # Add additional context
        if additional_context:
            prompt_parts.append("## Additional Context:")
            prompt_parts.append(additional_context)
            prompt_parts.append("")

        prompt_parts.append("Based on TheStrat methodology, analyze this setup and provide your trading decision in JSON format.")

        return "\n".join(prompt_parts)

    def _fallback_analysis(self, error_msg: str) -> AIAnalysis:
        """Return a safe fallback analysis on error."""
        return AIAnalysis(
            decision=AIDecision.HOLD,
            confidence=0.0,
            reasoning=f"Analysis failed: {error_msg}. Defaulting to HOLD.",
            key_observations=["Error occurred during analysis"],
            risk_level="high"
        )

    def quick_scenario_check(self, candles: List[Dict]) -> str:
        """
        Quick local scenario detection without API call.
        Use this for rapid checks, save API calls for full analysis.

        Args:
            candles: List of candle dicts with 'high', 'low', 'open', 'close'

        Returns:
            Scenario string: "1", "2U", "2D", or "3"
        """
        if len(candles) < 2:
            return "unknown"

        current = candles[-1]
        previous = candles[-2]

        curr_high, curr_low = current['high'], current['low']
        prev_high, prev_low = previous['high'], previous['low']

        takes_high = curr_high > prev_high
        takes_low = curr_low < prev_low

        if takes_high and takes_low:
            return "3"  # Outside bar
        elif takes_high and not takes_low:
            return "2U"  # Up
        elif takes_low and not takes_high:
            return "2D"  # Down
        else:
            return "1"  # Inside bar

    def should_analyze(self) -> bool:
        """Check if enough time has passed for another API call."""
        if self._last_analysis_time is None:
            return True

        elapsed = (datetime.now() - self._last_analysis_time).total_seconds()
        return elapsed >= self._min_analysis_interval


class GroqBrainManager:
    """
    Manages AI brain usage with rate limiting and caching.
    """

    def __init__(self, api_key: str = None, config: Dict = None):
        self.config = config or {}
        self.brain = None
        self._initialize_brain(api_key)

        # Analysis cache
        self._cache: Dict[str, AIAnalysis] = {}
        self._cache_ttl = config.get("cache_ttl_seconds", 30) if config else 30

    def _initialize_brain(self, api_key: str = None):
        """Initialize the Groq brain if possible."""
        try:
            model = self.config.get("model", "llama3-70b")
            self.brain = GroqBrain(api_key=api_key, model=model, config=self.config)
        except (ImportError, ValueError) as e:
            print(f"Warning: Groq brain not available: {e}")
            self.brain = None

    @property
    def is_available(self) -> bool:
        """Check if AI brain is available."""
        return self.brain is not None

    def get_analysis(
        self,
        current_price: float,
        timeframe_data: Dict[str, Dict],
        market_condition: Dict = None,
        force: bool = False
    ) -> Optional[AIAnalysis]:
        """
        Get AI analysis with caching and rate limiting.

        Args:
            current_price: Current price
            timeframe_data: Timeframe data dict
            market_condition: Market condition dict
            force: Force new analysis (ignore cache)

        Returns:
            AIAnalysis or None if not available
        """
        if not self.is_available:
            return None

        # Check cache
        cache_key = f"{current_price:.0f}"
        if not force and cache_key in self._cache:
            cached = self._cache[cache_key]
            age = (datetime.now() - cached.timestamp).total_seconds()
            if age < self._cache_ttl:
                return cached

        # Check rate limiting
        if not force and not self.brain.should_analyze():
            return self._cache.get(cache_key)

        # Get fresh analysis
        analysis = self.brain.analyze(
            current_price=current_price,
            timeframe_data=timeframe_data,
            market_condition=market_condition
        )

        # Update cache
        self._cache[cache_key] = analysis
        self.brain._last_analysis_time = datetime.now()

        return analysis
