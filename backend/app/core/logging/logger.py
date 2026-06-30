"""Structured logging helpers."""

import logging
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given name.

    Parameters:
        name: Logger name, typically __name__.

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)


logger = get_logger("personal_assistant")
