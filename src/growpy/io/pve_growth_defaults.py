"""
Default growth parameters for PVE presets.

Extracted from Quixel Megaplants Broadleaf Hazel reference to ensure
PVE presets work correctly in Unreal Engine while we implement proper
extraction from Grove .seed.json files.
"""

from typing import Any, Dict


def get_hazel_growth_defaults() -> Dict[str, Any]:
    """
    Get default growth parameters from Hazel reference.

    These are working values from a real Megaplants preset that can be used
    as fallbacks or defaults for any broadleaf species.

    Returns:
        Dictionary with growth parameter curves and values
    """
    return {
        # REQUIRED by Unreal C++ validation
        "phyllotaxyLeaf": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [
                0.0,
                198.39999389648438,
                51.630001068115234,
                1.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                2.0,
                2.0,
                0.05469999834895134,
            ],
        },
        # Growth curves
        "phototropism": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [
                0.24650000035762787,
                0.6690999865531921,
                0.46709999442100525,
                0.4977000057697296,
            ],
        },
        "phototropismChild": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [
                0.18629999458789825,
                0.37529999017715454,
                0.16590000689029694,
                0.16869999468326569,
            ],
        },
        "phyllotaxy": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [
                0.0,
                202.6999969482422,
                50.209999084472656,
                1.0,
                1.0,
                0.0,
                60.0,
                0.0,
                0.0,
                0.0,
                0.0,
                2.0,
                2.0,
                0.21960000693798065,
            ],
        },
        "phyllotaxyChild": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [
                0.0,
                198.39999389648438,
                51.630001068115234,
                1.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                2.0,
                2.0,
                0.05469999834895134,
            ],
        },
        "axialElongation": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [0.25, 0.0, 0.48190000653266907, 0.0, 0.0, 1.0],
        },
        "axialElongationChild": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [0.25, 0.0, 0.48190000653266907, 0.0, 0.0, 1.0],
        },
        "lateralElongation": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [0.17419999837875366, 0.0, 0.3652999997138977, 0.0, 0.0, 1.0],
        },
        "lateralElongationChild": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [0.1280000060796738, 0.0, 0.30000001192092896, 0.0, 0.0, 1.0],
        },
        "branchingCondition": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [0.0, 0.0, 0.0, 1.0, 0.11999999731779099, 1.0],
        },
        "branchingConditionChild": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        },
        "trunkGrowth": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [1.0, 0.0, 0.9382486343383789, 0.0, 0.0, 1.0],
        },
        "leafGrowth": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
        },
        "lightDetection": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        },
        "randomAngle": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        },
        "randomAngleChild": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        },
        "guide": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        },
        "abscissionSenescense": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [
                0.14829999208450317,
                36.0,
                1.0,
                5.0,
                0.0,
                0.4523000121116638,
                6.0,
                11.0,
                0.0,
            ],
        },
        # Scale parameters
        "maxDavinciPscales": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [
                0.12818339467048645,
                0.09680811315774918,
                0.1252952516078949,
                0.10661862790584564,
                0.25942081212997437,
                0.0500965379178524,
                0.12358713150024414,
                0.034325409680604935,
                0.11173060536384583,
                0.0881328210234642,
            ],
        },
        "maxPscales": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [
                0.028879253193736076,
                0.021759208291769028,
                0.041752081364393234,
                0.02884751558303833,
                0.030671710148453712,
                0.021017035469412804,
                0.03420468047261238,
                0.02320578508079052,
                0.026102518662810326,
                0.02909449301660061,
                0.01879052072763443,
                0.02581917680799961,
                0.01730617694556713,
                0.022400157526135445,
                0.02027486450970173,
            ],
        },
    }


def get_default_growth_params(use_hazel_defaults: bool = True) -> Dict[str, Any]:
    """
    Get default growth parameters for PVE preset generation.

    Args:
        use_hazel_defaults: If True, use Hazel reference values.
                           If False, use minimal defaults.

    Returns:
        Dictionary with growth parameters
    """
    if use_hazel_defaults:
        return get_hazel_growth_defaults()

    # Minimal defaults - just the required field
    return {
        "phyllotaxyLeaf": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": [
                0.0,
                137.5,
                50.0,
                1.0,
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                2.0,
                2.0,
                0.0,
            ],
        }
    }


def merge_growth_params(
    defaults: Dict[str, Any], overrides: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Merge default growth parameters with optional overrides.

    Args:
        defaults: Default growth parameters
        overrides: Optional dictionary to override specific parameters

    Returns:
        Merged parameters dictionary
    """
    import copy

    result = copy.deepcopy(defaults)

    if overrides:
        for key, value in overrides.items():
            if key in result:
                # Merge values, preserving structure
                if isinstance(value, dict) and "value" in value:
                    result[key]["value"] = value["value"]
                else:
                    result[key] = value
            else:
                result[key] = value

    return result
