"""
Trading strategy module for decision making.

Includes TheStrat implementation based on Rob Smith's methodology.
"""

from .base_strategy import BaseStrategy
from .momentum_strategy import MomentumStrategy
from .breakout_strategy import BreakoutStrategy
from .strategy_manager import StrategyManager

# TheStrat components
from .scenario_detector import (
    Candle,
    Scenario,
    ScenarioDetector,
    ScenarioResult,
)
from .timeframe_continuity import (
    ContinuityResult,
    TimeframeBias,
    TimeframeContinuityAnalyzer,
    TimeframeState,
)
from .thestrat_strategy import (
    SetupType,
    StratSetup,
    TheStratStrategy,
)
from .market_condition import (
    MarketConditionDetector,
    MarketConditionResult,
    MarketRegime,
    TradingCondition,
)

__all__ = [
    # Base
    "BaseStrategy",
    "StrategyManager",

    # Legacy strategies (kept for reference)
    "MomentumStrategy",
    "BreakoutStrategy",

    # TheStrat - Scenario Detection
    "Candle",
    "Scenario",
    "ScenarioDetector",
    "ScenarioResult",

    # TheStrat - Timeframe Continuity
    "ContinuityResult",
    "TimeframeBias",
    "TimeframeContinuityAnalyzer",
    "TimeframeState",

    # TheStrat - Strategy
    "SetupType",
    "StratSetup",
    "TheStratStrategy",

    # Market Condition
    "MarketConditionDetector",
    "MarketConditionResult",
    "MarketRegime",
    "TradingCondition",
]
