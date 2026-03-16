"""Tests for growpy.utils.log module."""

import logging

import pytest

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


class TestCaplogIntegration:
    """Tests verifying log messages appear at expected levels via caplog."""

    def setup_method(self):
        log_module._configured = False
        logger = logging.getLogger("growpy")
        logger.handlers.clear()

    def test_info_captured_when_verbose(self, caplog):
        setup_logging(verbose=True)
        logger = logging.getLogger("growpy.test_caplog")
        with caplog.at_level(logging.DEBUG, logger="growpy"):
            logger.info("visible info message")
        assert "visible info message" in caplog.text

    def test_info_suppressed_when_quiet(self, caplog):
        setup_logging(verbose=False)
        logger = logging.getLogger("growpy.test_caplog")
        with caplog.at_level(logging.DEBUG, logger="growpy"):
            logger.info("hidden info message")
        assert "hidden info message" not in caplog.text

    def test_warning_captured_when_quiet(self, caplog):
        setup_logging(verbose=False)
        logger = logging.getLogger("growpy.test_caplog")
        with caplog.at_level(logging.DEBUG, logger="growpy"):
            logger.warning("warning message")
        assert "warning message" in caplog.text

    def test_child_logger_inherits_level(self, caplog):
        setup_logging(verbose=True)
        child = logging.getLogger("growpy.some.module")
        with caplog.at_level(logging.DEBUG, logger="growpy"):
            child.info("child info")
        assert "child info" in caplog.text
