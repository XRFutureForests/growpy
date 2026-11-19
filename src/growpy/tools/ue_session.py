"""One Unreal editor session: launch, wait ready, run scripts, export graphs, quit.

``growpy-ue-session`` replaces the daily editor-session shell scripts (cleanup
class E, owner 2026-11-19). One invocation:

1. ``--lock NAME``: refuse when the lock folder holds any lock or an
   UnrealEditor process runs; write ``NAME.lock`` with a one-line purpose and
   always remove it at the end;
2. set ``PackageRestoreData.json`` aside when it would show UE's Restore
   Packages dialog, which blocks a headless start (the restore guard);
3. launch the editor (``-XRFFBatch``), print ``editor pid N`` and start a
   commit-charge guard that kills only that PID above ``--commit-limit``;
4. wait for a remote-exec ping. Zen splash trap: when the editor log's last
   line is "Waiting for ZenServer to be ready..." and no ping answered within
   ``--zen-timeout``, kill the own PID and its CrashReportClient, relaunch once;
5. the steps, in command-line order: ``--run`` (synchronous),
   ``--run-until-done`` (a ticker script: wait for its done file) and
   ``--export`` (adjacent exports go to ``growpy-pve-export`` as one call);
6. quit through remote exec, then kill the own PID if it is still alive --
   never an editor by image name;
7. the restore guard again.

Usage::

    growpy-ue-session --lock editor-e124 --purpose "E124 crown-base fill" \\
        --run build_graphs.py 1500 --export /Game/Generated/Trees/Graphs/PVG_ScotsPine_1
    growpy-ue-session --run-until-done fill.py data/tmp/fill/done.json 3600

Paths come from the arguments or the environment, never from constants:
``--project`` (``GROWPY_UE_UPROJECT``, the .uproject), ``--engine``
(``GROWPY_UE_ENGINE``, UnrealEditor.exe) and ``--lock-dir`` (``GROWPY_LOCK_DIR``).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

ENV_PROJECT = "GROWPY_UE_UPROJECT"  # the .uproject path
UE_REMOTE_PROJECT = "GROWPY_UE_PROJECT"  # ue_remote's own: a project name
ENV_ENGINE = "GROWPY_UE_ENGINE"
ENV_LOCK_DIR = "GROWPY_LOCK_DIR"

ZEN_WAIT_LINE = "Waiting for ZenServer to be ready..."
LAUNCH_FLAGS = ("-XRFFBatch",)

PING_SOURCE = "import unreal\nprint('project:', unreal.SystemLibrary.get_game_name())\n"
QUIT_SOURCE = "import unreal\nunreal.SystemLibrary.quit_editor()\n"


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# ----------------------------------------------------------------- arguments --


@dataclass(frozen=True)
class Step:
    """A step: ``run``, ``until`` (run, then wait for ``done``) or ``export``."""

    kind: str
    target: str
    timeout: float
    done: Path | None = None


class _StepAction(argparse.Action):
    """Append each step to ``namespace.steps`` in command-line order."""

    def __call__(self, parser, namespace, values, option_string=None):
        values = list(values)
        steps = list(getattr(namespace, "steps", None) or [])
        try:
            if self.dest == "run":
                if len(values) > 2:
                    raise ValueError
                steps.append(Step("run", values[0], _seconds(values[1:], 1500.0)))
            elif self.dest == "until":
                if not 2 <= len(values) <= 3:
                    raise ValueError
                steps.append(
                    Step(
                        "until",
                        values[0],
                        _seconds(values[2:], 3600.0),
                        Path(values[1]),
                    )
                )
            else:
                steps.append(Step("export", values[0], 0.0))
        except ValueError:
            parser.error(f"{option_string}: unexpected arguments {values}")
        namespace.steps = steps


def _seconds(rest: list[str], default: float) -> float:
    return float(rest[0]) if rest else default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="growpy-ue-session",
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project", help=f"the .uproject (default: ${ENV_PROJECT})")
    parser.add_argument("--engine", help=f"UnrealEditor.exe (default: ${ENV_ENGINE})")
    parser.add_argument(
        "--lock-dir", help=f"editor lock folder (default: ${ENV_LOCK_DIR})"
    )
    parser.add_argument(
        "--lock", metavar="NAME", help="take the editor slot as NAME.lock"
    )
    parser.add_argument("--purpose", default="", help="one-line purpose in the lock")
    parser.add_argument(
        "--commit-limit",
        type=float,
        default=85.0,
        help="kill the own editor above this commit charge %% (default 85)",
    )
    parser.add_argument(
        "--zen-timeout",
        type=float,
        default=360.0,
        help="seconds on the Zen splash with no ping before one relaunch (default 360)",
    )
    parser.add_argument(
        "--ready-timeout",
        type=float,
        default=1800.0,
        help="seconds to wait for the editor to answer a ping (default 1800)",
    )
    parser.add_argument(
        "--run",
        dest="run",
        nargs="+",
        action=_StepAction,
        metavar=("SCRIPT", "TIMEOUT"),
        help="run a script and print its output (timeout default 1500 s); repeatable",
    )
    parser.add_argument(
        "--run-until-done",
        dest="until",
        nargs="+",
        action=_StepAction,
        metavar=("SCRIPT", "DONE"),
        help="run a ticker script, then wait for its done file "
        "(SCRIPT DONE [TIMEOUT], default 3600 s); repeatable",
    )
    parser.add_argument(
        "--export",
        dest="export",
        nargs=1,
        action=_StepAction,
        metavar="GRAPH",
        help="export a PVE graph asset through growpy-pve-export; repeatable",
    )
    parser.set_defaults(steps=[])
    return parser


@dataclass(frozen=True)
class SessionArgs:
    project: Path
    engine: Path
    lock_dir: Path | None
    lock: str | None
    purpose: str
    commit_limit: float
    zen_timeout: float
    ready_timeout: float
    steps: tuple[Step, ...] = field(default=())

    @property
    def editor_log(self) -> Path:
        return self.project.parent / "Saved" / "Logs" / (self.project.stem + ".log")


def parse_args(argv: list[str] | None = None, env=None) -> SessionArgs:
    """Arguments with the environment defaults; exits with a clear message when
    the project or engine is unknown, or ``--lock`` has no lock folder."""
    env = os.environ if env is None else env
    parser = build_parser()
    ns = parser.parse_args(argv)
    project = ns.project or env.get(ENV_PROJECT)
    engine = ns.engine or env.get(ENV_ENGINE)
    lock_dir = ns.lock_dir or env.get(ENV_LOCK_DIR)
    if not project:
        parser.error(
            f"no project: pass --project or set {ENV_PROJECT} to the .uproject"
        )
    if not engine:
        parser.error(
            f"no engine: pass --engine or set {ENV_ENGINE} to UnrealEditor.exe"
        )
    if ns.lock and not lock_dir:
        parser.error(
            f"--lock needs a lock folder: pass --lock-dir or set {ENV_LOCK_DIR}"
        )
    if not str(project).lower().endswith(".uproject") or not Path(project).is_file():
        parser.error(f"project is not an existing .uproject: {project}")
    if not Path(engine).is_file():
        parser.error(f"engine is not an existing UnrealEditor.exe: {engine}")
    return SessionArgs(
        project=Path(project),
        engine=Path(engine),
        lock_dir=Path(lock_dir) if lock_dir else None,
        lock=ns.lock,
        purpose=ns.purpose,
        commit_limit=ns.commit_limit,
        zen_timeout=ns.zen_timeout,
        ready_timeout=ns.ready_timeout,
        steps=tuple(ns.steps),
    )


# ---------------------------------------------------------------------- lock --


class LockRefused(RuntimeError):
    """The editor slot is taken: another lock or a running editor."""


@contextlib.contextmanager
def editor_lock(
    lock_dir: Path,
    name: str,
    purpose: str,
    editors_running: Callable[[], int],
    settle: float = 20.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[Path]:
    """Hold ``lock_dir/<name>.lock`` for the block; always removed afterwards.

    Refused when the folder holds any lock (an existing file of the same name is
    someone's too) or an editor runs. After writing, the folder is checked again
    once ``settle`` seconds later, so two sessions racing for the slot both back off.
    """
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_dir / (name if name.endswith(".lock") else f"{name}.lock")
    held = sorted(p.name for p in lock_dir.iterdir())
    if held:
        raise LockRefused(f"lock folder {lock_dir} holds {', '.join(held)}")
    running = editors_running()
    if running:
        raise LockRefused(f"{running} UnrealEditor process(es) running")
    path.write_text((purpose or f"growpy-ue-session {name}").splitlines()[0] + "\n")
    try:
        sleep(settle)
        others = sorted(p.name for p in lock_dir.iterdir() if p != path)
        if others:
            raise LockRefused(
                f"lock folder {lock_dir} took {', '.join(others)} meanwhile"
            )
        log(f"lock {path.name} held")
        yield path
    finally:
        path.unlink(missing_ok=True)
        log(f"lock {path.name} released")


# ------------------------------------------------------------- restore guard --


def restore_guard(project: Path) -> str:
    """Set ``PackageRestoreData.json`` aside (as ``.aside_<HHMMSS>``) when it would
    show the Restore Packages dialog, which blocks a headless editor start."""
    path = project.parent / "Saved" / "Autosaves" / "PackageRestoreData.json"
    if not path.is_file():
        return "restore data absent"
    raw = path.read_bytes()
    utf16 = raw[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in raw[:8]
    data = json.loads(raw.decode("utf-16") if utf16 else raw.decode("utf-8-sig"))
    if not (data.get("RestoreEnabled") or data.get("Packages")):
        return "restore data clean"
    path.rename(path.with_name(path.name + time.strftime(".aside_%H%M%S")))
    return f"restore data set aside: {len(data.get('Packages', []))} package(s)"


# ------------------------------------------------------------ waits (pure) --


def zen_hung(log_tail: str, elapsed: float, zen_timeout: float) -> bool:
    """True when the editor sits on the Zen splash past ``zen_timeout``: the last
    non-empty log line ends with "Waiting for ZenServer to be ready..."."""
    lines = [line for line in log_tail.splitlines() if line.strip()]
    return (
        elapsed >= zen_timeout
        and bool(lines)
        and lines[-1].rstrip().endswith(ZEN_WAIT_LINE)
    )


def wait_ready(
    ping: Callable[[], bool],
    read_log_tail: Callable[[], str],
    *,
    ready_timeout: float,
    zen_timeout: float,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    poll: float = 20.0,
) -> str:
    """``"ready"`` when a ping answers, ``"zen"`` on the Zen splash hang,
    ``"timeout"`` after ``ready_timeout``."""
    start = clock()
    while True:
        if ping():
            return "ready"
        elapsed = clock() - start
        if zen_hung(read_log_tail(), elapsed, zen_timeout):
            return "zen"
        if elapsed >= ready_timeout:
            return "timeout"
        sleep(poll)


def wait_for_file(
    path: Path,
    timeout: float,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    poll: float = 10.0,
) -> bool:
    """True once ``path`` exists, False after ``timeout`` seconds."""
    start = clock()
    while not path.exists():
        if clock() - start >= timeout:
            return False
        sleep(poll)
    return True


# ------------------------------------------------------------- the editor --


def read_log_tail(path: Path, size: int = 4096) -> str:
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, path.stat().st_size - size))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def launch_editor(engine: Path, project: Path) -> int:
    """Start the editor detached from this process; return its PID."""
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [str(engine), str(project), *LAUNCH_FLAGS],
        cwd=str(project.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    return proc.pid


def pid_alive(pid: int) -> bool:
    import psutil

    try:
        return psutil.Process(pid).is_running()
    except psutil.NoSuchProcess:
        return False


def kill_own_editor(pid: int) -> list[int]:
    """Kill the editor ``pid`` and its CrashReportClient child; nothing else.
    The children are read first: a dead parent has none to find."""
    import psutil

    try:
        editor = psutil.Process(pid)
        crash = [
            c
            for c in editor.children(recursive=True)
            if c.name().lower().startswith("crashreportclient")
        ]
    except psutil.NoSuchProcess:
        return []
    killed = []
    for proc in (editor, *crash):
        with contextlib.suppress(psutil.NoSuchProcess):
            proc.kill()
            killed.append(proc.pid)
    return killed


def editors_running() -> int:
    """UnrealEditor processes running (a count only: never used to kill)."""
    import psutil

    return sum(
        1
        for p in psutil.process_iter(["name"])
        if (p.info.get("name") or "").lower().startswith("unrealeditor")
    )


def commit_percent() -> float:
    """System commit charge in % of the commit limit (Windows), the counter
    PercentCommittedBytesInUse; psutil does not report it, so ctypes reads it."""
    import ctypes
    from ctypes import wintypes

    class _PerfInfo(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("CommitTotal", ctypes.c_size_t),
            ("CommitLimit", ctypes.c_size_t),
            ("CommitPeak", ctypes.c_size_t),
            ("PhysicalTotal", ctypes.c_size_t),
            ("PhysicalAvailable", ctypes.c_size_t),
            ("SystemCache", ctypes.c_size_t),
            ("KernelTotal", ctypes.c_size_t),
            ("KernelPaged", ctypes.c_size_t),
            ("KernelNonpaged", ctypes.c_size_t),
            ("PageSize", ctypes.c_size_t),
            ("HandleCount", wintypes.DWORD),
            ("ProcessCount", wintypes.DWORD),
            ("ThreadCount", wintypes.DWORD),
        ]

    info = _PerfInfo()
    info.cb = ctypes.sizeof(info)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb):
        raise OSError("GetPerformanceInfo failed")
    return 100.0 * info.CommitTotal / info.CommitLimit


class CommitGuard(threading.Thread):
    """Kill only ``pid`` when the commit charge passes ``limit`` %; ends with the
    editor or on ``stop()``."""

    def __init__(
        self,
        pid,
        limit,
        *,
        percent=commit_percent,
        alive=pid_alive,
        kill=kill_own_editor,
        poll=10.0,
    ):
        super().__init__(daemon=True, name=f"commit-guard-{pid}")
        self.pid, self.limit, self.poll = pid, limit, poll
        self._percent, self._alive, self._kill = percent, alive, kill
        self._stop_event = threading.Event()
        self.fired = False

    def run(self) -> None:
        while not self._stop_event.is_set() and self._alive(self.pid):
            pct = self._percent()
            if pct > self.limit:
                self._kill(self.pid)
                self.fired = True
                log(
                    f"KILLED editor {self.pid}: commit {pct:.0f} % > {self.limit:.0f} %"
                )
                return
            self._stop_event.wait(self.poll)

    def stop(self) -> None:
        self._stop_event.set()


# ---------------------------------------------------------------- remote --


def run_source(source: str, timeout: float) -> dict:
    """Run Python source in the editor (``ue_remote.run_file`` on a temp file,
    as growpy-pve-export does)."""
    from growpy.io.unreal import ue_remote

    fd, path = tempfile.mkstemp(prefix="growpy_ue_session_", suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(source)
    try:
        return ue_remote.run_file(path, timeout=timeout)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


def run_script(path: str, timeout: float) -> dict:
    from growpy.io.unreal import ue_remote

    return ue_remote.run_file(path, timeout=timeout)


def ping_editor() -> bool:
    try:
        return bool(run_source(PING_SOURCE, timeout=20).get("success"))
    except (ConnectionError, RuntimeError, OSError):
        return False


def print_result(result: dict) -> bool:
    for line in result.get("output", []):
        text = line.get("output", "") if isinstance(line, dict) else str(line)
        print(text.rstrip(), flush=True)
    ok = bool(result.get("success"))
    print("SUCCESS" if ok else f"FAILED: {result.get('result')}", flush=True)
    return ok


def export_with_pve_export(graphs: list[str], editor_log: Path) -> bool:
    """``growpy-pve-export`` on the graphs, as the session scripts ran it (it
    also rebuilds the catalog print)."""
    from growpy.tools import pve_export

    return pve_export.main([*graphs, "--log", str(editor_log)]) == 0


# ----------------------------------------------------------------- steps --


@dataclass
class Runner:
    """What the steps call; the tests inject fakes."""

    run: Callable[[str, float], dict] = run_script
    export: Callable[[list[str], Path], bool] = export_with_pve_export
    wait_file: Callable[[Path, float], bool] = wait_for_file


def run_steps(steps: tuple[Step, ...], editor_log: Path, runner: Runner) -> bool:
    """The steps in order; adjacent exports as one call; stops at the first failure."""
    i = 0
    while i < len(steps):
        step = steps[i]
        if step.kind == "export":
            graphs = []
            while i < len(steps) and steps[i].kind == "export":
                graphs.append(steps[i].target)
                i += 1
            log(f"export {len(graphs)} graph(s)")
            if not runner.export(graphs, editor_log):
                log("export FAILED")
                return False
            continue
        if step.kind == "until":
            step.done.unlink(
                missing_ok=True
            )  # an old done file would end the wait at once
            log(f"run {step.target}, then wait for {step.done}")
            if not print_result(runner.run(step.target, 120.0)):
                return False
            if not runner.wait_file(step.done, step.timeout):
                log(f"TIMEOUT: no {step.done} after {step.timeout:.0f} s")
                return False
            log(f"done: {step.done}")
        else:
            log(f"run {step.target}")
            if not print_result(runner.run(step.target, step.timeout)):
                return False
        i += 1
    return True


# --------------------------------------------------------------- session --


def _start_editor(args: SessionArgs) -> tuple[int, CommitGuard]:
    pid = launch_editor(args.engine, args.project)
    log(f"editor pid {pid}")
    guard = CommitGuard(pid, args.commit_limit)
    guard.start()
    return pid, guard


def _quit_editor(pid: int) -> None:
    with contextlib.suppress(ConnectionError, RuntimeError, OSError):
        run_source(QUIT_SOURCE, timeout=30)
    if not wait_for_exit(pid):
        kill_own_editor(pid)
        log(f"editor {pid} killed after quit timeout")


def wait_for_exit(pid: int, timeout: float = 120.0) -> bool:
    """True once the editor ``pid`` has exited, within ``timeout`` seconds."""
    deadline = time.monotonic() + timeout
    while pid_alive(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(10.0)
    return True


def session(args: SessionArgs, runner: Runner | None = None) -> bool:
    """Steps 2-7 of the module docstring; the caller holds the lock."""
    runner = runner or Runner()
    # ue_remote pins the editor by project NAME from its own variable
    os.environ[UE_REMOTE_PROJECT] = args.project.stem
    log(restore_guard(args.project))
    pid, guard = _start_editor(args)
    try:
        for attempt in (1, 2):
            state = wait_ready(
                ping_editor,
                lambda: read_log_tail(args.editor_log),
                ready_timeout=args.ready_timeout,
                zen_timeout=args.zen_timeout,
            )
            if state == "zen" and attempt == 1:
                guard.stop()
                log(f"Zen splash hang: killed {kill_own_editor(pid)}, relaunching once")
                pid, guard = _start_editor(args)
                continue
            break
        if state != "ready":
            log(f"editor not ready ({state})")
            return False
        log("editor ready")
        return run_steps(args.steps, args.editor_log, runner)
    finally:
        _quit_editor(pid)
        guard.stop()
        log(restore_guard(args.project))
        with contextlib.suppress(Exception):
            log(f"session end; commit {commit_percent():.0f} %")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        import psutil  # noqa: F401
    except ImportError:
        print(
            "growpy-ue-session needs psutil (pip install growpy[monitor])",
            file=sys.stderr,
        )
        return 1
    log(f"session start: {len(args.steps)} step(s), project {args.project.name}")
    try:
        if args.lock:
            with editor_lock(args.lock_dir, args.lock, args.purpose, editors_running):
                ok = session(args)
        else:
            ok = session(args)
    except LockRefused as err:
        log(f"refused: {err}")
        return 3
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
