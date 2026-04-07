"""Execute a Python script in a running Unreal Engine 5 editor.

Uses the same UDP/TCP Remote Execution protocol that the VS Code
Unreal Python extension uses. Requires "Python Remote Execution"
enabled in UE Editor Preferences.

Usage:
    python -m growpy.cli.ue_exec <script.py>
    python -m growpy.cli.ue_exec data/output/forest/unreal_scripts/import_forest.py
    growpy-ue-exec data/output/forest/unreal_scripts/import_forest.py
"""

import argparse
import sys
import logging
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Execute a Python script in a running UE5 editor.",
    )
    parser.add_argument("script", help="Path to the .py file to execute in UE")
    parser.add_argument(
        "--port",
        type=int,
        default=6776,
        help="Local TCP port for UE to connect back to (default: 6776)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0,
        help="Timeout in seconds waiting for the script to finish (0 = no timeout)",
    )
    parser.add_argument(
        "--list-nodes",
        action="store_true",
        help="List discovered UE editor instances and exit",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    logger = logging.getLogger("growpy.ue_exec")

    from growpy.io.unreal.ue_remote import discover_nodes, run_file

    if args.list_nodes:
        logger.info("Searching for UE editors...")
        nodes = discover_nodes(timeout=3.0)
        if not nodes:
            logger.error("No UE editors found. Is Python Remote Execution enabled?")
            sys.exit(1)
        for i, node in enumerate(nodes):
            logger.info("  [%d] %s", i, node.get("node_id", "unknown"))
        sys.exit(0)

    script_path = Path(args.script).resolve()
    if not script_path.exists():
        logger.error("Script not found: %s", script_path)
        sys.exit(1)

    logger.info("Sending %s to UE editor...", script_path.name)
    try:
        result = run_file(
            str(script_path),
            timeout=args.timeout,
            command_endpoint=("127.0.0.1", args.port),
        )
    except ConnectionError as e:
        logger.error(str(e))
        sys.exit(1)
    except RuntimeError as e:
        logger.error("Execution error: %s", e)
        sys.exit(1)

    success = result.get("success", False)
    output = result.get("output", [])
    if output:
        for line in output:
            print(line.get("output", ""))

    if result.get("result"):
        print(result["result"])

    if not success:
        logger.error("Script execution failed in UE.")
        sys.exit(1)

    logger.info("Script completed successfully in UE.")


if __name__ == "__main__":
    main()
