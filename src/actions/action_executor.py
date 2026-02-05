"""
Action executor for handling trade signals.
Supports alert-only mode, semi-automatic, and fully automatic execution.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from ..signals.signal_detector import SignalType, TradingSignal
from ..utils.data_store import DataStore, TradeRecord
from ..utils.logger import get_logger
from .alert_manager import AlertManager

# Optional import for mouse automation
try:
    import pyautogui
    HAS_PYAUTOGUI = True
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    pyautogui.PAUSE = 0.1
except ImportError:
    HAS_PYAUTOGUI = False


logger = get_logger("action_executor")


class ExecutionMode(Enum):
    """Trade execution modes."""
    ALERT_ONLY = "alert_only"      # Just send notifications
    SEMI_AUTO = "semi_auto"        # Position mouse, wait for confirmation
    FULL_AUTO = "full_auto"        # Execute trades automatically


@dataclass
class ExecutionResult:
    """Result of a trade execution attempt."""
    success: bool
    action: str
    price: float
    timestamp: datetime
    mode: ExecutionMode
    message: str
    confirmed: bool = False


class ActionExecutor:
    """
    Executes trading actions based on signals.

    Modes:
    - alert_only: Only sends alerts, no mouse/keyboard interaction
    - semi_auto: Positions mouse over buttons, waits for manual click
    - full_auto: Automatically clicks buttons (USE WITH CAUTION)
    """

    def __init__(
        self,
        config: Dict,
        data_store: DataStore,
        alert_manager: AlertManager = None
    ):
        """
        Initialize action executor.

        Args:
            config: Execution configuration
            data_store: DataStore for recording trades
            alert_manager: AlertManager for notifications
        """
        self.config = config
        self.data_store = data_store
        self.alert_manager = alert_manager or AlertManager(config.get("alerts", {}))

        # Execution mode
        mode_str = config.get("mode", "alert_only")
        self.mode = ExecutionMode(mode_str)

        # Button positions
        execution_config = config.get("execution", {})
        self.buy_button = tuple(execution_config.get("buy_button", [0, 0]))
        self.sell_button = tuple(execution_config.get("sell_button", [0, 0]))
        self.click_delay = execution_config.get("click_delay", 0.5)
        self.require_confirmation = execution_config.get("require_confirmation", True)

        # Safety settings
        self.max_trades_per_minute = 2
        self.cooldown_seconds = 30

        # State tracking
        self._last_execution_time: Optional[datetime] = None
        self._recent_executions: List[datetime] = []
        self._pending_action: Optional[Dict] = None

        # Callbacks
        self._pre_execute_callback: Optional[Callable] = None
        self._post_execute_callback: Optional[Callable] = None

    def execute(
        self,
        signal: TradingSignal,
        current_price: float
    ) -> ExecutionResult:
        """
        Execute action based on trading signal.

        Args:
            signal: Trading signal to act on
            current_price: Current market price

        Returns:
            ExecutionResult with outcome
        """
        # Check if signal is actionable
        if not signal.is_actionable:
            return ExecutionResult(
                success=False,
                action="NONE",
                price=current_price,
                timestamp=datetime.now(),
                mode=self.mode,
                message="Signal not actionable"
            )

        # Safety checks
        safety_check = self._check_safety()
        if not safety_check[0]:
            return ExecutionResult(
                success=False,
                action=signal.signal_type.value,
                price=current_price,
                timestamp=datetime.now(),
                mode=self.mode,
                message=f"Safety check failed: {safety_check[1]}"
            )

        # Determine action
        action = signal.signal_type.value  # "BUY" or "SELL"

        # Execute based on mode
        if self.mode == ExecutionMode.ALERT_ONLY:
            return self._execute_alert_only(signal, current_price)

        elif self.mode == ExecutionMode.SEMI_AUTO:
            return self._execute_semi_auto(signal, current_price)

        elif self.mode == ExecutionMode.FULL_AUTO:
            return self._execute_full_auto(signal, current_price)

        return ExecutionResult(
            success=False,
            action=action,
            price=current_price,
            timestamp=datetime.now(),
            mode=self.mode,
            message="Unknown execution mode"
        )

    def _execute_alert_only(
        self,
        signal: TradingSignal,
        price: float
    ) -> ExecutionResult:
        """Execute in alert-only mode."""
        action = signal.signal_type.value

        # Send alert
        self.alert_manager.send_signal_alert(
            signal_type=action,
            price=price,
            confidence=signal.confidence,
            reasons=signal.reasons,
            strategy=signal.strategy
        )

        logger.info(f"[ALERT] {action} signal at {price:.2f} (conf: {signal.confidence:.0%})")

        # Record execution
        self._record_execution(action, price, signal)

        return ExecutionResult(
            success=True,
            action=action,
            price=price,
            timestamp=datetime.now(),
            mode=self.mode,
            message=f"Alert sent for {action} signal"
        )

    def _execute_semi_auto(
        self,
        signal: TradingSignal,
        price: float
    ) -> ExecutionResult:
        """Execute in semi-automatic mode."""
        if not HAS_PYAUTOGUI:
            logger.warning("pyautogui not available, falling back to alert-only")
            return self._execute_alert_only(signal, price)

        action = signal.signal_type.value

        # Send alert
        self.alert_manager.send_signal_alert(
            signal_type=action,
            price=price,
            confidence=signal.confidence,
            reasons=signal.reasons,
            strategy=signal.strategy
        )

        # Position mouse over appropriate button
        button_pos = self.buy_button if action == "BUY" else self.sell_button

        if button_pos != (0, 0):
            try:
                pyautogui.moveTo(button_pos[0], button_pos[1], duration=0.3)
                logger.info(f"Mouse positioned for {action} at {button_pos}")
            except Exception as e:
                logger.error(f"Failed to position mouse: {e}")

        # Store pending action for potential confirmation
        self._pending_action = {
            "action": action,
            "price": price,
            "signal": signal,
            "timestamp": datetime.now()
        }

        return ExecutionResult(
            success=True,
            action=action,
            price=price,
            timestamp=datetime.now(),
            mode=self.mode,
            message=f"Mouse positioned for {action}. Click to confirm.",
            confirmed=False
        )

    def _execute_full_auto(
        self,
        signal: TradingSignal,
        price: float
    ) -> ExecutionResult:
        """Execute in fully automatic mode."""
        if not HAS_PYAUTOGUI:
            logger.warning("pyautogui not available, falling back to alert-only")
            return self._execute_alert_only(signal, price)

        action = signal.signal_type.value

        # Pre-execution callback
        if self._pre_execute_callback:
            if not self._pre_execute_callback(signal, price):
                return ExecutionResult(
                    success=False,
                    action=action,
                    price=price,
                    timestamp=datetime.now(),
                    mode=self.mode,
                    message="Pre-execution callback rejected"
                )

        # Confirmation if required
        if self.require_confirmation:
            logger.warning(f"AUTO-EXECUTE: {action} at {price:.2f}? (3 second window)")
            time.sleep(3)  # Give time to abort

        # Get button position
        button_pos = self.buy_button if action == "BUY" else self.sell_button

        if button_pos == (0, 0):
            return ExecutionResult(
                success=False,
                action=action,
                price=price,
                timestamp=datetime.now(),
                mode=self.mode,
                message=f"{action} button position not configured"
            )

        try:
            # Move to button
            pyautogui.moveTo(button_pos[0], button_pos[1], duration=0.2)

            # Wait before clicking
            time.sleep(self.click_delay)

            # Click
            pyautogui.click()

            logger.info(f"AUTO-EXECUTED: {action} at {price:.2f}")

            # Send confirmation alert
            self.alert_manager.send_trade_alert(
                action=action,
                price=price,
                reason=f"Auto-executed by {signal.strategy}"
            )

            # Record trade
            self._record_execution(action, price, signal)
            self._record_trade(action, price, signal)

            # Post-execution callback
            if self._post_execute_callback:
                self._post_execute_callback(signal, price, True)

            return ExecutionResult(
                success=True,
                action=action,
                price=price,
                timestamp=datetime.now(),
                mode=self.mode,
                message=f"Auto-executed {action}",
                confirmed=True
            )

        except Exception as e:
            logger.error(f"Auto-execution failed: {e}")

            if self._post_execute_callback:
                self._post_execute_callback(signal, price, False)

            return ExecutionResult(
                success=False,
                action=action,
                price=price,
                timestamp=datetime.now(),
                mode=self.mode,
                message=f"Execution failed: {e}"
            )

    def _check_safety(self) -> Tuple[bool, str]:
        """
        Perform safety checks before execution.

        Returns:
            Tuple of (is_safe, reason)
        """
        now = datetime.now()

        # Check cooldown
        if self._last_execution_time:
            elapsed = (now - self._last_execution_time).total_seconds()
            if elapsed < self.cooldown_seconds:
                return (False, f"Cooldown active ({self.cooldown_seconds - elapsed:.0f}s remaining)")

        # Check rate limit
        cutoff = now - timedelta(minutes=1)
        recent = [t for t in self._recent_executions if t > cutoff]
        if len(recent) >= self.max_trades_per_minute:
            return (False, f"Rate limit reached ({self.max_trades_per_minute}/min)")

        return (True, "")

    def _record_execution(self, action: str, price: float, signal: TradingSignal):
        """Record an execution for rate limiting."""
        now = datetime.now()
        self._last_execution_time = now
        self._recent_executions.append(now)

        # Clean old executions
        cutoff = now - timedelta(minutes=5)
        self._recent_executions = [t for t in self._recent_executions if t > cutoff]

    def _record_trade(self, action: str, price: float, signal: TradingSignal):
        """Record trade in data store."""
        trade = TradeRecord(
            timestamp=datetime.now(),
            action=action,
            price=price,
            quantity=1.0,
            signal_confidence=signal.confidence,
            strategy=signal.strategy,
            notes="; ".join(signal.reasons[:3])
        )
        self.data_store.add_trade(trade)

    def set_mode(self, mode: str):
        """Set execution mode."""
        self.mode = ExecutionMode(mode)
        logger.info(f"Execution mode set to: {mode}")

    def set_button_positions(self, buy: Tuple[int, int], sell: Tuple[int, int]):
        """Set button positions for auto-execution."""
        self.buy_button = buy
        self.sell_button = sell
        logger.info(f"Button positions set - Buy: {buy}, Sell: {sell}")

    def set_pre_execute_callback(self, callback: Callable):
        """Set callback to run before execution."""
        self._pre_execute_callback = callback

    def set_post_execute_callback(self, callback: Callable):
        """Set callback to run after execution."""
        self._post_execute_callback = callback

    def confirm_pending(self) -> Optional[ExecutionResult]:
        """Confirm and execute pending action."""
        if not self._pending_action:
            return None

        action = self._pending_action["action"]
        price = self._pending_action["price"]
        signal = self._pending_action["signal"]

        # Clear pending
        self._pending_action = None

        # Record as confirmed
        self._record_execution(action, price, signal)
        self._record_trade(action, price, signal)

        return ExecutionResult(
            success=True,
            action=action,
            price=price,
            timestamp=datetime.now(),
            mode=self.mode,
            message=f"Confirmed {action}",
            confirmed=True
        )

    def cancel_pending(self):
        """Cancel pending action."""
        self._pending_action = None
        logger.info("Pending action cancelled")

    @property
    def has_pending(self) -> bool:
        """Check if there's a pending action."""
        return self._pending_action is not None
