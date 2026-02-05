"""
TheStrat Scenario Detector

Implements the Three Universal Truths of price action:
- Scenario 1: Inside Bar (consolidation/equilibrium)
- Scenario 2: Trending Bar (directional move - 2U or 2D)
- Scenario 3: Outside Bar (failed trend that expanded)

Based on Rob Smith's TheStrat methodology.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Scenario(Enum):
    """The three scenarios of price action."""
    SCENARIO_1 = "1"      # Inside bar - consolidation
    SCENARIO_2_UP = "2U"  # Trending up - higher high, higher low
    SCENARIO_2_DOWN = "2D"  # Trending down - lower low, lower high
    SCENARIO_3 = "3"      # Outside bar - takes both sides
    UNKNOWN = "?"


@dataclass
class Candle:
    """Represents a single price candle/bar."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    timeframe: str = "1H"  # Default timeframe

    @property
    def is_bullish(self) -> bool:
        """Green candle - buyers won."""
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """Red candle - sellers won."""
        return self.close < self.open

    @property
    def body_size(self) -> float:
        """Size of candle body."""
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        """Total range of candle."""
        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        """Upper wick size."""
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        """Lower wick size."""
        return min(self.open, self.close) - self.low

    def distance_from_open(self) -> float:
        """How far price moved from open (signed)."""
        return self.close - self.open

    def distance_from_open_percent(self) -> float:
        """Percentage move from open."""
        if self.open == 0:
            return 0
        return ((self.close - self.open) / self.open) * 100


@dataclass
class ScenarioResult:
    """Result of scenario detection for a candle."""
    scenario: Scenario
    candle: Candle
    prev_candle: Optional[Candle]
    timestamp: datetime
    timeframe: str
    details: Dict = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}

    @property
    def is_inside(self) -> bool:
        return self.scenario == Scenario.SCENARIO_1

    @property
    def is_trending(self) -> bool:
        return self.scenario in (Scenario.SCENARIO_2_UP, Scenario.SCENARIO_2_DOWN)

    @property
    def is_trending_up(self) -> bool:
        return self.scenario == Scenario.SCENARIO_2_UP

    @property
    def is_trending_down(self) -> bool:
        return self.scenario == Scenario.SCENARIO_2_DOWN

    @property
    def is_outside(self) -> bool:
        return self.scenario == Scenario.SCENARIO_3

    def __repr__(self):
        return f"Scenario({self.scenario.value}, {self.timeframe}, bullish={self.candle.is_bullish})"


