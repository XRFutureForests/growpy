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


def is_verbose() -> bool:
    """Check if growpy logging is at INFO level or below (verbose mode).

    Useful for controlling progress bars and other user-facing output
    that should be suppressed in quiet mode.
    """
    return logging.getLogger("growpy").getEffectiveLevel() <= logging.INFO


def setup_logging(verbose: bool = False) -> None:
    """Configure the growpy logger hierarchy.

    Args:
        verbose: If True, set level to INFO. If False, set to WARNING.
    """
    global _configured
    if _configured:
        # Update level if already configured
        level = logging.INFO if verbose else logging.WARNING
        for name in ("growpy", "__main__"):
            logging.getLogger(name).setLevel(level)
        return

    level = logging.INFO if verbose else logging.WARNING

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    for name in ("growpy", "__main__"):
        lgr = logging.getLogger(name)
        lgr.setLevel(level)
        lgr.addHandler(handler)
        lgr.propagate = False

    _configured = True
