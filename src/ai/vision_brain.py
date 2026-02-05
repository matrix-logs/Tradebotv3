"""
Vision-enabled AI Brain for chart analysis.
Uses Groq's vision models to actually SEE and analyze chart screenshots.
"""

import base64
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

try:
    from openai import OpenAI
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class TradingDecision(Enum):
    """Trading decisions from vision analysis."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"
    WAIT = "wait"


@dataclass
class TimeframeAnalysis:
    """Analysis for a single timeframe."""
    timeframe: str  # "monthly", "weekly", "daily", "hourly"
    scenario: str   # "1", "2U", "2D", "3"
    bias: str       # "bullish", "bearish", "neutral"
    candle_color: str  # "green", "red", "doji"
    notes: str = ""


@dataclass
class VisionAnalysis:
    """Complete vision analysis result."""
    decision: TradingDecision
    confidence: float
    reasoning: str

    # Timeframe breakdown
    monthly: Optional[TimeframeAnalysis] = None
    weekly: Optional[TimeframeAnalysis] = None
    daily: Optional[TimeframeAnalysis] = None
    hourly: Optional[TimeframeAnalysis] = None

    # FTFC status
    ftfc_status: str = "unknown"  # "UP", "DOWN", "MIXED"
    ftfc_aligned: bool = False

    # Price info
    current_price: Optional[float] = None
    key_levels: List[float] = field(default_factory=list)

    # Risk
    risk_level: str = "medium"
    suggested_entry: Optional[float] = None
    suggested_stop: Optional[float] = None
    suggested_target: Optional[float] = None

    # Meta
    timestamp: datetime = field(default_factory=datetime.now)
    raw_response: str = ""


class VisionBrain:
    """
    AI brain that can SEE charts using Groq's vision models.

    This sends actual screenshots to the AI, which analyzes:
    - Candle patterns across all timeframes
    - TheStrat scenarios (1, 2U, 2D, 3)
    - Full Timeframe Continuity (FTFC)
    - Support/resistance levels
    - Trading recommendations
    """

    # Groq API endpoint
    GROQ_BASE_URL = "https://api.groq.com/openai/v1"

    # Vision-capable models on Groq
    VISION_MODELS = {
        "llama-vision-90b": "llama-3.2-90b-vision-preview",  # Best quality
        "llama-vision-11b": "llama-3.2-11b-vision-preview",  # Faster
    }

    def __init__(
        self,
        api_key: str = None,
        model: str = "llama-vision-90b",
        config: Dict = None
    ):
        """
        Initialize vision brain.

        Args:
            api_key: Groq API key (or set GROQ_API_KEY env var)
            model: Vision model to use
            config: Additional configuration
        """
        if not VISION_AVAILABLE:
            raise ImportError("openai package required. Install: pip install openai")
        if not PIL_AVAILABLE:
            raise ImportError("Pillow required. Install: pip install Pillow")

        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("Groq API key required. Set GROQ_API_KEY env var or pass api_key")

        self.model = self.VISION_MODELS.get(model, model)
        self.config = config or {}

        # Initialize client
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.GROQ_BASE_URL
        )

        # Build the TheStrat analysis prompt
        self.system_prompt = self._build_system_prompt()

        # Rate limiting
        self._last_analysis_time = None
        self._min_interval = config.get("min_interval_seconds", 5) if config else 5

    def _build_system_prompt(self) -> str:
        """Build the system prompt for TheStrat visual analysis."""
        return """You are an expert forex/gold trader analyzing chart screenshots using TheStrat methodology by Rob Smith.

## Your Task
Analyze the trading chart screenshot. The screen shows multiple timeframes (typically Monthly, Weekly, Daily, and Hourly charts).

## TheStrat Scenarios - MEMORIZE THESE:

**Scenario 1 (Inside Bar):** Current candle is CONTAINED within previous candle
- Current High < Previous High AND Current Low > Previous Low
- Indicates consolidation, coiling energy
- Setup for breakout trade

