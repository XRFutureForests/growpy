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
    # Runs import_batch_*.py in numeric order, then post-import scripts
    # (e.g. growpy_pve_preset_import.py) automatically.
    python -m growpy.tools.ue_exec data/output/forest/unreal_scripts/

    # Import a single script:
    python -m growpy.tools.ue_exec data/output/forest/unreal_scripts/import_batch_01_european_oak.py

    # With resource limits:
    python -m growpy.tools.ue_exec data/output/forest/unreal_scripts/ --vram-limit 85

    # Disable the auto-restart watchdog (e.g. on a machine with a huge pagefile):
    python -m growpy.tools.ue_exec data/output/forest/unreal_scripts/ --restart-ram-limit 0

    # List UE editor instances:
    python -m growpy.tools.ue_exec --list-nodes
"""

import argparse
import logging
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger("growpy.ue_exec")

BATCH_PATTERN = re.compile(r"^import_batch_(\d+)_.+\.py$")

# Defaults for the auto-restart watchdog. Native Nanite/USD mesh builds leak
# committed memory that cleanup/GC cannot reclaim (see docs/guides/unreal-import.md
# troubleshooting); past a certain point Windows refuses to commit more pages
# ("paging file is too small") and UE crashes. Per-file/per-mesh progress
# tracking in the generated scripts makes killing and resuming UE safe, so we
# do it proactively instead of waiting for the crash.
DEFAULT_EDITOR_EXE = r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe"
DEFAULT_UPROJECT = r"D:\Unreal\XRLab\XRLab.uproject"

# Scripts to run after all numbered batches (order preserved).
# These depend on imported assets already existing in UE.
POST_IMPORT_SCRIPTS = [
    "growpy_wind_import.py",
    "growpy_pve_preset_import.py",
    "growpy_pve_graph_builder.py",
]


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
    _w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
except Exception:
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
    _acm = getattr(unreal, "AssetCompilingManager", None)
    if _acm is not None:
        _get = getattr(_acm, "get", None)
        _inst = _get() if callable(_get) else _acm
        _finish = getattr(_inst, "finish_all_compilation", None)
        if callable(_finish):
            _finish()
except Exception as _ace:
    print(f"  finish_all_compilation err: {_ace}")
try:
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)
except Exception:
    pass
gc.collect()
unreal.SystemLibrary.collect_garbage()
unreal.SystemLibrary.collect_garbage()
# Load a blank transient level to force Nanite page eviction from VRAM.
# Imported assets remain on disk -- only the GPU-resident pages are released.
try:
    _subsys = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    _subsys.new_level("/Engine/Maps/Templates/Template_Default")
    print("  Loaded blank level to release Nanite VRAM")
except Exception:
    try:
        unreal.EditorLevelLibrary.new_level("/Engine/Maps/Templates/Template_Default")
        print("  Loaded blank level to release Nanite VRAM")
    except Exception as _le:
        print(f"  Could not load blank level: {_le}")
gc.collect()
unreal.SystemLibrary.collect_garbage()
unreal.SystemLibrary.collect_garbage()
# Restore Nanite pools at reduced caps
# Re-acquire world reference after level change
_w = None
try:
    _w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
except Exception:
    try:
        _w = unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        pass
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
    """Find and sort batch import scripts, then append post-import scripts."""
    batches = []
    for f in scripts_dir.iterdir():
        m = BATCH_PATTERN.match(f.name)
        if m:
            batches.append((int(m.group(1)), f))
    batches.sort(key=lambda x: x[0])
    result = [f for _, f in batches]

    for name in POST_IMPORT_SCRIPTS:
        p = scripts_dir / name
        if p.exists():
            result.append(p)

    return result


ABORT_MARKER = "GROWPY_BATCH_ABORT_MEMORY"


def _run_single(
    script_path: Path,
    port: int,
    timeout: float,
) -> tuple[bool, bool]:
    """Send a single script to UE.

    Returns (success, aborted_memory) where aborted_memory is True when the
    batch printed the GROWPY_BATCH_ABORT_MEMORY marker. In that case the
    orchestrator must stop -- UE is near OOM and the user must restart it.
    """
    from growpy.io.unreal.ue_remote import run_file

    try:
        result = run_file(
            str(script_path),
            timeout=timeout,
            command_endpoint=("127.0.0.1", port),
        )
    except ConnectionError as e:
        logger.error("Connection failed: %s", e)
        return False, False
    except RuntimeError as e:
        logger.error("Execution error: %s", e)
        return False, False

    success = result.get("success", False)
    aborted = False
    output = result.get("output", [])
    if output:
        for line in output:
            text = line.get("output", "")
            if text:
                print(text)
                if ABORT_MARKER in text:
                    aborted = True

    if result.get("result"):
        result_text = result["result"]
        print(result_text)
        if ABORT_MARKER in result_text:
            aborted = True

    return success, aborted


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


def _find_ue_pids() -> list[int]:
    """Return PIDs of all running UnrealEditor processes."""
    try:
        import psutil
    except ImportError:
        return []
    pids = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = p.info.get("name") or ""
            if name.lower().startswith("unrealeditor"):
                pids.append(p.info["pid"])
        except Exception:
            pass
    return pids


def _kill_ue() -> bool:
    """Forcefully terminate all UnrealEditor processes. Returns True if any were found."""
    pids = _find_ue_pids()
    if pids:
        try:
            import psutil

            for pid in pids:
                try:
                    psutil.Process(pid).kill()
                except Exception:
                    pass
            return True
        except ImportError:
            pass
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", "UnrealEditor.exe"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def _launch_ue(editor_exe: str, uproject: str) -> None:
    """Launch UnrealEditor.exe with the given project, detached from this process."""
    subprocess.Popen(
        [editor_exe, uproject],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def _ue_alive(timeout: float = 2.0) -> bool:
    """Check whether a UE editor with Remote Execution is currently reachable."""
    from growpy.io.unreal.ue_remote import discover_nodes

    return bool(discover_nodes(timeout=timeout))


def _wait_for_ue_reachable(timeout: float = 300.0, poll: float = 5.0) -> bool:
    """Poll until a UE editor becomes reachable via Remote Execution, or time out."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _ue_alive(timeout=3.0):
            return True
        time.sleep(poll)
    return False


