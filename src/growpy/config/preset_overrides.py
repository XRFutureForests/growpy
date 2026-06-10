"""Preset override system for dynamic parameter adjustment during simulation.

Allows modifying Grove preset parameters at runtime, including:
- Static overrides: Replace preset values with fixed values
- Cycle-based interpolation: Smoothly transition values over growth cycles
- JSON-defined curves: Species-specific curves defined in seed.json files

This addresses the issue where trees "die" at high cycle counts due to
aggressive drop_decay, drop_weak, or other pruning parameters.

JSON Curve Format (in seed.json files):
    Add a "_curve" suffix to any parameter to define cycle-based interpolation:

    {
        "drop_decay": 0.3,
        "drop_decay_curve": {
            "start": 0.0,
            "end": 0.3,
            "easing": "ease_in"
        },
        ...
    }

    The curve will interpolate from "start" to "end" over the simulation.
    If no curve is defined, the static value is used throughout.

    Easing options: "linear", "ease_in", "ease_out", "ease_in_out"

CLI Usage (overrides JSON settings):
    from growpy.config.preset_overrides import PresetOverrides

    # Static override: always use this value
    overrides.add_static("drop_decay", 0.1)

    # Interpolated override: transition from start to end over simulation
    overrides.add_interpolated("drop_weak", start=0.3, end=0.05)

    # Apply to grove at a specific cycle
    overrides.apply_to_grove(grove, current_cycle=5, total_cycles=10)
"""

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Grove Properties parameters that require int type (not float)
INT_PARAMS = {
    "add_side_branches",
    "add_bud_life",
    "grow_nodes",
    "shade_alongside",
    "twig_longevity",
    "twig_wither",
    "sow_age",
    "sow_limit",
}


@dataclass
class StaticOverride:
    """A static preset override that uses a fixed value."""

    param: str
    value: float


@dataclass
class InterpolatedOverride:
    """An interpolated preset override that transitions between values.

    Easing Functions:
        linear:      Constant rate of change
        ease_in:     Starts slow, accelerates (power curve: t^power)
        ease_out:    Starts fast, decelerates (inverse power curve)
        ease_in_out: Smooth S-curve with controllable midpoint

    Power Parameter:
        Controls curve steepness. Default is 2.0 (quadratic).
        - power=1.0: Linear (no easing effect)
        - power=2.0: Quadratic (default, gentle curve)
        - power=3.0: Cubic (steeper curve)
        - power=4.0+: Very steep, almost step-like

    Absolute Cycle Parameters (take precedence over relative parameters):
        midpoint_cycle:    Absolute cycle for ease_in_out inflection point
        transition_cycle:  Absolute cycle where ease_in/ease_out reaches 50% transition

    Relative Parameters (used if absolute not specified):
        midpoint: Relative position (0.0-1.0) for ease_in_out inflection
    """

    param: str
    start: float
    end: float
    easing: str = "linear"  # linear, ease_in, ease_out, ease_in_out
    power: float = 2.0  # Curve steepness (1.0=linear, 2.0=quadratic, 3.0=cubic)
    midpoint: float = 0.5  # Relative inflection point for ease_in_out (0.0-1.0)
    midpoint_cycle: int | None = None  # Absolute cycle for ease_in_out inflection
    transition_cycle: int | None = (
        None  # Absolute cycle for ease_in/ease_out 50% point
    )


@dataclass
class CycleArrayOverride:
    """A per-cycle override with explicit values for each cycle.

    Used for yield-table calibration where grow_length (or other parameters)
    needs arbitrary per-cycle values that don't fit a simple easing curve.

    If the simulation runs more cycles than values provided, the last value
    is repeated. If fewer, extra values are ignored.
    """

    param: str
    values: list[float]


