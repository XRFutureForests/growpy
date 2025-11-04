"""
Bridge for executing Python scripts in Unreal Engine via Remote Execution.

This module provides a clean interface for GrowPy to communicate with Unreal Engine
without requiring VSCode or manual intervention. It uses Unreal's native Remote
Execution protocol via direct TCP sockets (no external dependencies).
"""

import asyncio
import json
import logging
import socket
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

# Always available via socket implementation
REMOTE_EXECUTION_AVAILABLE = True

logger = logging.getLogger(__name__)


@dataclass
class UnrealConnectionConfig:
    """Configuration for Unreal Engine remote connection via TCP socket"""

    command_host: str = "127.0.0.1"
    command_port: int = 6776
    timeout: float = 5.0  # seconds


class UnrealRemoteBridge:
    """
    Bridge for executing Python code in Unreal Engine via TCP socket.

    Uses direct socket connection to Unreal's Remote Execution port (default 6776).
    No external dependencies required - uses Python standard library only.

    Example:
        ```python
        bridge = UnrealRemoteBridge()
        if await bridge.connect():
            result = await bridge.execute_script("unreal.log('Hello from GrowPy!')")
            print(result)
        ```
    """

    def __init__(self, config: Optional[UnrealConnectionConfig] = None):
        self.config = config or UnrealConnectionConfig()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._project_name: Optional[str] = "Connected"

    async def connect(self) -> bool:
        """
        Connect to running Unreal Engine instance via TCP socket.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(
                f"Connecting to Unreal Engine at {self.config.command_host}:{self.config.command_port}..."
            )

            # Open TCP connection to Unreal's Remote Execution port
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.config.command_host, self.config.command_port
                ),
                timeout=self.config.timeout,
            )

            logger.info("Successfully connected to Unreal Engine")
            return True

        except asyncio.TimeoutError:
            logger.error(f"Connection timeout after {self.config.timeout}s")
            return False
        except ConnectionRefusedError:
            logger.error(
                f"Connection refused. Make sure Unreal Engine is running with Python Remote Execution enabled."
            )
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Unreal Engine: {e}")
            return False

    async def disconnect(self):
        """Close connection to Unreal Engine"""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self._reader = None
                self._writer = None
                logger.info("Disconnected from Unreal Engine")

    async def execute_script(
        self, code: str, unattended: bool = True, mode: str = "execute"
    ) -> Optional[Dict[str, Any]]:
        """
        Execute Python code in Unreal Engine via socket protocol.

        The protocol sends JSON messages with length prefixes:
        - Send: 4-byte length + JSON command
        - Receive: 4-byte length + JSON response

        Args:
            code: Python code to execute
            unattended: If True, runs without user confirmation (ignored for socket)
            mode: "execute" or "evaluate" - evaluate returns expression result (ignored for socket)

        Returns:
            Response dict with 'success', 'result', and 'output' keys
        """
        if not self._writer or not self._reader:
            logger.error("Not connected to Unreal Engine. Call connect() first.")
            return None

        try:
            # Prepare command - just send the code directly
            # Unreal's Remote Execution protocol expects raw Python code
            command_bytes = code.encode("utf-8")

            # Send command: 4-byte length prefix + code
            length_prefix = struct.pack("<I", len(command_bytes))
            self._writer.write(length_prefix + command_bytes)
            await self._writer.drain()

            logger.debug(f"Sent command ({len(command_bytes)} bytes)")

            # Read response: 4-byte length prefix + response data
            length_data = await asyncio.wait_for(
                self._reader.readexactly(4), timeout=self.config.timeout
            )
            response_length = struct.unpack("<I", length_data)[0]

            logger.debug(f"Receiving response ({response_length} bytes)")

            response_data = await asyncio.wait_for(
                self._reader.readexactly(response_length), timeout=self.config.timeout
            )

            # Try to parse as JSON (Unreal may send JSON response)
            try:
                response_text = response_data.decode("utf-8")
                response = json.loads(response_text)
                success = response.get("success", True)
                result = response.get("result", response_text)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If not JSON, treat as plain text response
                result = response_data.decode("utf-8", errors="replace")
                success = True  # Assume success if we got a response

            logger.debug(f"Execution {'succeeded' if success else 'failed'}")

            return {"success": success, "result": result, "output": []}

        except asyncio.TimeoutError:
            logger.error("Script execution timeout")
            return {"success": False, "result": "Execution timeout", "output": []}
        except Exception as e:
            logger.error(f"Failed to execute script: {e}")
            return {"success": False, "result": str(e), "output": []}

    async def execute_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """
        Execute Python file in Unreal Engine.

        Args:
            filepath: Path to Python file to execute

        Returns:
            Response dict with execution results
        """
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return None

        code = filepath.read_text(encoding="utf-8")

        # Set __file__ variable in Unreal
        setup_code = f"__file__ = r'{filepath}'\n{code}"

        return await self.execute_script(setup_code)

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to Unreal Engine"""
        return self._writer is not None and not self._writer.is_closing()

    @property
    def project_name(self) -> Optional[str]:
        """Get connected Unreal project name (not available via socket)"""
        return self._project_name if self.is_connected else None


# Convenience function for one-off executions
async def execute_in_unreal(
    code: str, config: Optional[UnrealConnectionConfig] = None
) -> Optional[Dict[str, Any]]:
    """
    Execute Python code in Unreal Engine (convenience function).

    This creates a temporary connection, executes the code, and disconnects.
    For multiple executions, use UnrealRemoteBridge directly.

    Args:
        code: Python code to execute
        config: Optional connection configuration

    Returns:
        Execution response dict

    Example:
        ```python
        result = await execute_in_unreal('''
        import unreal
        unreal.log("Hello from GrowPy!")
        ''')
        ```
    """
    bridge = UnrealRemoteBridge(config)

    try:
        if await bridge.connect():
            return await bridge.execute_script(code)
    finally:
        await bridge.disconnect()

    return None


# Example usage for testing
if __name__ == "__main__":

    async def test_connection():
        """Test the Unreal remote bridge"""
        bridge = UnrealRemoteBridge()

        if await bridge.connect():
            print(f"Connected to project: {bridge.project_name}")

            # Test simple execution
            result = await bridge.execute_script(
                """
import unreal
unreal.log("GrowPy connection test successful!")
print("Current project:", unreal.SystemLibrary.get_project_directory())
            """
            )

            if result:
                print(f"Success: {result['success']}")
                print(f"Output: {result.get('output', [])}")

            await bridge.disconnect()
        else:
            print("Failed to connect to Unreal Engine")
            print("Make sure:")
            print("1. Unreal Engine is running")
            print("2. Python Remote Execution is enabled in project settings")
            print("3. Editor Scripting Utilities plugin is enabled")

    # Run the test
    asyncio.run(test_connection())