def _restart_ue(editor_exe: str, uproject: str, timeout: float = 300.0) -> bool:
    """Kill any running UE editor, relaunch it, and wait until reachable."""
    _kill_ue()
    time.sleep(3.0)
    _launch_ue(editor_exe, uproject)
    return _wait_for_ue_reachable(timeout=timeout)


class _RamWatchdog:
    """Background poller that kills UE proactively if RAM crosses a threshold.

    Runs alongside a blocking remote-exec call. Killing UE mid-call makes the
    blocked socket read raise a catchable ConnectionError, so the caller's
    normal failure path -- combined with per-file resume in the generated
    scripts -- handles the rest safely.
    """

    def __init__(self, ram_limit: float, poll_interval: float):
        self.ram_limit = ram_limit
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._triggered = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.ram_limit <= 0:
            return
        self._stop.clear()
        self._triggered.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            ram = _get_system_ram()
            if ram is not None:
                _, _, pct = ram
                if pct >= self.ram_limit:
                    logger.warning(
                        "  [Watchdog] RAM %.1f%% >= restart threshold %.1f%% -- "
                        "killing UE before it OOMs",
                        pct,
                        self.ram_limit,
                    )
                    self._triggered.set()
                    _kill_ue()
                    return
            if self._stop.wait(self.poll_interval):
                return

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def triggered(self) -> bool:
        return self._triggered.is_set()


def _run_single_with_restart(
    script_path: Path,
    port: int,
    timeout: float,
    editor_exe: str,
    uproject: str,
    restart_ram_limit: float,
    restart_poll_interval: float,
    max_restarts: int,
) -> tuple[bool, bool]:
    """Run a script, auto-restarting UE on crash or RAM-threshold breach.

    Per-file/per-mesh progress tracking in the generated scripts (done.txt)
    makes it safe to kill UE and resend the same script -- already-completed
    work is skipped. Returns the same (success, aborted_memory) tuple as
    _run_single, after exhausting max_restarts if UE keeps going down.
    """
    attempts = 0
    while True:
        watchdog = _RamWatchdog(restart_ram_limit, restart_poll_interval)
        watchdog.start()
        try:
            ok, aborted = _run_single(script_path, port, timeout)
        finally:
            watchdog.stop()

        if ok or aborted:
            return ok, aborted

        # Failure with UE still reachable is a genuine script error, not a
        # crash -- don't mask it with blind retries.
        if _ue_alive():
            return ok, aborted

        attempts += 1
        if attempts > max_restarts:
            logger.error(
                "  [Restart] UE down and exceeded max restarts (%d) for %s",
                max_restarts,
                script_path.name,
            )
            return False, False

        logger.warning(
            "  [Restart] UE not reachable (crashed or killed by watchdog) -- "
            "restarting (attempt %d/%d) and resuming %s",
            attempts,
            max_restarts,
            script_path.name,
        )
        if not _restart_ue(editor_exe, uproject):
            logger.error("  [Restart] UE did not come back online within timeout.")
            return False, False
        logger.info("  [Restart] UE reachable again, retrying %s", script_path.name)


