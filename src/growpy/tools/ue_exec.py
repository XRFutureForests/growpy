"""Execute Python scripts in a running Unreal Engine 5 editor with monitoring.

Sends batch import scripts one at a time via the UE Remote Execution protocol,
with VRAM/RAM monitoring between batches. If a directory of batch scripts is
detected (unreal_scripts/), they are executed sequentially with progress tracking
and resource checks between each batch.

Uses the same UDP/TCP Remote Execution protocol that the VS Code
Unreal Python extension uses. Requires "Python Remote Execution"
enabled in UE Editor Preferences.

Usage:
    # Import all batches from a scripts directory (recommended):
    python -m growpy.tools.ue_exec data/output/forest/unreal_scripts/

    # Import a single script:
    python -m growpy.tools.ue_exec data/output/forest/unreal_scripts/import_batch_01_european_oak.py

    # With resource limits:
    python -m growpy.tools.ue_exec data/output/forest/unreal_scripts/ --vram-limit 85

    # List UE editor instances:
    python -m growpy.tools.ue_exec --list-nodes
"""

import argparse
import logging
import re
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger("growpy.ue_exec")

BATCH_PATTERN = re.compile(r"^import_batch_(\d+)_.+\.py$")


def _get_gpu_vram() -> tuple[int, int, float] | None:
    """Query GPU VRAM usage via nvidia-smi. Returns (used_mb, total_mb, pct)."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
                "--id=0",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            used = int(parts[0].strip())
            total = int(parts[1].strip())
            pct = round(used / total * 100, 1) if total > 0 else 0
            return (used, total, pct)
    except Exception:
        pass
    return None


def _get_system_ram() -> tuple[int, int, float] | None:
    """Query system RAM usage. Returns (used_mb, total_mb, pct)."""
    try:
        import psutil

        mem = psutil.virtual_memory()
        used = mem.used // (1024 * 1024)
        total = mem.total // (1024 * 1024)
        pct = round(mem.percent, 1)
        return (used, total, pct)
    except ImportError:
        pass

    # Fallback: Windows wmic
    try:
        result = subprocess.run(
            [
                "wmic",
                "OS",
                "get",
                "FreePhysicalMemory,TotalVisibleMemorySize",
                "/value",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            vals = {}
            for line in lines:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    vals[k.strip()] = int(v.strip())
            total_kb = vals.get("TotalVisibleMemorySize", 0)
            free_kb = vals.get("FreePhysicalMemory", 0)
            if total_kb > 0:
                total = total_kb // 1024
                used = (total_kb - free_kb) // 1024
                pct = round(used / total * 100, 1)
                return (used, total, pct)
    except Exception:
        pass
    return None


def _vram_bar(pct: float, width: int = 20) -> str:
    filled = int(width * pct / 100)
    return "#" * filled + "-" * (width - filled)


def _print_resources(context: str = "") -> tuple[float, float]:
    """Print current resource usage. Returns (vram_pct, ram_pct)."""
    vram_pct = 0.0
    ram_pct = 0.0

    vram = _get_gpu_vram()
    if vram:
        used, total, pct = vram
        vram_pct = pct
        logger.info("  [VRAM] %d/%d MB (%s%%) [%s]", used, total, pct, _vram_bar(pct))

    ram = _get_system_ram()
    if ram:
        used, total, pct = ram
        ram_pct = pct
        logger.info("  [RAM]  %d/%d MB (%s%%) [%s]", used, total, pct, _vram_bar(pct))

    if context:
        logger.info("  %s", context)

    return vram_pct, ram_pct


def _wait_for_resources(
    vram_limit: float,
    ram_limit: float,
    poll_interval: float = 15.0,
    timeout: float = 600.0,
) -> bool:
    """Wait until VRAM and RAM drop below limits. Returns True if settled."""
    vram_pct, ram_pct = _print_resources()

    if vram_pct < vram_limit and ram_pct < ram_limit:
        return True

    resource = "VRAM" if vram_pct >= vram_limit else "RAM"
    current = vram_pct if vram_pct >= vram_limit else ram_pct
    limit = vram_limit if vram_pct >= vram_limit else ram_limit
    logger.warning(
        "  %s at %.1f%% (limit: %.0f%%), waiting for it to settle...",
        resource,
        current,
        limit,
    )

    waited = 0.0
    while waited < timeout:
        time.sleep(poll_interval)
        waited += poll_interval
        vram_pct, ram_pct = _print_resources(
            f"waited {int(waited // 60)}m{int(waited % 60):02d}s"
        )
        if vram_pct < vram_limit and ram_pct < ram_limit:
            logger.info("  Resources settled, continuing")
            return True

    logger.warning("  Resources still high after %ds, proceeding anyway", int(timeout))
    return False


# UE-side cleanup script executed between batches when resources are high
_UE_CLEANUP_SCRIPT = """\
import unreal, gc
_w = None
try:
    _w = unreal.EditorLevelLibrary.get_editor_world()
