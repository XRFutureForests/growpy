"""Shared GPU VRAM and system RAM monitoring helpers.

Single source of truth for resource queries used by both:
- ``growpy.tools.ue_exec`` (orchestrator-side, live Python)
- ``growpy.io.unreal.unreal_scripts`` (UE-embedded preamble generation)

The pure functions here (``query_gpu_vram``, ``query_system_ram``,
``format_resource_bar``) have no side effects and are safe to call from
any Python context. Callers that need logging or waiting behaviour
compose these primitives themselves.
"""

from __future__ import annotations

import subprocess


def query_gpu_vram() -> tuple[int, int, float] | None:
    """Query GPU VRAM usage via nvidia-smi.

    Returns:
        ``(used_mb, total_mb, percent)`` or ``None`` if nvidia-smi is
        unavailable or fails.
    """
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
            pct = round(used / total * 100, 1) if total > 0 else 0.0
            return (used, total, pct)
    except Exception:
        pass
    return None


def query_system_ram() -> tuple[int, int, float] | None:
    """Query system RAM usage.

    Returns:
        ``(used_mb, total_mb, percent)`` or ``None`` if neither psutil
        nor the Windows wmic fallback is available.
    """
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
            vals: dict[str, int] = {}
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


def format_resource_bar(pct: float, width: int = 20) -> str:
    """Format a percentage as a fixed-width ASCII bar (e.g. ``#####---------------``)."""
    filled = int(width * pct / 100)
    return "#" * filled + "-" * (width - filled)


def vram_over_limit(pct: float, limit_percent: float) -> bool:
    """Return True if VRAM usage ``pct`` is at or above ``limit_percent``."""
    return limit_percent > 0 and pct >= limit_percent
