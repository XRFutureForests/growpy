"""Centralized logging configuration for GrowPy.

Call setup_logging(verbose=True/False) once at CLI entry point to configure
the root 'growpy' logger. All modules use logging.getLogger(__name__) which
inherits from this root config.

When verbose=True:  INFO level, shows progress and status messages.
When verbose=False: WARNING level, only errors and warnings.
"""

import logging
import sys

_configured = False


def setup_logging(verbose: bool = False) -> None:
    """Configure the growpy logger hierarchy.

    Args:
        verbose: If True, set level to INFO. If False, set to WARNING.
    """
    global _configured
    if _configured:
        # Update level if already configured
        logger = logging.getLogger("growpy")
        logger.setLevel(logging.INFO if verbose else logging.WARNING)
        return

    logger = logging.getLogger("growpy")
    logger.setLevel(logging.INFO if verbose else logging.WARNING)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False
    _configured = True