except Exception:
    pass
if _w:
    for _cmd in (
        "FlushRenderingCommands",
        "r.Nanite.MaxAllocatedPages 0",
        "r.Nanite.Streaming.MaxPendingPages 0",
        "r.Streaming.FlushAll",
        "r.RHI.GPUDefrag",
        "r.D3D12.FreeAllPooledTextures",
        "r.D3D12.FreeUnusedResources",
    ):
        try:
            unreal.KismetSystemLibrary.execute_console_command(_w, _cmd)
        except Exception:
            pass
try:
    unreal.SystemLibrary.flush_async_loading()
except Exception:
    pass
try:
    unreal.AssetCompilingManager.get_default().finish_all_compilation()
except Exception:
    pass
try:
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)
except Exception:
    pass
gc.collect()
try:
    unreal.SystemLibrary.collect_garbage(full_purge=True)
except Exception:
    unreal.SystemLibrary.collect_garbage()
# Restore Nanite pools at reduced caps
if _w:
    for _cmd in (
        "r.Nanite.MaxAllocatedPages 512",
        "r.Nanite.Streaming.MaxPendingPages 32",
    ):
        try:
            unreal.KismetSystemLibrary.execute_console_command(_w, _cmd)
        except Exception:
            pass
print("CLEANUP COMPLETE")
"""


def _discover_batch_scripts(scripts_dir: Path) -> list[Path]:
    """Find and sort batch import scripts in a directory."""
    batches = []
    for f in sorted(scripts_dir.iterdir()):
        if BATCH_PATTERN.match(f.name):
            batches.append(f)
    return batches


def _run_single(
    script_path: Path,
    port: int,
    timeout: float,
) -> bool:
    """Send a single script to UE. Returns True on success."""
    from growpy.io.unreal.ue_remote import run_file

    try:
        result = run_file(
            str(script_path),
            timeout=timeout,
            command_endpoint=("127.0.0.1", port),
        )
    except ConnectionError as e:
        logger.error("Connection failed: %s", e)
        return False
    except RuntimeError as e:
        logger.error("Execution error: %s", e)
        return False

    success = result.get("success", False)
    output = result.get("output", [])
    if output:
        for line in output:
            text = line.get("output", "")
            if text:
                print(text)

    if result.get("result"):
        print(result["result"])

    return success


def _run_cleanup(port: int) -> None:
    """Send the VRAM cleanup script to UE."""
    from growpy.io.unreal.ue_remote import run_command

    logger.info("  Sending cleanup/GC to UE editor...")
    try:
        run_command(
            _UE_CLEANUP_SCRIPT,
            timeout=120,
            command_endpoint=("127.0.0.1", port),
        )
    except Exception as e:
        logger.warning("  Cleanup script failed: %s", e)


def run_batches(
    scripts_dir: Path,
    port: int = 6776,
    timeout: float = 0,
    vram_limit: float = 90.0,
    ram_limit: float = 90.0,
    batch_delay: float = 10.0,
) -> list[str]:
    """Execute batch scripts sequentially with resource monitoring.

    Returns list of failed batch filenames.
    """
    batches = _discover_batch_scripts(scripts_dir)
    if not batches:
        logger.error("No import_batch_*.py scripts found in %s", scripts_dir)
        return ["<no batches>"]

    logger.info("=" * 60)
    logger.info("GrowPy UE Import Orchestrator")
    logger.info("=" * 60)
    logger.info("Scripts directory: %s", scripts_dir)
    logger.info("Batches found: %d", len(batches))
    for i, b in enumerate(batches):
        logger.info("  [%d/%d] %s", i + 1, len(batches), b.name)
    logger.info("VRAM limit: %.0f%%  |  RAM limit: %.0f%%", vram_limit, ram_limit)
    logger.info("")

    _print_resources("before import")
    logger.info("")

    failed = []
    for idx, batch_path in enumerate(batches):
        label = f"[{idx + 1}/{len(batches)}]"
        logger.info("%s Sending %s ...", label, batch_path.name)
        t0 = time.monotonic()

        ok = _run_single(batch_path, port, timeout)
        elapsed = time.monotonic() - t0

        if ok:
            logger.info("%s Completed in %.0fs", label, elapsed)
        else:
            logger.error("%s FAILED after %.0fs", label, elapsed)
            failed.append(batch_path.name)

        # Resource check between batches (skip after last)
        if idx < len(batches) - 1:
            logger.info("")
            vram_pct, ram_pct = _print_resources(f"after {batch_path.name}")

            # If resources are high, run cleanup in UE first
            if vram_pct >= vram_limit or ram_pct >= ram_limit:
                _run_cleanup(port)
                time.sleep(batch_delay)
                settled = _wait_for_resources(
                    vram_limit, ram_limit, poll_interval=15.0, timeout=300.0
                )
                if not settled:
                    logger.warning(
                        "  Resources still high -- proceeding (Nanite VRAM is persistent)"
                    )
            else:
                time.sleep(batch_delay)

    logger.info("")
    logger.info("=" * 60)
    succeeded = len(batches) - len(failed)
    logger.info("Import complete: %d/%d batches succeeded", succeeded, len(batches))
    if failed:
        logger.error("Failed batches: %s", ", ".join(failed))
    logger.info("=" * 60)

    return failed


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Execute Python scripts in a running UE5 editor. "
            "Pass a directory to run all batch scripts with resource monitoring, "
            "or a single .py file to execute directly."
        ),
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Path to a .py script or an unreal_scripts/ directory",
    )
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
        help="Timeout in seconds per script (0 = no timeout)",
    )
    parser.add_argument(
        "--vram-limit",
        type=float,
        default=90.0,
        help="VRAM usage %% threshold to trigger cleanup between batches (default: 90)",
    )
    parser.add_argument(
        "--ram-limit",
        type=float,
        default=90.0,
        help="RAM usage %% threshold to trigger cleanup between batches (default: 90)",
    )
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=10.0,
        help="Minimum delay in seconds between batches (default: 10)",
    )
    parser.add_argument(
        "--list-nodes",
        action="store_true",
        help="List discovered UE editor instances and exit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    from growpy.io.unreal.ue_remote import discover_nodes

    if args.list_nodes:
        logger.info("Searching for UE editors...")
        nodes = discover_nodes(timeout=3.0)
        if not nodes:
            logger.error("No UE editors found. Is Python Remote Execution enabled?")
            sys.exit(1)
        for i, node in enumerate(nodes):
            logger.info("  [%d] %s", i, node.get("node_id", "unknown"))
        sys.exit(0)

    if not args.target:
        parser.error("A target script or directory is required.")

    target = Path(args.target).resolve()

    # Directory mode: run all batch scripts with monitoring
    if target.is_dir():
        failed = run_batches(
            target,
            port=args.port,
            timeout=args.timeout,
            vram_limit=args.vram_limit,
            ram_limit=args.ram_limit,
            batch_delay=args.batch_delay,
        )
        if failed:
            sys.exit(1)
        sys.exit(0)

    # Single file mode
    if not target.exists():
        logger.error("Not found: %s", target)
        sys.exit(1)

    if not target.suffix == ".py":
        logger.error("Expected a .py file or directory: %s", target)
        sys.exit(1)

    logger.info("Sending %s to UE editor...", target.name)
    ok = _run_single(target, args.port, args.timeout)
    if not ok:
        logger.error("Script execution failed in UE.")
        sys.exit(1)
    logger.info("Script completed successfully in UE.")


if __name__ == "__main__":
    main()
