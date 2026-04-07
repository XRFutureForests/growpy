"""Minimal client for Unreal Engine 5 Python Remote Execution protocol.

Connects to a running UE editor via the same UDP/TCP protocol that
UE's PythonScriptPlugin exposes (and the VS Code extension uses).

Requires "Python Remote Execution" enabled in UE Editor Preferences:
  Edit > Editor Preferences > Plugins > Python > Remote Execution > Enable
"""

import json
import socket
import time
import uuid
import logging

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 1
PROTOCOL_MAGIC = "ue_py"

TYPE_PING = "ping"
TYPE_PONG = "pong"
TYPE_OPEN_CONNECTION = "open_connection"
TYPE_CLOSE_CONNECTION = "close_connection"
TYPE_COMMAND = "command"
TYPE_COMMAND_RESULT = "command_result"

MODE_EXEC_FILE = "ExecuteFile"
MODE_EXEC_STATEMENT = "ExecuteStatement"
MODE_EVAL_STATEMENT = "EvaluateStatement"

MULTICAST_GROUP = "239.0.0.1"
MULTICAST_PORT = 6766
MULTICAST_BIND = "127.0.0.1"
COMMAND_ENDPOINT = ("127.0.0.1", 6776)
RECV_BUF = 65536


def _make_msg(type_: str, source: str, dest: str = None, data: dict = None) -> bytes:
    obj = {
        "version": PROTOCOL_VERSION,
        "magic": PROTOCOL_MAGIC,
        "type": type_,
        "source": source,
    }
    if dest:
        obj["dest"] = dest
    if data:
        obj["data"] = data
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def _parse_msg(raw: bytes) -> dict | None:
    try:
        obj = json.loads(raw.decode("utf-8"))
        if obj.get("magic") != PROTOCOL_MAGIC:
            return None
        return obj
    except Exception:
        return None


def discover_nodes(timeout: float = 3.0, bind_address: str = MULTICAST_BIND) -> list[dict]:
    """Send UDP pings and collect pong responses from running UE editors."""
    node_id = str(uuid.uuid4())
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((bind_address, MULTICAST_PORT))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 0)
        sock.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_MULTICAST_IF,
            socket.inet_aton(bind_address),
        )
        sock.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_ADD_MEMBERSHIP,
            socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(bind_address),
        )
        sock.settimeout(0.5)

        nodes = {}
        deadline = time.monotonic() + timeout
        ping = _make_msg(TYPE_PING, node_id)

        while time.monotonic() < deadline:
            sock.sendto(ping, (MULTICAST_GROUP, MULTICAST_PORT))
            recv_until = min(time.monotonic() + 1.0, deadline)
            while time.monotonic() < recv_until:
                try:
                    data = sock.recv(RECV_BUF)
                except socket.timeout:
                    break
                msg = _parse_msg(data)
                if not msg or msg.get("type") != TYPE_PONG:
                    continue
                if msg.get("source") == node_id:
                    continue
                nodes[msg["source"]] = msg.get("data", {})
                nodes[msg["source"]]["node_id"] = msg["source"]
        return list(nodes.values())
    finally:
        sock.close()


