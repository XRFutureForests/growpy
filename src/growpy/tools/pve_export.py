"""Trigger the Export click of PVE graphs in the running Unreal editor.

PVE's Export is an asset-editor toolkit action (``FPVEditor::OnExport``), not a
UFUNCTION, so no Python or reflection route reaches it. This tool drives the
editor's own UI from outside instead, and needs neither focus nor an unlocked
desktop:

1. remote Python (``ue_remote``): enable ``Accessibility.Enable`` (Slate then
   answers Windows UI Automation), ``pcg.LogProfilingData`` (prints a per-node
   table when the graph has executed), read the graph's export nodes, and open
   the graph in its asset editor, which executes it;
2. wait for ``PVEditor initialized for <graph>`` and the PCG profiling table in
   the editor log -- the export reads the editor's inspection cache, so the
   graph must have finished executing;
3. ``pve_export_drive.ps1``: a posted mouse press gives the toolbar button
   Slate focus, a posted Ctrl+E fires the Export command, and the two modal
   dialogs (export settings: Batch + Export; overwrite prompt: Continue) are
   confirmed through UIA ``Invoke``;
4. wait for one ``Mesh exported successfully`` line per export node, then save
   the export folders (a PVE export exists only in memory until saved).

Usage::

    growpy-pve-export /Game/PVE/Graphs/PVG_SilverFir_1 /Game/PVE/Graphs/PVG_SilverFir_2
    growpy-pve-export /Game/PVE_Test/Graphs/PVG_Wind_Probe --no-save --keep-open
    growpy-pve-export ... --log "D:/Unreal/XRLabDB 5.8/Saved/Logs/XRLabDB.log"

The log path defaults to ``<uproject dir>/Saved/Logs/<project>.log`` from
``[unreal] uproject`` in config, else from the running editor's command line.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

logger = logging.getLogger("growpy.pve_export")

HERE = Path(__file__).resolve().parent
DRIVE_PS1 = HERE / "pve_export_drive.ps1"

# console variables the editor needs; all runtime-only, re-applied on every call
EDITOR_CVARS = (
    "Accessibility.Enable 1",
    "pcg.LogProfilingData 1",
    "Slate.AccessibleWidgetsProcessedPerTick 5000",
)

UE_OPEN_SCRIPT = """\
import json
import unreal

PATH = {path!r}
REOPEN = {reopen!r}
for cmd in {cvars!r}:
    unreal.SystemLibrary.execute_console_command(None, cmd)
asset = unreal.load_asset(PATH)
if asset is None:
    raise SystemExit("PVEXPORT_ERROR asset not found: %s" % PATH)
aes = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
if REOPEN:
    aes.close_all_editors_for_asset(asset)
info = {{"export_nodes": []}}
try:
    pv_instance = "/Script/ProceduralVegetation.ProceduralVegetationInstance"
    inst = unreal.new_object(unreal.load_class(None, pv_instance))
    gi = inst.get_editor_property("graph_instance")
    gi.set_editor_property("procedural_vegetation", asset)
    graph = gi.get_mutable_pcg_graph()
    for node in graph.get_editor_property("nodes"):
        settings = node.get_settings()
        if type(settings).__name__ != "PVExportSettings":
            continue
        entry = {{}}
        try:
            export = settings.get_editor_property("export_settings")
            for key in ("mesh_name", "content_browser_folder", "replace_policy"):
                try:
                    value = export.get_editor_property(key)
                    entry[key] = str(getattr(value, "path", value))
                except Exception:
                    pass
        except Exception as exc:
            entry["error"] = repr(exc)
        info["export_nodes"].append(entry)
except Exception as exc:
    info["error"] = repr(exc)
unreal.log("PVEXPORT_INFO " + json.dumps(info))
unreal.log("PVEXPORT_OPEN %s" % aes.open_editor_for_assets([asset]))
"""

UE_SAVE_SCRIPT = """\
import unreal

eal = unreal.EditorAssetLibrary
saved = 0
for folder in {folders!r}:
    for path in eal.list_assets(folder, recursive=True, include_folder=False):
        if eal.save_asset(path, only_if_is_dirty=True):
            saved += 1
for path in {assets!r}:
    if eal.does_asset_exist(path) and eal.save_asset(path, only_if_is_dirty=True):
        saved += 1
