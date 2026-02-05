"""
Main trading bot orchestrator.
Coordinates all components for screen-based trading.
"""

import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

from .capture.screen_capture import ScreenCapture
from .vision.price_extractor import PriceExtractor, MarketSnapshot
from .signals.signal_detector import SignalDetector, TradingSignal, SignalType
from .signals.pattern_recognizer import PatternRecognizer
from .strategy.strategy_manager import StrategyManager
from .strategy.market_condition import MarketConditionDetector
from .actions.action_executor import ActionExecutor, ExecutionMode
from .actions.alert_manager import AlertManager
from .utils.config_loader import ConfigLoader
from .utils.data_store import DataStore
from .utils.logger import setup_logger, get_logger, TradeLogger


class ScreenTradingBot:
    """
    Main trading bot that reads the screen and makes trading decisions.

    This bot:
    1. Captures screen regions showing trading data
    2. Extracts prices and indicators using OCR
    3. Analyzes data using configurable strategies
    4. Generates signals and executes actions
    """

    def __init__(self, config_path: str = None):
        """
        Initialize the trading bot.

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config = ConfigLoader(config_path)

        # Setup logging
        log_level = self.config.get("general.log_level", "INFO")
        self.logger = setup_logger("tradebot", level=log_level)
        self.trade_logger = TradeLogger()

        self.logger.info("Initializing Screen Trading Bot...")

        # Initialize components
        self._init_components()

        # Bot state
        self.is_running = False
        self.is_paused = False
        self._start_time: Optional[datetime] = None
        self._tick_count = 0
        self._error_count = 0
        self._max_errors = 10

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.logger.info("Bot initialized successfully")

    def _init_components(self):
        """Initialize all bot components."""
        # Data store
        data_dir = self.config.get("general.data_dir", "./data")
        self.data_store = DataStore(data_dir)

        # Screen capture and OCR
        monitor = self.config.get("screen.monitor", 0)
        ocr_engine = self.config.get("ocr.engine", "easyocr")

        self.screen_capture = ScreenCapture(monitor=monitor)
        self.price_extractor = PriceExtractor(
            ocr_engine=ocr_engine,
            monitor=monitor
        )

        # Pattern recognition
        self.pattern_recognizer = PatternRecognizer(
            config=self.config.get("signals.colors", {})
        )

        # Signal detection
        self.signal_detector = SignalDetector(
            data_store=self.data_store,
            config=self.config.get("signals", {})
        )

        # Strategy management
        self.strategy_manager = StrategyManager(
            data_store=self.data_store,
            config=self.config.get("strategy", {})
        )

        # Market condition detector for adaptive strategy
        market_condition_config = self.config.get("strategy.market_condition", {})
        if market_condition_config.get("enabled", False):
            self.market_condition_detector = MarketConditionDetector(
                data_store=self.data_store,
                config=market_condition_config
            )
            self.strategy_manager.market_condition_detector = self.market_condition_detector
            self.logger.info("Market condition detection enabled")
        else:
            self.market_condition_detector = None

        # Alert management
        self.alert_manager = AlertManager(
            config=self.config.get("actions.alerts", {})
        )

        # Action execution
        self.action_executor = ActionExecutor(
            config=self.config.get("actions", {}),
            data_store=self.data_store,
            alert_manager=self.alert_manager
        )

        # Risk management
        self.risk_config = self.config.get("risk", {})
        self._trades_today = 0
        self._consecutive_losses = 0

    def start(self):
        """Start the trading bot main loop."""
        self.logger.info("Starting trading bot...")

        self.is_running = True
        self._start_time = datetime.now()

        # Check trading hours
        if not self._is_trading_hours():
            self.logger.warning("Outside trading hours. Bot will wait...")

        # Send startup alert
        self.alert_manager.send_alert(
            title="Trading Bot Started",
            message=f"Strategy: {self.strategy_manager.active_strategy_name}\nMode: {self.action_executor.mode.value}",
            signal_type="INFO"
        )

        # Main loop
        fps = self.config.get("screen.fps", 2)
        tick_interval = 1.0 / fps

        self.logger.info(f"Running at {fps} FPS (tick interval: {tick_interval:.2f}s)")

        try:
            while self.is_running:
                tick_start = time.time()

                try:
                    self._tick()
                except Exception as e:
                    self._handle_error(e)

                # Maintain frame rate
                elapsed = time.time() - tick_start
                sleep_time = max(0, tick_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")

        finally:
            self.stop()

    def _tick(self):
        """Execute one tick of the bot loop."""
        self._tick_count += 1

        # Skip if paused
        if self.is_paused:
            return

        # Check trading hours
        if not self._is_trading_hours():
            if self._tick_count % 60 == 0:  # Log every ~30 seconds at 2 FPS
                self.logger.debug("Outside trading hours")
            return

        # Check risk limits
        if not self._check_risk_limits():
            return

        # Get market snapshot
        regions = self.config.get_enabled_regions()
        snapshot = self.price_extractor.get_market_snapshot(regions)

        # Validate price data
        if snapshot.price is None or not snapshot.price.is_reliable:
            if self._tick_count % 10 == 0:
                self.logger.warning("Unable to read price from screen")
            return

        current_price = snapshot.price.value

        # Store price data
        self.data_store.add_price(
            price=current_price,
            confidence=snapshot.price.confidence,
            source="screen"
        )

        # Log price periodically
        if self._tick_count % 30 == 0:  # Every ~15 seconds at 2 FPS
            self.logger.info(f"Price: {current_price:.2f} (conf: {snapshot.price.confidence:.0%})")

        # Analyze market conditions if detector is available
        if self.market_condition_detector:
            market_condition = self.market_condition_detector.analyze(current_price)
            if self._tick_count % 60 == 0:  # Log market condition every ~30 seconds
                self.logger.info(
                    f"Market: {market_condition.regime.value} | "
                    f"Volatility: {market_condition.volatility_level} | "
                    f"Condition: {market_condition.trading_condition.value}"
                )

        # Get strategy signal
        indicators = snapshot.indicators
        signal = self.strategy_manager.get_signal(current_price, indicators)

        # Log signals
        if signal.signal_type != SignalType.HOLD:
            self.logger.info(
                f"Signal: {signal.signal_type.value} | "
                f"Strength: {signal.strength.name} | "
                f"Confidence: {signal.confidence:.0%}"
            )
            for reason in signal.reasons:
                self.logger.debug(f"  - {reason}")

        # Execute action if signal is actionable
        if signal.is_actionable:
            result = self.action_executor.execute(signal, current_price)

            if result.success:
                self._on_trade_executed(signal, result)

        # Reset error count on successful tick
        self._error_count = 0

    def _is_trading_hours(self) -> bool:
        """Check if current time is within trading hours."""
        if not self.risk_config.get("trading_hours", {}).get("enabled", False):
            return True

        now = datetime.now()

        # Check trading days
        trading_days = self.risk_config.get("trading_hours", {}).get("trading_days", [0, 1, 2, 3, 4])
        if now.weekday() not in trading_days:
            return False

        # Check trading hours
        start_str = self.risk_config.get("trading_hours", {}).get("start", "00:00")
        end_str = self.risk_config.get("trading_hours", {}).get("end", "23:59")

        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()

        return start_time <= now.time() <= end_time

    def _check_risk_limits(self) -> bool:
        """Check if risk limits allow trading."""
        # Check max trades per day
        max_trades = self.risk_config.get("max_trades_per_day", 100)
        if self._trades_today >= max_trades:
            if self._tick_count % 300 == 0:
                self.logger.warning(f"Max daily trades reached ({max_trades})")
            return False

        # Check consecutive losses
        max_losses = self.risk_config.get("max_consecutive_losses", 5)
        if self._consecutive_losses >= max_losses:
            if self._tick_count % 300 == 0:
                self.logger.warning(f"Max consecutive losses reached ({max_losses})")
            return False

        return True

    def _on_trade_executed(self, signal: TradingSignal, result):
        """Handle trade execution."""
        self._trades_today += 1

        # Log trade
        self.trade_logger.log_signal(
            signal_type=signal.signal_type.value,
            confidence=signal.confidence,
            price=signal.price,
            details={"strategy": signal.strategy, "reasons": signal.reasons}
        )

        # Start signal cooldown
        self.signal_detector.start_cooldown()

    def _handle_error(self, error: Exception):
        """Handle errors during tick execution."""
        self._error_count += 1
        self.logger.error(f"Tick error: {error}")

        if self._error_count >= self._max_errors:
            self.logger.critical(f"Too many errors ({self._error_count}), stopping bot")
            self.alert_manager.send_error_alert(
                error="Too many consecutive errors",
                details=str(error)
            )
            self.stop()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def stop(self):
        """Stop the trading bot."""
        if not self.is_running:
            return

        self.logger.info("Stopping trading bot...")
        self.is_running = False

        # Send shutdown alert
        runtime = datetime.now() - self._start_time if self._start_time else timedelta(0)
        stats = self.data_store.get_trade_stats()

        self.alert_manager.send_alert(
            title="Trading Bot Stopped",
            message=f"Runtime: {runtime}\nTrades: {stats['total_trades']}\nP&L: {stats['total_pnl']:.2f}",
            signal_type="INFO"
        )

        # Cleanup
        self.price_extractor.close()
        self.screen_capture.close()

        self.logger.info("Bot stopped successfully")

    def pause(self):
        """Pause trading (continue monitoring)."""
        self.is_paused = True
        self.logger.info("Trading paused")

    def resume(self):
        """Resume trading."""
        self.is_paused = False
        self.logger.info("Trading resumed")

    def get_status(self) -> Dict:
        """Get current bot status."""
        status = {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "tick_count": self._tick_count,
            "trades_today": self._trades_today,
            "mode": self.action_executor.mode.value,
            "strategy": self.strategy_manager.active_strategy_name,
            "trade_stats": self.data_store.get_trade_stats(),
            "recent_prices": len(self.data_store.price_history)
        }

        # Add market condition if available
        if self.market_condition_detector:
            prices = self.data_store.price_history
            if prices:
                current_price = prices[-1].get("price", 0)
                condition = self.market_condition_detector.analyze(current_price)
                status["market_condition"] = {
                    "regime": condition.regime.value,
                    "volatility": condition.volatility_level,
                    "trading_condition": condition.trading_condition.value
                }

        return status

    def set_strategy(self, name: str) -> bool:
        """Change active strategy."""
        success = self.strategy_manager.set_active_strategy(name)
        if success:
            self.logger.info(f"Strategy changed to: {name}")
        return success

    def set_mode(self, mode: str):
        """Change execution mode."""
        self.action_executor.set_mode(mode)
        self.logger.info(f"Execution mode changed to: {mode}")


def run_bot(config_path: str = None):
    """
    Run the trading bot.

    Args:
        config_path: Optional path to configuration file
    """
    bot = ScreenTradingBot(config_path)
    bot.start()


if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else None
    run_bot(config)