def run_command(
    code: str,
    node_id: str = None,
    exec_mode: str = MODE_EXEC_FILE,
    timeout: float = 0,
    command_endpoint: tuple = COMMAND_ENDPOINT,
    bind_address: str = MULTICAST_BIND,
) -> dict:
    """Execute Python code in a running UE editor.

    Args:
        code: Python source code to execute.
        node_id: Target UE node ID. If None, uses the first discovered node.
        exec_mode: One of MODE_EXEC_FILE, MODE_EXEC_STATEMENT, MODE_EVAL_STATEMENT.
        timeout: TCP receive timeout in seconds. 0 = block until response.
        command_endpoint: (host, port) tuple for the local TCP server.
        bind_address: Local address for UDP multicast binding.

    Returns:
        dict with 'success' (bool), 'result' (str), and 'output' (list of log lines).
    """
    local_id = str(uuid.uuid4())

    # Discover UE node
    if not node_id:
        nodes = discover_nodes(timeout=3.0, bind_address=bind_address)
        if not nodes:
            raise ConnectionError(
                "No Unreal Engine editor found. "
                "Ensure UE is running with Python Remote Execution enabled "
                "(Edit > Editor Preferences > Plugins > Python > Remote Execution)."
            )
        node_id = nodes[0]["node_id"]
        logger.info("Found UE node: %s", node_id)

    # Open UDP broadcast socket
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind((bind_address, MULTICAST_PORT))
    udp.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    udp.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 0)
    udp.setsockopt(
        socket.IPPROTO_IP,
        socket.IP_MULTICAST_IF,
        socket.inet_aton(bind_address),
    )
    udp.setsockopt(
        socket.IPPROTO_IP,
        socket.IP_ADD_MEMBERSHIP,
        socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(bind_address),
    )

    # Set up TCP listener for UE to connect back to
    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_server.bind(command_endpoint)
    tcp_server.listen(1)
    tcp_server.settimeout(5)

    try:
        # Ask UE to connect to our TCP server
        open_msg = _make_msg(
            TYPE_OPEN_CONNECTION,
            local_id,
            node_id,
            {"command_ip": command_endpoint[0], "command_port": command_endpoint[1]},
        )
        tcp_conn = None
        for _ in range(6):
            udp.sendto(open_msg, (MULTICAST_GROUP, MULTICAST_PORT))
            try:
                tcp_conn, _ = tcp_server.accept()
                tcp_conn.setblocking(True)
                break
            except socket.timeout:
                continue
        if not tcp_conn:
            raise ConnectionError(
                "UE editor did not connect back. Check that Python Remote Execution "
                "is enabled and the editor is not blocked by a modal dialog."
            )

        # Send the command
        cmd_msg = _make_msg(
            TYPE_COMMAND,
            local_id,
            node_id,
            {"command": code, "unattended": True, "exec_mode": exec_mode},
        )
        tcp_conn.sendall(cmd_msg)

        # Receive the result (may be large, keep reading until connection closes or valid JSON)
        if timeout > 0:
            tcp_conn.settimeout(timeout)
        else:
            tcp_conn.settimeout(None)

        chunks = []
        while True:
            try:
                part = tcp_conn.recv(RECV_BUF)
                if not part:
                    break
                chunks.append(part)
                # Try to parse -- UE closes connection after result
                msg = _parse_msg(b"".join(chunks))
                if msg and msg.get("type") == TYPE_COMMAND_RESULT:
                    break
            except socket.timeout:
                break

        tcp_conn.close()

        result_msg = _parse_msg(b"".join(chunks))
        if not result_msg or result_msg.get("type") != TYPE_COMMAND_RESULT:
            raise RuntimeError("Did not receive a valid command_result from UE.")
        return result_msg.get("data", {})

    finally:
        # Notify UE to close the connection
        try:
            close_msg = _make_msg(TYPE_CLOSE_CONNECTION, local_id, node_id)
            udp.sendto(close_msg, (MULTICAST_GROUP, MULTICAST_PORT))
        except Exception:
            pass
        tcp_server.close()
        udp.close()


def run_file(
    filepath: str,
    timeout: float = 0,
    command_endpoint: tuple = COMMAND_ENDPOINT,
) -> dict:
    """Read a Python file and execute it in UE.

    Args:
        filepath: Path to the .py file to execute in UE.
        timeout: TCP receive timeout in seconds. 0 = block until response.
        command_endpoint: (host, port) tuple for the local TCP server.

    Returns:
        dict with 'success' (bool), 'result' (str), and 'output' (list of log lines).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()
    return run_command(code, timeout=timeout, command_endpoint=command_endpoint)
