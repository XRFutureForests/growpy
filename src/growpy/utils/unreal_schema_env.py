import os
from pathlib import Path

_CONFIGURED = False


def configure_unreal_usd_plugin_path(custom_dir: str | None = None) -> None:
    """Ensure Unreal's USD schema is on PXR_PLUGINPATH_NAME before importing pxr.

    - Resolves project root from this file location.
    - Defaults to `data/unreal_schema/mac` unless `custom_dir` provided.
    - Idempotent: won't duplicate entries across repeated calls.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    try:
        # Allow explicit override
        plugin_dir = Path(custom_dir) if custom_dir else None

        if not plugin_dir:
            # Derive repo root: src/growpy/utils/unreal_schema_env.py -> repo root is parents[3]
            repo_root = Path(__file__).resolve().parents[3]
            # Default to mac schema folder for this workspace; caller may override per-OS
            plugin_dir = repo_root / "data" / "unreal_schema" / "mac"

        plugin_dir = plugin_dir.resolve()
        if not plugin_dir.exists():
            # Nothing to do if schema folder is missing
            return

        sep = os.pathsep
        current = os.environ.get("PXR_PLUGINPATH_NAME", "")

        # Prepend if not already present (split handles duplicates robustly)
        paths = [p for p in current.split(sep) if p]
        if str(plugin_dir) not in paths:
            new_value = (
                str(plugin_dir) if not current else f"{plugin_dir}{sep}{current}"
            )
            os.environ["PXR_PLUGINPATH_NAME"] = new_value
    finally:
        _CONFIGURED = True
