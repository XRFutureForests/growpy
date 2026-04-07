"""Tests for growpy.io.usd.tree_export utility functions."""

import pytest

from growpy.io.usd.tree_export import handle_bone_limit_error, is_bone_limit_error


class TestIsBoneLimitError:
    """Tests for is_bone_limit_error."""

    def test_matches_bone_limit_message(self):
        err = ValueError("Tree has 300 bones which exceeds the limit of 256")
        assert is_bone_limit_error(err) is True

    def test_rejects_unrelated_error(self):
        err = ValueError("Invalid mesh data")
        assert is_bone_limit_error(err) is False

    def test_rejects_partial_match_bones_only(self):
        err = ValueError("Too many bones in skeleton")
        assert is_bone_limit_error(err) is False

    def test_rejects_partial_match_limit_only(self):
        err = ValueError("Exceeded the limit of faces")
        assert is_bone_limit_error(err) is False


class TestHandleBoneLimitError:
    """Tests for handle_bone_limit_error."""

    def test_raises_system_exit(self):
        err = ValueError("300 bones exceeds limit of 256")
        with pytest.raises(SystemExit, match="1"):
            handle_bone_limit_error(err)
