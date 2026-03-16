"""Tests for growpy.utils.log module."""

import logging

import growpy.utils.log as log_module
from growpy.utils.log import setup_logging


class TestSetupLogging:
    """Tests for setup_logging function."""

    def setup_method(self):
        """Reset _configured flag before each test."""
        log_module._configured = False
        logger = logging.getLogger("growpy")
        logger.handlers.clear()

    def test_verbose_sets_info_level(self):
        setup_logging(verbose=True)
        logger = logging.getLogger("growpy")
        assert logger.level == logging.INFO

    def test_quiet_sets_warning_level(self):
        setup_logging(verbose=False)
        logger = logging.getLogger("growpy")
        assert logger.level == logging.WARNING

    def test_adds_handler(self):
        setup_logging()
        logger = logging.getLogger("growpy")
        assert len(logger.handlers) == 1

    def test_idempotent_does_not_add_duplicate_handler(self):
        setup_logging(verbose=True)
        setup_logging(verbose=False)
        logger = logging.getLogger("growpy")
        assert len(logger.handlers) == 1

    def test_reconfigure_changes_level(self):
        setup_logging(verbose=False)
        logger = logging.getLogger("growpy")
        assert logger.level == logging.WARNING
        setup_logging(verbose=True)
        assert logger.level == logging.INFO

    def test_propagate_disabled(self):
        setup_logging()
        logger = logging.getLogger("growpy")
        assert logger.propagate is False