**Scenario 2U (Uptrend):** Current candle takes out ONLY the previous HIGH
- Current High > Previous High AND Current Low >= Previous Low
- Bullish continuation signal

**Scenario 2D (Downtrend):** Current candle takes out ONLY the previous LOW
- Current Low < Previous Low AND Current High <= Previous High
- Bearish continuation signal

**Scenario 3 (Outside Bar):** Current candle takes out BOTH previous high AND low
- Indicates reversal or major expansion
- Most volatile scenario

## Full Timeframe Continuity (FTFC):
- FTFC UP: All timeframes showing bullish (green candles, 2U scenarios)
- FTFC DOWN: All timeframes showing bearish (red candles, 2D scenarios)
- MIXED: Timeframes not aligned (be cautious)

## Analysis Instructions:

1. Look at EACH visible timeframe chart
2. Identify the CURRENT candle's scenario (1, 2U, 2D, or 3)
3. Note the candle color (green=bullish, red=bearish)
4. Check if timeframes are aligned (FTFC)
5. Read the current price from the chart
6. Identify any key support/resistance levels

## Response Format (JSON):

```json
{
  "monthly": {"scenario": "2U", "bias": "bullish", "color": "green"},
  "weekly": {"scenario": "2U", "bias": "bullish", "color": "green"},
  "daily": {"scenario": "2D", "bias": "bearish", "color": "red"},
  "hourly": {"scenario": "1", "bias": "neutral", "color": "doji"},
  "ftfc_status": "MIXED",
  "ftfc_aligned": false,
  "current_price": 4881.51,
  "key_levels": [4900, 4850, 4800],
  "decision": "wait",
  "confidence": 0.6,
  "risk_level": "medium",
  "reasoning": "Higher timeframes bullish but daily showing pullback. Wait for daily to show continuation (2U) before entry.",
  "suggested_entry": null,
  "suggested_stop": null,
  "suggested_target": null
}
```