@dataclass
class PresetOverrides:
    """Container for preset overrides applied during simulation.

    Supports three types of overrides:
    - Static: Fixed value replacement
    - Interpolated: Value transitions over growth cycles (easing curves)
    - Cycle arrays: Explicit per-cycle values (from yield table calibration)

    Attributes:
        static_overrides: Dict of param -> value for static overrides
        interpolated_overrides: List of InterpolatedOverride for cycle-based values
        cycle_array_overrides: List of CycleArrayOverride for per-cycle values
    """

    static_overrides: dict[str, float] = field(default_factory=dict)
    interpolated_overrides: list[InterpolatedOverride] = field(default_factory=list)
    cycle_array_overrides: list[CycleArrayOverride] = field(default_factory=list)
    # Memoized lookup table: {total_cycles: [overrides_at_cycle_0, ..., overrides_at_cycle_N]}
    _lookup_table: dict[int, list[dict[str, float]]] = field(
        default_factory=dict, compare=False, repr=False
    )

    def add_static(self, param: str, value: float) -> "PresetOverrides":
        """Add a static override.

        Args:
            param: Preset parameter name (e.g., 'drop_decay')
            value: Fixed value to use

        Returns:
            Self for chaining
        """
        self.static_overrides[param] = value
        self._lookup_table.clear()  # Invalidate cache
        return self

    def add_interpolated(
        self,
        param: str,
        start: float,
        end: float,
        easing: str = "linear",
    ) -> "PresetOverrides":
        """Add an interpolated override that changes over cycles.

        Args:
            param: Preset parameter name (e.g., 'drop_decay')
            start: Value at cycle 0
            end: Value at final cycle
            easing: Interpolation type ('linear', 'ease_in', 'ease_out', 'ease_in_out')

        Returns:
            Self for chaining
        """
        self.interpolated_overrides.append(
            InterpolatedOverride(param=param, start=start, end=end, easing=easing)
        )
        self._lookup_table.clear()  # Invalidate cache
        return self

    def get_value_at_cycle(
        self,
        override: InterpolatedOverride,
        current_cycle: int,
        total_cycles: int,
    ) -> float:
        """Calculate interpolated value at a specific cycle.

        Args:
            override: The interpolated override
            current_cycle: Current simulation cycle (0-indexed)
            total_cycles: Total number of cycles

        Returns:
            Interpolated value for the current cycle
        """
        if total_cycles <= 1:
            return override.end

        t = current_cycle / (total_cycles - 1)
        t = max(0.0, min(1.0, t))

        power = override.power

        # Calculate effective midpoint (absolute cycle takes precedence)
        if override.midpoint_cycle is not None and total_cycles > 1:
            midpoint = override.midpoint_cycle / (total_cycles - 1)
            midpoint = max(0.01, min(0.99, midpoint))  # Clamp to valid range
        else:
            midpoint = override.midpoint

        # Calculate transition point for ease_in/ease_out (absolute cycle takes precedence)
        if override.transition_cycle is not None and total_cycles > 1:
            transition_point = override.transition_cycle / (total_cycles - 1)
            transition_point = max(0.01, min(0.99, transition_point))
        else:
            transition_point = None  # Use default behavior

        if override.easing == "ease_in":
            # Power curve: starts slow, accelerates
            if transition_point is not None:
                # Adjust power so that at transition_point, we're at 50% of the transition
                # For t^p = 0.5 at t=transition_point: p = log(0.5) / log(transition_point)
                if transition_point > 0 and transition_point < 1:
                    power = -0.693147 / (
                        -0.000001
                        if transition_point >= 1
                        else (
                            max(
                                -10,
                                min(
                                    -0.1,
                                    (
                                        -abs(1 / (1 - transition_point))
                                        if transition_point > 0.5
                                        else -1
                                    ),
                                ),
                            )
                            if transition_point >= 0.5
                            else max(0.1, min(10, abs(1 / transition_point)))
                        )
                    )
                    # Simplified: calculate power from transition_point
                    if 0 < transition_point < 1:
                        power = math.log(0.5) / math.log(transition_point)
                        power = max(0.5, min(10.0, power))  # Clamp to reasonable range
            t = t**power

        elif override.easing == "ease_out":
            # Inverse power curve: starts fast, decelerates
            if transition_point is not None:
                # Adjust power so that at transition_point, we're at 50% of the transition
                # For 1-(1-t)^p = 0.5 at t=transition_point: (1-t)^p = 0.5
                # p = log(0.5) / log(1-transition_point)
                if 0 < transition_point < 1:
                    power = math.log(0.5) / math.log(1 - transition_point)
                    power = max(0.5, min(10.0, power))  # Clamp to reasonable range
            t = 1 - (1 - t) ** power

        elif override.easing == "ease_in_out":
            # Asymmetric S-curve with controllable midpoint
            # Uses smoothstep with adjustable inflection point
            if midpoint <= 0.0 or midpoint >= 1.0:
                midpoint = 0.5

            if t < midpoint:
                # First half: ease_in portion
                t_normalized = t / midpoint
                t = midpoint * (t_normalized**power)
            else:
                # Second half: ease_out portion
                t_normalized = (t - midpoint) / (1.0 - midpoint)
                t = midpoint + (1.0 - midpoint) * (1 - (1 - t_normalized) ** power)

        return override.start + (override.end - override.start) * t

    def add_cycle_array(
        self, param: str, values: list[float]
    ) -> "PresetOverrides":
        """Add a per-cycle array override (e.g., from yield table calibration).

        Args:
            param: Preset parameter name (e.g., 'grow_length')
            values: List of values, one per cycle

        Returns:
            Self for chaining
        """
        self.cycle_array_overrides.append(
            CycleArrayOverride(param=param, values=values)
        )
        self._lookup_table.clear()
        return self

    def get_all_overrides_at_cycle(
        self,
        current_cycle: int,
        total_cycles: int,
    ) -> dict[str, float]:
        """Get all override values for a specific cycle.

        Results are memoized per total_cycles to avoid recomputing easing math
        on every call during the simulation inner loop.

        Priority (last wins): static < interpolated < cycle_array

        Args:
            current_cycle: Current simulation cycle
            total_cycles: Total number of cycles

        Returns:
            Dict of param -> value for all overrides at this cycle
        """
        if not self.interpolated_overrides and not self.cycle_array_overrides:
            return dict(self.static_overrides)

        # Build lookup table for this total_cycles value if not cached
        if total_cycles not in self._lookup_table:
            table = []
            for c in range(total_cycles):
                entry = dict(self.static_overrides)
                for override in self.interpolated_overrides:
                    entry[override.param] = self.get_value_at_cycle(override, c, total_cycles)
                for arr_override in self.cycle_array_overrides:
                    idx = min(c, len(arr_override.values) - 1)
                    entry[arr_override.param] = arr_override.values[idx]
                table.append(entry)
            self._lookup_table[total_cycles] = table

        idx = max(0, min(current_cycle, total_cycles - 1))
        return self._lookup_table[total_cycles][idx]

    def apply_to_grove(
        self,
        grove: Any,
        current_cycle: int,
        total_cycles: int,
    ) -> None:
        """Apply overrides to a grove at a specific cycle.

        Args:
            grove: Grove instance (gc.Grove)
            current_cycle: Current simulation cycle
            total_cycles: Total number of cycles
        """
        overrides = self.get_all_overrides_at_cycle(current_cycle, total_cycles)

        if not overrides:
            return

        props = grove.get_properties()
        for param, value in overrides.items():
            if hasattr(props, param):
                # Cast to int for parameters that require it
                if param in INT_PARAMS:
                    value = int(value)
                setattr(props, param, value)
        grove.set_properties(props)

    def is_empty(self) -> bool:
        """Check if any overrides are defined."""
        return (
            not self.static_overrides
            and not self.interpolated_overrides
            and not self.cycle_array_overrides
        )


