"""VRAM/RSS monitor preamble for UE-embedded batch import scripts.

This module owns the self-contained Python snippet that gets injected into
generated Unreal Engine batch scripts. The preamble runs inside UE's Python
(where psutil is unavailable), so it uses Win32 ctypes directly for RSS
monitoring and nvidia-smi for GPU VRAM.

Extracted from ``unreal_scripts.py`` to keep the script generator focused
on import logic rather than embedding a 200-line string literal.
"""

import logging

logger = logging.getLogger(__name__)


def get_vram_monitor_preamble() -> str:
    """Return the VRAM/RSS monitor preamble with RSS_LIMIT_GB auto-filled.

    Computes the UE working-set budget as 90% of total system RAM at
    generation time; falls back to 28 GB if psutil is unavailable.
    """
    try:
        import psutil

        rss_limit = round(psutil.virtual_memory().total / (1024**3) * 0.90, 1)
    except Exception:
        rss_limit = 28.0
    return _VRAM_MONITOR_PREAMBLE.replace("__RSS_LIMIT_GB__", f"{rss_limit}")


# Snippet injected into batch scripts for GPU VRAM monitoring via nvidia-smi
# and UE process RSS monitoring via Win32 psapi (psutil is not available in UE
# Python). Returns (used_mb, total_mb, percent) or None if unavailable.
_VRAM_MONITOR_PREAMBLE = '''
import subprocess
import ctypes
from ctypes import wintypes

# VRAM threshold: pause import when usage exceeds this percentage
# Set high (95%) because the orchestrator handles cleanup between batches at a lower threshold.
VRAM_LIMIT_PERCENT = 95

# Working-set budget in GB. Compared against WorkingSetSize (actual physical
# pages owned by UE), NOT PrivateUsage (committed virtual memory which can
# safely exceed physical RAM via the page file). Value auto-computed at
# generation time as 90% of total system RAM (see get_vram_monitor_preamble).
RSS_LIMIT_GB = __RSS_LIMIT_GB__


class _PMC(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


try:
    _kernel32 = ctypes.WinDLL("kernel32")
    _psapi = ctypes.WinDLL("psapi")
    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    _psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
    _psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    _HAVE_WIN32_MEM = True
except Exception:
    _HAVE_WIN32_MEM = False


def _get_proc_rss():
    """Return (working_set_gb, private_gb) for the current UE process."""
    if not _HAVE_WIN32_MEM:
        return None
    pmc = _PMC()
    pmc.cb = ctypes.sizeof(_PMC)
    if _psapi.GetProcessMemoryInfo(_kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
        return (pmc.WorkingSetSize / 1e9, pmc.PrivateUsage / 1e9)
    return None


def _log_rss(tag):
    info = _get_proc_rss()
    if info is None:
        return 0.0
    ws, pv = info
    print(f"  [RSS {tag}] ws={ws:.2f}GB private={pv:.2f}GB (limit {RSS_LIMIT_GB:.1f}GB)")
    return ws

# Maximum time (seconds) to wait for VRAM to drop below threshold before giving up
VRAM_WAIT_TIMEOUT = 300

# Polling interval (seconds) when waiting for VRAM to settle
VRAM_POLL_INTERVAL = 15

def _get_gpu_vram():
    """Query GPU VRAM usage via nvidia-smi. Returns (used_mb, total_mb, pct) or None."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits", "--id=0"],
            capture_output=True, text=True, timeout=5,
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

def _vram_bar(pct):
    bar_len = 20
    filled = int(bar_len * pct / 100)
    return "#" * filled + "-" * (bar_len - filled)

def _check_vram(context=""):
    """Print VRAM usage and return True if over limit."""
    info = _get_gpu_vram()
    if info is None:
        return False
    used, total, pct = info
    status = f"  [VRAM] {used}/{total} MB ({pct}%) [{_vram_bar(pct)}]"
    if context:
        status += f"  ({context})"
    print(status)
    if VRAM_LIMIT_PERCENT > 0 and pct >= VRAM_LIMIT_PERCENT:
        return True
    return False

def _wait_for_vram(context="", min_delay=5.0):
    """Wait for VRAM to drop below threshold before continuing.

    Always waits at least min_delay seconds. If VRAM is over the limit,
    polls every VRAM_POLL_INTERVAL seconds until it drops below threshold
    or VRAM_WAIT_TIMEOUT is reached.

    Returns True if VRAM settled below threshold, False if timed out.
    """
    time.sleep(min_delay)
    info = _get_gpu_vram()
    if info is None:
        return True
    used, total, pct = info
    if VRAM_LIMIT_PERCENT <= 0 or pct < VRAM_LIMIT_PERCENT:
        print(f"  [VRAM] {used}/{total} MB ({pct}%) [{_vram_bar(pct)}]  ({context})")
        return True

    print(f"  [VRAM] {used}/{total} MB ({pct}%) [{_vram_bar(pct)}]  ({context})")
    print(f"  -- VRAM {pct}% >= {VRAM_LIMIT_PERCENT}% threshold, pausing until it settles...")
    waited = 0.0
    while waited < VRAM_WAIT_TIMEOUT:
        time.sleep(VRAM_POLL_INTERVAL)
        waited += VRAM_POLL_INTERVAL
        info = _get_gpu_vram()
        if info is None:
            return True
        used, total, pct = info
        mins = int(waited // 60)
        secs = int(waited % 60)
        print(f"  [VRAM] {used}/{total} MB ({pct}%) [{_vram_bar(pct)}]  (waited {mins}m{secs:02d}s)")
        if pct < VRAM_LIMIT_PERCENT:
            print(f"  -- VRAM settled below {VRAM_LIMIT_PERCENT}%, continuing")
            return True

    print(f"  ** VRAM still {pct}% after {int(VRAM_WAIT_TIMEOUT)}s timeout -- proceeding anyway **")
    print(f"  ** Per-file tracking ensures progress is safe even if UE crashes **")
    return True
'''