unreal.log("PVEXPORT_SAVED %d" % saved)
"""

UE_CLOSE_SCRIPT = """\
import unreal

asset = unreal.load_asset({path!r})
unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).close_all_editors_for_asset(asset)
unreal.log("PVEXPORT_CLOSED")
"""


def _run_in_editor(source: str, timeout: float = 600.0) -> list[str]:
    """Execute Python source in the editor; return its log lines."""
    from growpy.io.unreal import ue_remote

    fd, path = tempfile.mkstemp(prefix="growpy_pve_export_", suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(source)
    try:
        result = ue_remote.run_file(path, timeout=timeout)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    lines = []
    for line in result.get("output", []):
        text = line.get("output", "") if isinstance(line, dict) else str(line)
        lines.append(text.rstrip())
    if not result.get("success"):
        raise RuntimeError(f"editor script failed: {result.get('result')}")
    return lines


def _find_log_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    try:
        from growpy.config.core import get_config

        uproject = get_config().unreal_uproject
    except Exception:
        uproject = None
    if not uproject:
        # the running editor knows its project: read the .uproject off its command line
        try:
            out = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Process"
                    " -Filter \"Name='UnrealEditor.exe'\""
                    " | Select-Object -First 1).CommandLine",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            ).stdout
            match = re.search(r'"?([A-Za-z]:[^"]+?\.uproject)"?', out)
            uproject = match.group(1) if match else None
        except Exception:
            uproject = None
    if not uproject:
        raise SystemExit(
            "cannot resolve the editor log: pass --log, set [unreal] uproject "
            "in config, or start the editor"
        )
    project = Path(uproject)
    return project.parent / "Saved" / "Logs" / (project.stem + ".log")


def _read_log_from(log: Path, offset: int) -> str:
    with open(log, "rb") as fh:
        fh.seek(offset)
        return fh.read().decode("utf-8", errors="replace")


_PROFILE_TITLE = re.compile(r"LogPCG:\s+-+ .*\[.*\] -+")
_PROFILE_SEP = re.compile(r"LogPCG:\s+-{40,}\s*$")
_PROFILE_EXPORT_ROW = re.compile(r"LogPCG:\s+PVExport\s+\d+\s")


def _wait_for_graph_ready(
    log: Path, offset: int, name: str, timeout: float
) -> int | None:
    """Block until the opened graph has executed; return the PVExport row count."""
    deadline = time.time() + timeout
    initialized = False
    while time.time() < deadline:
        text = _read_log_from(log, offset)
        if not initialized and f"PVEditor initialized for {name}" in text:
            initialized = True
            logger.info("  editor initialized for %s", name)
        if initialized:
            # the profiling table: title, header, separator, rows, separator
            lines = text.splitlines()
            start = None
            for i, line in enumerate(lines):
                if _PROFILE_TITLE.search(line):
                    start = i
            if start is not None:
                seps = [
                    i for i in range(start, len(lines)) if _PROFILE_SEP.search(lines[i])
                ]
                if len(seps) >= 2:
                    rows = lines[seps[0] + 1 : seps[1]]
                    exports = sum(1 for row in rows if _PROFILE_EXPORT_ROW.search(row))
                    return exports
        time.sleep(2.0)
    return None


def _powershell() -> str:
    return shutil.which("pwsh") or shutil.which("powershell") or "powershell"


def _drive(
    name: str,
    log: Path,
    expected: int,
    export_timeout: float,
    locate: bool,
    toolbar: tuple[int, int] | None,
) -> int:
    cmd = [
        _powershell(),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(DRIVE_PS1),
        "-WindowTitle",
        name,
        "-LogPath",
        str(log),
        "-ExpectedMeshes",
        str(expected),
        "-ExportSec",
        str(int(export_timeout)),
    ]
    if toolbar:
        cmd += ["-ToolbarX", str(toolbar[0]), "-ToolbarY", str(toolbar[1])]
    if locate:
        cmd.append("-LocateToolbar")
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        logger.info("  %s", line.rstrip())
    return proc.wait()


def export_graphs(
    paths: list[str],
    *,
    log: Path,
    reopen: bool = True,
    save: bool = True,
    keep_open: bool = False,
    ready_timeout: float = 900.0,
    export_timeout: float = 3600.0,
    toolbar: tuple[int, int] | None = None,
) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for path in paths:
        name = path.rsplit("/", 1)[-1]
        logger.info("== %s", path)
        offset = log.stat().st_size
        lines = _run_in_editor(
            UE_OPEN_SCRIPT.format(path=path, reopen=reopen, cvars=EDITOR_CVARS)
        )
        info: dict = {}
        for line in lines:
            if "PVEXPORT_INFO " in line:
                info = json.loads(line.split("PVEXPORT_INFO ", 1)[1])
            elif "PVEXPORT_ERROR" in line:
                logger.error("  %s", line)
        nodes = info.get("export_nodes", [])
        if info.get("error"):
            logger.warning("  export-node read failed: %s", info["error"])
        logger.info(
            "  %d export node(s): %s",
            len(nodes),
            ", ".join(n.get("mesh_name", "?") for n in nodes),
        )
        expected = (
            _wait_for_graph_ready(log, offset, name, ready_timeout) if reopen else None
        )
        if expected is None:
            expected = len(nodes)
            logger.warning(
                "  graph-ready marker not seen; expecting %d mesh(es) from the "
                "export nodes",
                expected,
            )
        else:
            logger.info(
                "  graph executed, %d PVExport row(s) in the profiling table", expected
            )
        rc = _drive(name, log, expected, export_timeout, locate=False, toolbar=toolbar)
        if rc in (2, 3):
            logger.warning(
                "  toolbar offsets missed (rc=%d); retrying with a UIA locate", rc
            )
            rc = _drive(
                name, log, expected, export_timeout, locate=True, toolbar=toolbar
            )
        ok = rc == 0
        if ok and save:
            folders = sorted(
                {
                    n["content_browser_folder"]
                    for n in nodes
                    if n.get("content_browser_folder")
                }
            )
            exported = re.findall(
                r'Mesh exported successfully "[^"]+" ([^\r\n]+)',
                _read_log_from(log, offset),
            )
            assets = sorted({p for group in exported for p in group.split()})
            for line in _run_in_editor(
                UE_SAVE_SCRIPT.format(folders=folders, assets=assets), timeout=1800
            ):
                if "PVEXPORT_SAVED" in line:
                    logger.info("  %s", line.split("LogPython:")[-1].strip())
        if not keep_open:
            _run_in_editor(UE_CLOSE_SCRIPT.format(path=path))
        results[path] = ok
        logger.info("  %s", "OK" if ok else f"FAILED (rc={rc})")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "graphs",
        nargs="+",
        help="PVE graph asset paths, e.g. /Game/PVE/Graphs/PVG_SilverFir_1",
    )
    parser.add_argument(
        "--log",
        default=None,
        help="editor log file (default: derived from the uproject)",
    )
    parser.add_argument(
        "--no-reopen",
        action="store_true",
        help="do not close+reopen an already open graph editor",
    )
    parser.add_argument(
        "--no-save", action="store_true", help="leave the exported assets unsaved"
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="leave the graph editor open afterwards",
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=900.0,
        help="seconds to wait for the graph to execute after opening",
    )
    parser.add_argument(
        "--export-timeout",
        type=float,
        default=3600.0,
        help="seconds to wait for the export itself",
    )
    parser.add_argument(
        "--toolbar",
        default=None,
        metavar="X,Y",
        help="window-relative offset of the toolbar Export button (default 435,83)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )

    if not DRIVE_PS1.is_file():
        parser.error(f"driver script missing: {DRIVE_PS1}")
    toolbar = None
    if args.toolbar:
        x, y = args.toolbar.split(",")
        toolbar = (int(x), int(y))
    log = _find_log_path(args.log)
    if not log.is_file():
        parser.error(f"editor log not found: {log}")
    logger.info("editor log: %s", log)

    results = export_graphs(
        args.graphs,
        log=log,
        reopen=not args.no_reopen,
        save=not args.no_save,
        keep_open=args.keep_open,
        ready_timeout=args.ready_timeout,
        export_timeout=args.export_timeout,
        toolbar=toolbar,
    )
    failed = [p for p, ok in results.items() if not ok]
    logger.info("%d/%d graph(s) exported", len(results) - len(failed), len(results))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
