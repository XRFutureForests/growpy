"""Tests for growpy.io.unreal.ue_remote protocol helpers."""

import json

from growpy.io.unreal.ue_remote import (
    MODE_EVAL_STATEMENT,
    MODE_EXEC_FILE,
    MODE_EXEC_STATEMENT,
    PROTOCOL_MAGIC,
    PROTOCOL_VERSION,
    TYPE_CLOSE_CONNECTION,
    TYPE_COMMAND,
    TYPE_COMMAND_RESULT,
    TYPE_OPEN_CONNECTION,
    TYPE_PING,
    TYPE_PONG,
    _make_msg,
    _parse_msg,
)


class TestMakeMsg:
    """Tests for UE protocol message construction."""

    def test_returns_bytes(self):
        result = _make_msg(TYPE_PING, "node-1")
        assert isinstance(result, bytes)

    def test_valid_json(self):
        raw = _make_msg(TYPE_PING, "node-1")
        obj = json.loads(raw.decode("utf-8"))
        assert obj["version"] == PROTOCOL_VERSION
        assert obj["magic"] == PROTOCOL_MAGIC
        assert obj["type"] == TYPE_PING
        assert obj["source"] == "node-1"

    def test_includes_dest(self):
        raw = _make_msg(TYPE_COMMAND, "src", "dst")
        obj = json.loads(raw.decode("utf-8"))
        assert obj["dest"] == "dst"

    def test_no_dest_when_none(self):
        raw = _make_msg(TYPE_PING, "src")
        obj = json.loads(raw.decode("utf-8"))
        assert "dest" not in obj

    def test_includes_data(self):
        raw = _make_msg(TYPE_COMMAND, "src", "dst", {"command": "print(1)"})
        obj = json.loads(raw.decode("utf-8"))
        assert obj["data"]["command"] == "print(1)"

    def test_no_data_when_none(self):
        raw = _make_msg(TYPE_PING, "src")
        obj = json.loads(raw.decode("utf-8"))
        assert "data" not in obj

    def test_utf8_encoding(self):
        raw = _make_msg(TYPE_COMMAND, "src", data={"command": "x = 'Aeichen'"})
        text = raw.decode("utf-8")
        assert "Aeichen" in text


class TestParseMsg:
    """Tests for UE protocol message parsing."""

    def test_valid_message(self):
        raw = json.dumps({
            "version": PROTOCOL_VERSION,
            "magic": PROTOCOL_MAGIC,
            "type": TYPE_PONG,
            "source": "ue-node",
        }).encode("utf-8")
        msg = _parse_msg(raw)
        assert msg is not None
        assert msg["type"] == TYPE_PONG
        assert msg["source"] == "ue-node"

    def test_wrong_magic_returns_none(self):
        raw = json.dumps({
            "version": 1,
            "magic": "wrong",
            "type": TYPE_PONG,
            "source": "x",
        }).encode("utf-8")
        assert _parse_msg(raw) is None

    def test_invalid_json_returns_none(self):
        assert _parse_msg(b"not json") is None

    def test_empty_bytes_returns_none(self):
        assert _parse_msg(b"") is None

    def test_command_result_with_data(self):
        raw = json.dumps({
            "version": PROTOCOL_VERSION,
            "magic": PROTOCOL_MAGIC,
            "type": TYPE_COMMAND_RESULT,
            "source": "ue-node",
            "data": {"success": True, "result": "42", "output": ["line1"]},
        }).encode("utf-8")
        msg = _parse_msg(raw)
        assert msg["data"]["success"] is True
        assert msg["data"]["result"] == "42"

    def test_roundtrip(self):
        data = {"command": "print('hello')", "exec_mode": MODE_EXEC_FILE}
        raw = _make_msg(TYPE_COMMAND, "src-1", "dst-2", data)
        msg = _parse_msg(raw)
        assert msg["type"] == TYPE_COMMAND
        assert msg["source"] == "src-1"
        assert msg["dest"] == "dst-2"
        assert msg["data"]["command"] == "print('hello')"


class TestProtocolConstants:
    """Tests for protocol constant values."""

    def test_exec_modes(self):
        assert MODE_EXEC_FILE == "ExecuteFile"
        assert MODE_EXEC_STATEMENT == "ExecuteStatement"
        assert MODE_EVAL_STATEMENT == "EvaluateStatement"

    def test_message_types(self):
        assert TYPE_PING == "ping"
        assert TYPE_PONG == "pong"
        assert TYPE_COMMAND == "command"
        assert TYPE_COMMAND_RESULT == "command_result"
        assert TYPE_OPEN_CONNECTION == "open_connection"
        assert TYPE_CLOSE_CONNECTION == "close_connection"
