"""Structured logging setup.

``print`` is reserved for ``cli.py``; everything else logs structured events so
that a run can be replayed from its log without re-reading the code.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure(verbose: bool = False, quiet: bool = False) -> None:
    """Configure structlog for human-readable stderr output.

    Args:
        verbose: Include debug events.
        quiet: Warnings and above only, for command output that is read as a
            report rather than watched as progress.

    """
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=logging.INFO)
    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger for a module."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