def parse_override_arg(arg: str) -> tuple[str, float]:
    """Parse a static override argument.

    Args:
        arg: String in format 'param=value' (e.g., 'drop_decay=0.1')

    Returns:
        Tuple of (param_name, value)

    Raises:
        ValueError: If format is invalid
    """
    if "=" not in arg:
        raise ValueError(f"Invalid override format: '{arg}'. Expected 'param=value'")

    param, value_str = arg.split("=", 1)
    try:
        value = float(value_str)
    except ValueError:
        raise ValueError(f"Invalid value '{value_str}' for parameter '{param}'")

    return param.strip(), value


def parse_curve_arg(arg: str) -> tuple[str, float, float, str]:
    """Parse an interpolated override argument.

    Args:
        arg: String in format 'param=start:end' or 'param=start:end:easing'
             Examples: 'drop_decay=0.3:0.1' or 'drop_decay=0.3:0.1:ease_out'

    Returns:
        Tuple of (param_name, start, end, easing)

    Raises:
        ValueError: If format is invalid
    """
    if "=" not in arg:
        raise ValueError(f"Invalid curve format: '{arg}'. Expected 'param=start:end'")

    param, value_str = arg.split("=", 1)
    parts = value_str.split(":")

    if len(parts) < 2:
        raise ValueError(
            f"Invalid curve format: '{arg}'. Expected 'param=start:end[:easing]'"
        )

    try:
        start = float(parts[0])
        end = float(parts[1])
    except ValueError:
        raise ValueError(f"Invalid numeric values in curve: '{arg}'")

    easing = parts[2] if len(parts) > 2 else "linear"
    valid_easings = ["linear", "ease_in", "ease_out", "ease_in_out"]
    if easing not in valid_easings:
        raise ValueError(f"Invalid easing '{easing}'. Choose from: {valid_easings}")

    return param.strip(), start, end, easing


