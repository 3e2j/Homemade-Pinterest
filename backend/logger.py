"""Centralized logging system for backend."""

import sys
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


class Logger:
    """Simple terminal-based logger with prefix support."""

    def __init__(self, prefix: str = "[App]", level: LogLevel = LogLevel.INFO):
        self.prefix = prefix
        self.level = level

    def _log(self, level: LogLevel, message: str) -> None:
        """Write log message to stderr with level indicator."""
        if level.value < self.level.value:
            return
        level_str = level.name
        print(f"{self.prefix} [{level_str}] {message}", file=sys.stderr)

    def debug(self, message: str) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message)

    def info(self, message: str) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message)

    def warning(self, message: str) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message)

    def error(self, message: str) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message)


# Global logger instance
_logger = Logger("[Backend]", LogLevel.INFO)


def debug(message: str) -> None:
    """Log debug message."""
    _logger.debug(message)


def info(message: str) -> None:
    """Log info message."""
    _logger.info(message)


def warning(message: str) -> None:
    """Log warning message."""
    _logger.warning(message)


def error(message: str) -> None:
    """Log error message."""
    _logger.error(message)
