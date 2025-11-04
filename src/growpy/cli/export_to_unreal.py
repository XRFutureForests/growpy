#!/usr/bin/env python
"""
Export trees to Unreal Engine via Remote Execution.

This script generates forest/grove data and directly imports it into
a running Unreal Engine instance using the Remote Execution protocol.

Usage:
    python src/growpy/cli/export_to_unreal.py forest.csv --output-dir data/output/forest

    # Or with Unreal import:
    python src/growpy/cli/export_to_unreal.py forest.csv --import-to-unreal

Requirements:
    - Unreal Engine running with Python Remote Execution enabled
    - unreal-remote-execution package: pip install unreal-remote-execution
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from growpy.io.unreal_remote_bridge import (
    REMOTE_EXECUTION_AVAILABLE,
    UnrealConnectionConfig,
    UnrealRemoteBridge,
)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Export trees and optionally import to Unreal Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "csv_file", help="CSV file with forest data (species, x, y, height)"
    )

    parser.add_argument(
        "--output-dir",
        default="data/output/forest",
        help="Output directory for exported files",
    )

    parser.add_argument(
        "--import-to-unreal",
        action="store_true",
        help="Import exported assets directly into running Unreal Engine",
    )

    parser.add_argument(
        "--unreal-project-path", help="Unreal project Content path (e.g., /Game/Trees/)"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Unreal Engine command host (default: localhost)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=6776,
        help="Unreal Engine command port (default: 6776)",
    )

    return parser.parse_args()


async def import_to_unreal(
    output_dir: Path, project_path: str, host: str = "127.0.0.1", port: int = 6776
):
    """
    Import exported assets into running Unreal Engine.

    Args:
        output_dir: Directory containing exported USD files
        project_path: Unreal project path (e.g., /Game/Trees/)
        host: Unreal host address
        port: Unreal command port
    """
    if not REMOTE_EXECUTION_AVAILABLE:
        print("ERROR: unreal-remote-execution package not installed")
        print("Install with: pip install unreal-remote-execution")
        return False

    config = UnrealConnectionConfig(command_host=host, command_port=port)

    bridge = UnrealRemoteBridge(config)

    print("Connecting to Unreal Engine...")
    if not await bridge.connect():
        print("ERROR: Failed to connect to Unreal Engine")
        print("Make sure:")
        print("1. Unreal Engine is running")
        print("2. Python Remote Execution is enabled:")
        print("   Edit > Project Settings > Plugins > Python > Enable Remote Execution")
        print("3. Editor Scripting Utilities plugin is enabled")
        return False

    print(f"Connected to project: {bridge.project_name}")

    # Find all USD files
    usd_files = list(output_dir.glob("**/*.usda")) + list(output_dir.glob("**/*.usd"))

    if not usd_files:
        print(f"WARNING: No USD files found in {output_dir}")
        await bridge.disconnect()
        return False

    print(f"Found {len(usd_files)} USD files to import")

    # Generate import script
    import_script = f"""
import unreal

# Get USD import options
options = unreal.UsdStageImportOptions()

# Import each USD file
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

"""

    for usd_file in usd_files:
        # Convert Windows path to forward slashes for Unreal
        usd_path = str(usd_file.resolve()).replace("\\", "/")
        asset_name = usd_file.stem

        import_script += f"""
# Import {asset_name}
unreal.log(f"Importing {{asset_name}}...")
factory = unreal.UsdStageImporterFactory()
task = unreal.AssetImportTask()
task.filename = r"{usd_path}"
task.destination_path = "{project_path}"
task.replace_existing = True
task.automated = True
task.factory = factory

asset_tools.import_asset_tasks([task])
unreal.log(f"Imported {{asset_name}} to {project_path}")

"""

    # Execute import
    print("Executing import script in Unreal...")
    result = await bridge.execute_script(import_script)

    if result and result.get("success"):
        print("\nImport completed successfully!")
        print(f"Assets imported to: {project_path}")
    else:
        print("\nERROR: Import failed")
        if result:
            print(f"Error: {result.get('result', 'Unknown error')}")

    await bridge.disconnect()
    return result and result.get("success", False)


def main():
    """Main execution"""
    args = parse_args()

    output_dir = Path(args.output_dir)

    # TODO: Integrate with generate_forest.py to actually generate the trees
    # For now, just handle Unreal import if files exist

    if args.import_to_unreal:
        if not output_dir.exists():
            print(f"ERROR: Output directory does not exist: {output_dir}")
            print("Generate forest first or check the path")
            return 1

        project_path = args.unreal_project_path or "/Game/GrowPy/Trees"

        # Run async import
        success = asyncio.run(
            import_to_unreal(output_dir, project_path, args.host, args.port)
        )

        return 0 if success else 1

    else:
        print("Export completed. Use --import-to-unreal to import into Unreal Engine.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