def create_overrides_from_args(
    static_args: list[str] | None = None,
    curve_args: list[str] | None = None,
) -> PresetOverrides:
    """Create PresetOverrides from CLI arguments.

    Args:
        static_args: List of static overrides (e.g., ['drop_decay=0.1'])
        curve_args: List of curve overrides (e.g., ['drop_decay=0.3:0.1'])

    Returns:
        Configured PresetOverrides instance
    """
    overrides = PresetOverrides()

    if static_args:
        for arg in static_args:
            param, value = parse_override_arg(arg)
            overrides.add_static(param, value)

    if curve_args:
        for arg in curve_args:
            param, start, end, easing = parse_curve_arg(arg)
            overrides.add_interpolated(param, start, end, easing)

    return overrides


def load_curves_from_preset(preset_path: Path) -> PresetOverrides:
    """Load curve definitions from a seed.json preset file.

    Looks for fields ending in "_curve" that define interpolated values.

    Basic example in seed.json:
        {
            "drop_decay": 0.3,
            "drop_decay_curve": {
                "start": 0.0,
                "end": 0.3,
                "easing": "ease_in"
            }
        }

    Advanced example with power and midpoint:
        {
            "drop_decay": 0.3,
            "drop_decay_curve": {
                "start": 0.0,
                "end": 0.3,
                "easing": "ease_in_out",
                "power": 3.0,
                "midpoint": 0.7
            }
        }

    Args:
        preset_path: Path to the seed.json file

    Returns:
        PresetOverrides with curves from the preset
    """
    overrides = PresetOverrides()

    if not preset_path.exists():
        return overrides

    with open(preset_path) as f:
        preset_data = json.load(f)

    for key, value in preset_data.items():
        if key.endswith("_curve") and isinstance(value, dict):
            param = key[:-6]  # Remove "_curve" suffix
            start = value.get("start", 0.0)
            end = value.get("end", preset_data.get(param, 0.0))
            easing = value.get("easing", "linear")
            power = value.get("power", 2.0)
            midpoint = value.get("midpoint", 0.5)
            midpoint_cycle = value.get("midpoint_cycle", None)
            transition_cycle = value.get("transition_cycle", None)

            valid_easings = ["linear", "ease_in", "ease_out", "ease_in_out"]
            if easing not in valid_easings:
                easing = "linear"

            overrides.interpolated_overrides.append(
                InterpolatedOverride(
                    param=param,
                    start=start,
                    end=end,
                    easing=easing,
                    power=power,
                    midpoint=midpoint,
                    midpoint_cycle=midpoint_cycle,
                    transition_cycle=transition_cycle,
                )
            )

    # Load yield table calibration data (per-cycle arrays + static overrides)
    calibration = preset_data.get("_yield_table_calibration")
    if calibration and isinstance(calibration, dict):
        grow_length_per_cycle = calibration.get("grow_length_per_cycle")
        if grow_length_per_cycle and isinstance(grow_length_per_cycle, list):
            # Enforce survival floor: grow_length below 50% of base kills
            # some trees depending on random seed (Grove engine limitation).
            base_gl = preset_data.get("grow_length", 0.3)
            floor = base_gl * 0.5
            grow_length_per_cycle = [max(v, floor) for v in grow_length_per_cycle]
            overrides.cycle_array_overrides.append(
                CycleArrayOverride(param="grow_length", values=grow_length_per_cycle)
            )
        # Load static calibration overrides (e.g. thicken_base_scale)
        static_cal = calibration.get("static_overrides")
        if static_cal and isinstance(static_cal, dict):
            for param, value in static_cal.items():
                overrides.static_overrides[param] = value

    return overrides