IMPORTANT:
- Always respond with valid JSON only
- If you can't see a timeframe clearly, mark it as "unknown"
- Be conservative - when in doubt, recommend "wait" or "hold"
- Focus on what you can ACTUALLY SEE in the chart"""

    def _encode_image(self, image: Union[str, Path, np.ndarray, "Image.Image"]) -> str:
        """
        Encode image to base64 for API.

        Args:
            image: File path, numpy array, or PIL Image

        Returns:
            Base64 encoded string
        """
        if isinstance(image, (str, Path)):
            # File path
            with open(image, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

        elif isinstance(image, np.ndarray):
            # Numpy array (from screen capture)
            img = Image.fromarray(image)
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        elif PIL_AVAILABLE and isinstance(image, Image.Image):
            # PIL Image
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

    def analyze_chart(
        self,
        screenshot: Union[str, Path, np.ndarray, "Image.Image"],
        symbol: str = "XAU/USD",
        additional_context: str = None
    ) -> VisionAnalysis:
        """
        Analyze a chart screenshot using vision AI.

        Args:
            screenshot: Chart screenshot (path, numpy array, or PIL Image)
            symbol: Trading symbol (e.g., "XAU/USD")
            additional_context: Any additional context to provide

        Returns:
            VisionAnalysis with complete breakdown
        """
        # Encode image
        image_base64 = self._encode_image(screenshot)

        # Build user message
        user_content = [
            {
                "type": "text",
                "text": f"Analyze this {symbol} chart using TheStrat methodology. Identify scenarios for each timeframe and provide a trading recommendation."
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_base64}"
                }
            }
        ]

        if additional_context:
            user_content[0]["text"] += f"\n\nAdditional context: {additional_context}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.3,
                max_tokens=1500
            )

            content = response.choices[0].message.content

            # Parse JSON from response
            result = self._parse_response(content)
            result.raw_response = content

            self._last_analysis_time = datetime.now()
            return result

        except Exception as e:
            return VisionAnalysis(
                decision=TradingDecision.HOLD,
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                risk_level="high",
                raw_response=str(e)
            )

    def _parse_response(self, content: str) -> VisionAnalysis:
        """Parse the AI response into structured VisionAnalysis."""
        try:
            # Try to extract JSON from response
            # Handle cases where response has text before/after JSON
            json_start = content.find("{")
            json_end = content.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")

            # Build timeframe analyses
            def parse_tf(tf_data: dict, tf_name: str) -> Optional[TimeframeAnalysis]:
                if not tf_data or tf_data.get("scenario") == "unknown":
                    return None
                return TimeframeAnalysis(
                    timeframe=tf_name,
                    scenario=tf_data.get("scenario", "unknown"),
                    bias=tf_data.get("bias", "neutral"),
                    candle_color=tf_data.get("color", "unknown")
                )

            return VisionAnalysis(
                decision=TradingDecision(data.get("decision", "hold")),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                monthly=parse_tf(data.get("monthly", {}), "monthly"),
                weekly=parse_tf(data.get("weekly", {}), "weekly"),
                daily=parse_tf(data.get("daily", {}), "daily"),
                hourly=parse_tf(data.get("hourly", {}), "hourly"),
                ftfc_status=data.get("ftfc_status", "unknown"),
                ftfc_aligned=data.get("ftfc_aligned", False),
                current_price=data.get("current_price"),
                key_levels=data.get("key_levels", []),
                risk_level=data.get("risk_level", "medium"),
                suggested_entry=data.get("suggested_entry"),
                suggested_stop=data.get("suggested_stop"),
                suggested_target=data.get("suggested_target")
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Return a basic analysis if parsing fails
            return VisionAnalysis(
                decision=TradingDecision.HOLD,
                confidence=0.3,
                reasoning=f"Could not parse full response: {content[:200]}...",
                risk_level="high"
            )

    def should_analyze(self) -> bool:
        """Check if enough time has passed for another analysis."""
        if self._last_analysis_time is None:
            return True
        elapsed = (datetime.now() - self._last_analysis_time).total_seconds()
        return elapsed >= self._min_interval


class VisionBrainManager:
    """
    Manages vision AI with caching and rate limiting.
    Provides continuous monitoring capability.
    """

    def __init__(self, api_key: str = None, config: Dict = None):
        self.config = config or {}
        self.brain: Optional[VisionBrain] = None
        self._initialize_brain(api_key)

        # Analysis cache
        self._last_analysis: Optional[VisionAnalysis] = None
        self._cache_ttl = config.get("cache_ttl_seconds", 30) if config else 30

    def _initialize_brain(self, api_key: str = None):
        """Initialize the vision brain."""
        try:
            model = self.config.get("model", "llama-vision-90b")
            self.brain = VisionBrain(
                api_key=api_key,
                model=model,
                config=self.config
            )
        except (ImportError, ValueError) as e:
            print(f"Warning: Vision brain not available: {e}")
            self.brain = None

    @property
    def is_available(self) -> bool:
        """Check if vision brain is available."""
        return self.brain is not None

    def analyze(
        self,
        screenshot: Union[str, Path, np.ndarray],
        symbol: str = "XAU/USD",
        force: bool = False
    ) -> Optional[VisionAnalysis]:
        """
        Analyze screenshot with caching.

        Args:
            screenshot: Chart screenshot
            symbol: Trading symbol
            force: Force new analysis (ignore cache)

        Returns:
            VisionAnalysis or None
        """
        if not self.is_available:
            return None

        # Check cache
        if not force and self._last_analysis:
            age = (datetime.now() - self._last_analysis.timestamp).total_seconds()
            if age < self._cache_ttl:
                return self._last_analysis

        # Check rate limit
        if not force and not self.brain.should_analyze():
            return self._last_analysis

        # Get fresh analysis
        analysis = self.brain.analyze_chart(screenshot, symbol)
        self._last_analysis = analysis

        return analysis

    def get_last_analysis(self) -> Optional[VisionAnalysis]:
        """Get the most recent analysis."""
        return self._last_analysis