def run_batches(
    scripts_dir: Path,
    port: int = 6776,
    timeout: float = 0,
    vram_limit: float = 75.0,
    ram_limit: float = 75.0,
    batch_delay: float = 10.0,
    editor_exe: str = DEFAULT_EDITOR_EXE,
    uproject: str = DEFAULT_UPROJECT,
    restart_ram_limit: float = 82.0,
    restart_poll_interval: float = 10.0,
    max_restarts: int = 10,
) -> list[str]:
    """Execute batch scripts sequentially with resource monitoring.

    Returns list of failed batch filenames.
    """
    batches = _discover_batch_scripts(scripts_dir)
    if not batches:
        logger.error("No executable scripts found in %s", scripts_dir)
        return ["<no batches>"]

    logger.info("=" * 60)
    logger.info("GrowPy UE Import Orchestrator")
    logger.info("=" * 60)
    logger.info("Scripts directory: %s", scripts_dir)
    logger.info("Batches found: %d", len(batches))
    for i, b in enumerate(batches):
        logger.info("  [%d/%d] %s", i + 1, len(batches), b.name)
    logger.info("VRAM limit: %.0f%%  |  RAM limit: %.0f%%", vram_limit, ram_limit)
    if restart_ram_limit > 0:
        logger.info(
            "Auto-restart watchdog: RAM >= %.0f%% triggers UE kill+restart+resume",
            restart_ram_limit,
        )
    logger.info("")

    _print_resources("before import")
    logger.info("")

    failed = []
    for idx, batch_path in enumerate(batches):
        label = f"[{idx + 1}/{len(batches)}]"
        logger.info("%s Sending %s ...", label, batch_path.name)
        t0 = time.monotonic()

        ok, aborted_memory = _run_single_with_restart(
            batch_path,
            port,
            timeout,
            editor_exe,
            uproject,
            restart_ram_limit,
            restart_poll_interval,
            max_restarts,
        )
        elapsed = time.monotonic() - t0

        if ok:
            logger.info("%s Completed in %.0fs", label, elapsed)
        else:
            logger.error("%s FAILED after %.0fs", label, elapsed)
            failed.append(batch_path.name)

        if aborted_memory:
            logger.error("")
            logger.error("=" * 60)
            logger.error("Batch aborted: UE private memory over limit")
            logger.error("Per-file progress is saved in done.txt next to each batch.")
            logger.error("Please restart Unreal Engine and re-run ue_exec to resume.")
            logger.error("=" * 60)
            return failed or [batch_path.name]

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
                    _, ram_pct = _print_resources()
                    if restart_ram_limit > 0 and ram_pct >= restart_ram_limit:
                        logger.warning(
                            "  RAM %.1f%% >= restart threshold %.1f%% after cleanup "
                            "-- restarting UE before continuing",
                            ram_pct,
                            restart_ram_limit,
                        )
                        if not _restart_ue(editor_exe, uproject):
                            logger.error(
                                "  UE did not come back online -- next batch may fail."
                            )
                    else:
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
        default=75.0,
        help="VRAM usage %% threshold to trigger cleanup between batches (default: 75)",
    )
    parser.add_argument(
        "--ram-limit",
        type=float,
        default=75.0,
        help="RAM usage %% threshold to trigger cleanup between batches (default: 75)",
    )
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=10.0,
        help="Minimum delay in seconds between batches (default: 10)",
    )
    parser.add_argument(
        "--editor-exe",
        default=DEFAULT_EDITOR_EXE,
        help=f"Path to UnrealEditor.exe for auto-restart (default: {DEFAULT_EDITOR_EXE})",
    )
    parser.add_argument(
        "--uproject",
        default=DEFAULT_UPROJECT,
        help=f"Path to the .uproject file for auto-restart (default: {DEFAULT_UPROJECT})",
    )
    parser.add_argument(
        "--restart-ram-limit",
        type=float,
        default=82.0,
        help=(
            "System RAM %% threshold that triggers an automatic UE kill+restart"
            "+resume, both proactively during a script and after a failed "
            "between-batch cleanup. 0 disables auto-restart (default: 82)"
        ),
    )
    parser.add_argument(
        "--restart-poll-interval",
        type=float,
        default=10.0,
        help="Seconds between RAM checks for the auto-restart watchdog (default: 10)",
    )
    parser.add_argument(
        "--max-restarts",
        type=int,
        default=10,
        help="Max automatic UE restarts per script before giving up (default: 10)",
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
            editor_exe=args.editor_exe,
            uproject=args.uproject,
            restart_ram_limit=args.restart_ram_limit,
            restart_poll_interval=args.restart_poll_interval,
            max_restarts=args.max_restarts,
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
    ok, aborted_memory = _run_single_with_restart(
        target,
        args.port,
        args.timeout,
        args.editor_exe,
        args.uproject,
        args.restart_ram_limit,
        args.restart_poll_interval,
        args.max_restarts,
    )
    if aborted_memory:
        logger.error(
            "Batch aborted: UE private memory over limit. Restart UE and rerun."
        )
        sys.exit(2)
    if not ok:
        logger.error("Script execution failed in UE.")
        sys.exit(1)
    logger.info("Script completed successfully in UE.")


if __name__ == "__main__":
    main()