def load_target_dbh_from_preset(preset_path: Path) -> list[float]:
    """Load target DBH per cycle from yield table calibration in a seed.json.

    Used at export time to compute radial scale for stem mesh correction.
    Prefer load_height_dbh_model_from_preset() for height-driven DBH prediction.

    Args:
        preset_path: Path to the seed.json file

    Returns:
        List of target DBH values (meters) per cycle, or empty list if none
    """
    if not preset_path.exists():
        return []

    with open(preset_path) as f:
        preset_data = json.load(f)

    calibration = preset_data.get("_yield_table_calibration")
    if calibration and isinstance(calibration, dict):
        target_dbh = calibration.get("target_dbh_per_cycle")
        if target_dbh and isinstance(target_dbh, list):
            return target_dbh
    return []


def load_height_dbh_model_from_preset(
    preset_path: Path,
) -> dict[str, float] | None:
    """Load height-DBH allometric model from yield table calibration in a seed.json.

    The model is a power function DBH(cm) = a * H(m)^b fitted from the yield
    table's height/DBH relationship. This is preferred over the age-indexed
    target_dbh_per_cycle because it uses actual tree height (accurate after
    calibration) rather than age alignment via flushes_per_year.

    Args:
        preset_path: Path to the seed.json file

    Returns:
        Dict with 'a', 'b' power model coefficients, or None if not available.
    """
    if not preset_path.exists():
        return None

    with open(preset_path) as f:
        preset_data = json.load(f)

    calibration = preset_data.get("_yield_table_calibration")
    if calibration and isinstance(calibration, dict):
        model = calibration.get("height_dbh_model")
        if model and isinstance(model, dict) and "a" in model and "b" in model:
            return model
    return None


def predict_dbh_from_height_model(
    height_m: float,
    model: dict[str, float],
) -> float:
    """Predict DBH in meters from height using the allometric power model.

    Args:
        height_m: Tree height in meters.
        model: Dict with 'a' and 'b' coefficients (DBH_m = a * H_m^b).

    Returns:
        Predicted DBH in meters.
    """
    if height_m <= 0:
        return 0.0
    dbh_m = model["a"] * (height_m ** model["b"])
    return max(0.0, dbh_m)


def get_species_overrides(species_name: str) -> PresetOverrides:
    """Get preset overrides for a species from its seed.json file.

    Args:
        species_name: Species name (e.g., "Silver Fir")

    Returns:
        PresetOverrides loaded from the species preset, or empty if none defined
    """
    from . import get_config

    config = get_config()
    try:
        preset_path = config.get_preset_path(species_name)
        return load_curves_from_preset(preset_path)
    except Exception:
        logger.warning("Failed to load preset overrides for %s", species_name)
        return PresetOverrides()


# Common presets for longevity issues
LONGEVITY_OVERRIDES = PresetOverrides(
    static_overrides={
        "drop_decay": 0.1,
        "drop_weak": 0.1,
        "drop_shaded": 0.0,
        "drop_obsolete": 0.0,
    }
)

GRADUAL_DECAY_OVERRIDES = PresetOverrides(
    interpolated_overrides=[
        InterpolatedOverride(param="drop_decay", start=0.0, end=0.3, easing="ease_in"),
        InterpolatedOverride(param="drop_weak", start=0.0, end=0.3, easing="ease_in"),
    ]
)