class ScenarioDetector:
    """
    Detects TheStrat scenarios from candle data.

    The Three Universal Truths:
    1. Price only does three things: inside (1), trending (2), or broadening (3)
    2. Across 4+ timeframes, price moves in direction of most Scenario 2s
    3. Price discovery happens as a broadening formation (series of 3s)
    """

    def __init__(self):
        """Initialize the scenario detector."""
        # History of detected scenarios by timeframe
        self._history: Dict[str, List[ScenarioResult]] = {}

    def detect_scenario(
        self,
        current: Candle,
        previous: Candle
    ) -> ScenarioResult:
        """
        Detect the scenario for the current candle relative to previous.

        Args:
            current: Current/most recent candle
            previous: Previous candle

        Returns:
            ScenarioResult with detected scenario
        """
        # Check for higher high and lower low
        higher_high = current.high > previous.high
        lower_low = current.low < previous.low
        higher_low = current.low > previous.low
        lower_high = current.high < previous.high

        details = {
            "higher_high": higher_high,
            "lower_low": lower_low,
            "higher_low": higher_low,
            "lower_high": lower_high,
            "current_bullish": current.is_bullish,
            "prev_bullish": previous.is_bullish,
        }

        # Scenario 3: Outside Bar - takes out BOTH sides
        # Higher high AND lower low
        if higher_high and lower_low:
            scenario = Scenario.SCENARIO_3
            details["description"] = "Outside bar - took both sides of previous range"

        # Scenario 2U: Trending Up - higher high, higher low (or at least higher high)
        elif higher_high and not lower_low:
            scenario = Scenario.SCENARIO_2_UP
            details["description"] = "Trending up - higher high without lower low"

        # Scenario 2D: Trending Down - lower low, lower high (or at least lower low)
        elif lower_low and not higher_high:
            scenario = Scenario.SCENARIO_2_DOWN
            details["description"] = "Trending down - lower low without higher high"

        # Scenario 1: Inside Bar - stays within previous range
        elif not higher_high and not lower_low:
            scenario = Scenario.SCENARIO_1
            details["description"] = "Inside bar - consolidation within previous range"

        else:
            scenario = Scenario.UNKNOWN
            details["description"] = "Unknown scenario"

        result = ScenarioResult(
            scenario=scenario,
            candle=current,
            prev_candle=previous,
            timestamp=current.timestamp,
            timeframe=current.timeframe,
            details=details
        )

        # Store in history
        tf = current.timeframe
        if tf not in self._history:
            self._history[tf] = []
        self._history[tf].append(result)

        # Keep history manageable
        if len(self._history[tf]) > 1000:
            self._history[tf] = self._history[tf][-500:]

        return result

    def detect_from_ohlc(
        self,
        current_ohlc: Tuple[float, float, float, float],
        prev_ohlc: Tuple[float, float, float, float],
        timeframe: str = "1H",
        timestamp: datetime = None
    ) -> ScenarioResult:
        """
        Detect scenario from OHLC tuples.

        Args:
            current_ohlc: (open, high, low, close) for current bar
            prev_ohlc: (open, high, low, close) for previous bar
            timeframe: Timeframe string (e.g., "1H", "D", "W")
            timestamp: Timestamp for current bar

        Returns:
            ScenarioResult
        """
        timestamp = timestamp or datetime.now()

        current = Candle(
            timestamp=timestamp,
            open=current_ohlc[0],
            high=current_ohlc[1],
            low=current_ohlc[2],
            close=current_ohlc[3],
            timeframe=timeframe
        )

        previous = Candle(
            timestamp=timestamp,  # Approximate
            open=prev_ohlc[0],
            high=prev_ohlc[1],
            low=prev_ohlc[2],
            close=prev_ohlc[3],
            timeframe=timeframe
        )

        return self.detect_scenario(current, previous)

    def detect_failed_2(
        self,
        candles: List[Candle]
    ) -> Optional[Dict]:
        """
        Detect a Failed 2 setup.

        A Failed 2 occurs when:
        - Price attempts to break a level (makes a 2U or 2D)
        - Fails to continue
        - Reverses back inside (closes opposite to the breakout)

        Args:
            candles: List of recent candles (at least 2)

        Returns:
            Dict with failed 2 details or None
        """
        if len(candles) < 2:
            return None

        current = candles[-1]
        previous = candles[-2]

        scenario = self.detect_scenario(current, previous)

        # Check for Failed 2U: Started as 2U (higher high) but closed bearish
        if scenario.scenario == Scenario.SCENARIO_2_UP and current.is_bearish:
            # Higher high but closed red - buyers failed
            return {
                "type": "FAILED_2U",
                "description": "Failed 2-Up: Broke higher but closed bearish",
                "entry_trigger": "Break below current candle low",
                "stop_loss": "Above current candle high",
                "target": "Previous candle low or lower",
                "candle": current,
                "scenario": scenario
            }

        # Check for Failed 2D: Started as 2D (lower low) but closed bullish
        if scenario.scenario == Scenario.SCENARIO_2_DOWN and current.is_bullish:
            # Lower low but closed green - sellers failed
            return {
                "type": "FAILED_2D",
                "description": "Failed 2-Down: Broke lower but closed bullish",
                "entry_trigger": "Break above current candle high",
                "stop_loss": "Below current candle low",
                "target": "Previous candle high or higher",
                "candle": current,
                "scenario": scenario
            }

        return None

    def detect_2_2_reversal(
        self,
        candles: List[Candle]
    ) -> Optional[Dict]:
        """
        Detect a 2-2 Reversal setup.

        A 2-2 Reversal occurs when:
        - A 2U is followed by a 2D (bearish reversal)
        - A 2D is followed by a 2U (bullish reversal)

        Args:
            candles: List of recent candles (at least 3)

        Returns:
            Dict with reversal details or None
        """
        if len(candles) < 3:
            return None

        # Get scenarios for last two bars
        prev_scenario = self.detect_scenario(candles[-2], candles[-3])
        curr_scenario = self.detect_scenario(candles[-1], candles[-2])

        # 2U followed by 2D = Bearish reversal
        if (prev_scenario.scenario == Scenario.SCENARIO_2_UP and
            curr_scenario.scenario == Scenario.SCENARIO_2_DOWN):
            return {
                "type": "2U_2D_REVERSAL",
                "direction": "BEARISH",
                "description": "2U-2D Reversal: Uptrend failed, now trending down",
                "entry_trigger": "Break below current candle low",
                "stop_loss": "Above the 2U high",
                "prev_scenario": prev_scenario,
                "curr_scenario": curr_scenario
            }

        # 2D followed by 2U = Bullish reversal
        if (prev_scenario.scenario == Scenario.SCENARIO_2_DOWN and
            curr_scenario.scenario == Scenario.SCENARIO_2_UP):
            return {
                "type": "2D_2U_REVERSAL",
                "direction": "BULLISH",
                "description": "2D-2U Reversal: Downtrend failed, now trending up",
                "entry_trigger": "Break above current candle high",
                "stop_loss": "Below the 2D low",
                "prev_scenario": prev_scenario,
                "curr_scenario": curr_scenario
            }

        return None

    def detect_inside_bar_setup(
        self,
        candles: List[Candle]
    ) -> Optional[Dict]:
        """
        Detect an Inside Bar breakout setup.

        An Inside Bar setup occurs when:
        - Current bar is a Scenario 1 (inside bar)
        - Waiting for breakout of its high or low

        Args:
            candles: List of recent candles (at least 2)

        Returns:
            Dict with inside bar setup details or None
        """
        if len(candles) < 2:
            return None

        current = candles[-1]
        previous = candles[-2]

        scenario = self.detect_scenario(current, previous)

        if scenario.scenario == Scenario.SCENARIO_1:
            return {
                "type": "INSIDE_BAR",
                "description": "Inside bar formed - compression/indecision",
                "long_entry": current.high,
                "short_entry": current.low,
                "long_stop": current.low,
                "short_stop": current.high,
                "candle": current,
                "scenario": scenario
            }

        return None

    def get_scenario_sequence(
        self,
        timeframe: str,
        count: int = 10
    ) -> List[ScenarioResult]:
        """
        Get recent scenario sequence for a timeframe.

        Args:
            timeframe: Timeframe to get history for
            count: Number of recent scenarios

        Returns:
            List of recent ScenarioResults
        """
        if timeframe not in self._history:
            return []
        return self._history[timeframe][-count:]

    def get_scenario_counts(
        self,
        timeframe: str,
        count: int = 10
    ) -> Dict[str, int]:
        """
        Get counts of each scenario type in recent history.

        Args:
            timeframe: Timeframe to analyze
            count: Number of recent bars to count

        Returns:
            Dict with scenario counts
        """
        recent = self.get_scenario_sequence(timeframe, count)

        counts = {
            "1": 0,
            "2U": 0,
            "2D": 0,
            "3": 0
        }

        for result in recent:
            if result.scenario == Scenario.SCENARIO_1:
                counts["1"] += 1
            elif result.scenario == Scenario.SCENARIO_2_UP:
                counts["2U"] += 1
            elif result.scenario == Scenario.SCENARIO_2_DOWN:
                counts["2D"] += 1
            elif result.scenario == Scenario.SCENARIO_3:
                counts["3"] += 1

        return counts

    def get_dominant_direction(
        self,
        timeframe: str,
        count: int = 10
    ) -> Tuple[str, float]:
        """
        Get the dominant direction based on Scenario 2s.

        "Price moves in the direction of the most Scenario 2s"

        Args:
            timeframe: Timeframe to analyze
            count: Number of recent bars

        Returns:
            Tuple of (direction: "UP"/"DOWN"/"NEUTRAL", confidence: 0-1)
        """
        counts = self.get_scenario_counts(timeframe, count)

        total_2s = counts["2U"] + counts["2D"]

        if total_2s == 0:
            return ("NEUTRAL", 0.5)

        up_ratio = counts["2U"] / total_2s

        if up_ratio > 0.6:
            return ("UP", up_ratio)
        elif up_ratio < 0.4:
            return ("DOWN", 1 - up_ratio)
        else:
            return ("NEUTRAL", 0.5)

    def clear_history(self, timeframe: str = None):
        """Clear scenario history."""
        if timeframe:
            self._history[timeframe] = []
        else:
            self._history.clear()
