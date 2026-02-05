"""
Alert manager for sending notifications about trading signals.
Supports desktop notifications, sound alerts, Discord, and Telegram.
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional

import requests

# Optional imports for notifications
try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False


class AlertManager:
    """
    Manages alerts and notifications for trading signals.
    """

    def __init__(self, config: Dict = None):
        """
        Initialize alert manager.

        Args:
            config: Alert configuration
        """
        self.config = config or {}

        # Alert settings
        self.desktop_enabled = self.config.get("desktop_notification", True)
        self.sound_enabled = self.config.get("sound_alert", False)
        self.sound_file = self.config.get("sound_file", "./assets/alert.wav")

        # Discord settings
        discord_config = self.config.get("discord", {})
        self.discord_enabled = discord_config.get("enabled", False)
        self.discord_webhook = discord_config.get("webhook_url", "")

        # Telegram settings
        telegram_config = self.config.get("telegram", {})
        self.telegram_enabled = telegram_config.get("enabled", False)
        self.telegram_token = telegram_config.get("bot_token", "")
        self.telegram_chat_id = telegram_config.get("chat_id", "")

        # Alert history
        self._alert_history = []
        self._last_alert_time: Optional[datetime] = None

    def send_alert(
        self,
        title: str,
        message: str,
        signal_type: str = "INFO",
        price: float = None,
        urgency: str = "normal"
    ) -> bool:
        """
        Send an alert through all enabled channels.

        Args:
            title: Alert title
            message: Alert message
            signal_type: Type of signal (BUY, SELL, INFO, WARNING)
            price: Current price (optional)
            urgency: Alert urgency (low, normal, high)

        Returns:
            True if at least one alert was sent successfully
        """
        success = False
        timestamp = datetime.now()

        # Build alert data
        alert_data = {
            "title": title,
            "message": message,
            "signal_type": signal_type,
            "price": price,
            "urgency": urgency,
            "timestamp": timestamp.isoformat()
        }

        # Desktop notification
        if self.desktop_enabled:
            if self._send_desktop(title, message, urgency):
                success = True

        # Sound alert
        if self.sound_enabled and urgency in ("normal", "high"):
            self._play_sound()

        # Discord
        if self.discord_enabled and self.discord_webhook:
            if self._send_discord(title, message, signal_type, price):
                success = True

        # Telegram
        if self.telegram_enabled and self.telegram_token:
            if self._send_telegram(title, message, signal_type, price):
                success = True

        # Record alert
        self._alert_history.append(alert_data)
        self._last_alert_time = timestamp

        return success

    def _send_desktop(self, title: str, message: str, urgency: str) -> bool:
        """Send desktop notification."""
        if not HAS_PLYER:
            print(f"[ALERT] {title}: {message}")
            return True

        try:
            # Map urgency to timeout
            timeout = {"low": 5, "normal": 10, "high": 15}.get(urgency, 10)

            notification.notify(
                title=title,
                message=message,
                app_name="ScreenTrader",
                timeout=timeout
            )
            return True
        except Exception as e:
            print(f"Desktop notification error: {e}")
            # Fallback to console
            print(f"[ALERT] {title}: {message}")
            return True

    def _play_sound(self):
        """Play alert sound."""
        try:
            # Try different sound methods
            if os.path.exists(self.sound_file):
                try:
                    import playsound
                    playsound.playsound(self.sound_file, block=False)
                except ImportError:
                    # Fallback to system beep
                    print("\a")  # Terminal bell
            else:
                print("\a")  # Terminal bell
        except Exception as e:
            print(f"Sound alert error: {e}")

    def _send_discord(
        self,
        title: str,
        message: str,
        signal_type: str,
        price: float = None
    ) -> bool:
        """Send Discord webhook notification."""
        try:
            # Color based on signal type
            colors = {
                "BUY": 0x00FF00,   # Green
                "SELL": 0xFF0000,  # Red
                "INFO": 0x0099FF,  # Blue
                "WARNING": 0xFFAA00  # Orange
            }
            color = colors.get(signal_type, 0x808080)

            # Build embed
            embed = {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {"text": "ScreenTrader Bot"}
            }

            if price:
                embed["fields"] = [
                    {"name": "Price", "value": f"${price:,.2f}", "inline": True},
                    {"name": "Signal", "value": signal_type, "inline": True}
                ]

            payload = {"embeds": [embed]}

            response = requests.post(
                self.discord_webhook,
                json=payload,
                timeout=10
            )

            return response.status_code in (200, 204)

        except Exception as e:
            print(f"Discord alert error: {e}")
            return False

    def _send_telegram(
        self,
        title: str,
        message: str,
        signal_type: str,
        price: float = None
    ) -> bool:
        """Send Telegram notification."""
        try:
            # Format message
            emoji = {
                "BUY": "\U0001F7E2",   # Green circle
                "SELL": "\U0001F534",  # Red circle
                "INFO": "\u2139\uFE0F",  # Info
                "WARNING": "\u26A0\uFE0F"  # Warning
            }.get(signal_type, "\U0001F4CA")

            text = f"{emoji} *{title}*\n\n{message}"
            if price:
                text += f"\n\n*Price:* ${price:,.2f}"

            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }

            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200

        except Exception as e:
            print(f"Telegram alert error: {e}")
            return False

    def send_signal_alert(
        self,
        signal_type: str,
        price: float,
        confidence: float,
        reasons: list,
        strategy: str
    ):
        """
        Send a formatted trading signal alert.

        Args:
            signal_type: BUY, SELL, or HOLD
            price: Current price
            confidence: Signal confidence
            reasons: List of signal reasons
            strategy: Strategy name
        """
        title = f"{signal_type} Signal Detected!"

        # Build message
        lines = [
            f"Strategy: {strategy}",
            f"Confidence: {confidence:.0%}",
            "",
            "Reasons:"
        ]
        for reason in reasons[:5]:  # Limit to 5 reasons
            lines.append(f"  - {reason}")

        message = "\n".join(lines)

        urgency = "high" if confidence > 0.8 else "normal"

        self.send_alert(
            title=title,
            message=message,
            signal_type=signal_type,
            price=price,
            urgency=urgency
        )

    def send_trade_alert(
        self,
        action: str,
        price: float,
        pnl: float = None,
        reason: str = ""
    ):
        """
        Send a trade execution alert.

        Args:
            action: BUY or SELL
            price: Execution price
            pnl: Profit/loss (if closing position)
            reason: Trade reason
        """
        if pnl is not None:
            title = f"Position Closed: {action}"
            pnl_text = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}"
            message = f"Closed at ${price:,.2f}\nP&L: {pnl_text}\n{reason}"
        else:
            title = f"Trade Executed: {action}"
            message = f"Entered at ${price:,.2f}\n{reason}"

        self.send_alert(
            title=title,
            message=message,
            signal_type=action,
            price=price,
            urgency="normal"
        )

    def send_error_alert(self, error: str, details: str = ""):
        """Send an error alert."""
        self.send_alert(
            title="Trading Bot Error",
            message=f"{error}\n{details}",
            signal_type="WARNING",
            urgency="high"
        )

    @property
    def alert_history(self):
        """Get alert history."""
        return self._alert_history.copy()

    def clear_history(self):
        """Clear alert history."""
        self._alert_history.clear()
