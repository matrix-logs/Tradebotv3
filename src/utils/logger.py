"""
Logging utilities for the trading bot.
Provides colored console output and file logging.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


# Global console for rich output
console = Console()

# Store loggers to avoid duplicates
_loggers = {}


def setup_logger(
    name: str = "tradebot",
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: str = "./data/logs"
) -> logging.Logger:
    """
    Set up a logger with console and optional file output.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional specific log file name
        log_dir: Directory for log files

    Returns:
        Configured logger instance
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers = []  # Clear existing handlers

    # Rich console handler for beautiful output
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        markup=True
    )
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler
    if log_file or log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        if log_file is None:
            log_file = f"tradebot_{datetime.now().strftime('%Y%m%d')}.log"

        file_handler = logging.FileHandler(log_path / log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger


def get_logger(name: str = "tradebot") -> logging.Logger:
    """
    Get an existing logger or create a new one.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    if name in _loggers:
        return _loggers[name]
    return setup_logger(name)


class TradeLogger:
    """Specialized logger for trade events."""

    def __init__(self, log_dir: str = "./data/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.trade_file = self.log_dir / "trades.log"
        self.signal_file = self.log_dir / "signals.log"

    def log_signal(
        self,
        signal_type: str,
        confidence: float,
        price: float,
        details: dict
    ) -> None:
        """Log a trading signal."""
        timestamp = datetime.now().isoformat()
        entry = f"{timestamp} | {signal_type} | conf={confidence:.2f} | price={price} | {details}\n"

        with open(self.signal_file, "a") as f:
            f.write(entry)

    def log_trade(
        self,
        action: str,
        price: float,
        quantity: float = 1.0,
        details: Optional[dict] = None
    ) -> None:
        """Log a trade execution."""
        timestamp = datetime.now().isoformat()
        entry = f"{timestamp} | {action} | price={price} | qty={quantity} | {details or {}}\n"

        with open(self.trade_file, "a") as f:
            f.write(entry)
