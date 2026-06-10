"""
PVE Preset JSON schema definition.

Extracted from Quixel Megaplants format - defines structure and data types only,
not actual values. This serves as the lightweight template for PVE generation.
"""

from typing import Any


def get_pve_schema() -> dict[str, Any]:
    """
    Get the PVE preset JSON schema structure.

    This is extracted from reference files like Broadleaf_Hazel_01.json
    but contains only the structure and data type information, not actual values.

    Returns:
        Dictionary defining PVE preset structure with empty value arrays
    """
    return {
        "globalAttributes": {
            # Simulation parameters
            "cycle": {"isArray": False, "size": 1, "type": "int"},
            "cycleTime": {"isArray": False, "size": 1, "type": "float"},
            "randomSeed": {"isArray": False, "size": 1, "type": "int"},
            # Growth parameters (curves)
            "abscissionSenescense": {"isArray": True, "size": 1, "type": "float"},
            "axialElongation": {"isArray": True, "size": 1, "type": "float"},
            "axialElongationChild": {"isArray": True, "size": 1, "type": "float"},
            "branchingCondition": {"isArray": True, "size": 1, "type": "float"},
            "branchingConditionChild": {"isArray": True, "size": 1, "type": "float"},
            "lateralElongation": {"isArray": True, "size": 1, "type": "float"},
            "lateralElongationChild": {"isArray": True, "size": 1, "type": "float"},
            # Physical parameters
            "gravitationalForce": {"isArray": False, "size": 1, "type": "float"},
            "guide": {"isArray": True, "size": 1, "type": "float"},
            # Branch/bud limits
            "compoundMaxBranchGeneration": {"isArray": False, "size": 1, "type": "int"},
            "compoundMaxBranchNumber": {"isArray": False, "size": 1, "type": "int"},
            "maxBranchNumber": {"isArray": False, "size": 1, "type": "int"},
            "maxBudNumber": {"isArray": False, "size": 1, "type": "int"},
            # Leaf parameters
            "leafGrowth": {"isArray": True, "size": 1, "type": "float"},
            "lightDetection": {"isArray": True, "size": 1, "type": "float"},
            # Scale parameters
            "maxDavinciPscales": {"isArray": True, "size": 1, "type": "float"},
            "maxGenerations": {"isArray": False, "size": 1, "type": "int"},
            "maxPscale": {"isArray": False, "size": 1, "type": "float"},
            "maxPscales": {"isArray": True, "size": 1, "type": "float"},
            "max_curve_length": {"isArray": False, "size": 1, "type": "float"},
            "max_pscale": {"isArray": False, "size": 1, "type": "float"},
            "minPscale": {"isArray": False, "size": 1, "type": "float"},
            "photogrammetryTrunk": {"isArray": False, "size": 1, "type": "int"},
            # Phototropism / phyllotaxy / angle curves
            "phototropism": {"isArray": True, "size": 1, "type": "float"},
            "phototropismChild": {"isArray": True, "size": 1, "type": "float"},
            "phyllotaxy": {"isArray": True, "size": 1, "type": "float"},
            "phyllotaxyChild": {"isArray": True, "size": 1, "type": "float"},
            # REQUIRED by UE LoadMegaPlantsJsonToCollection validation
            "phyllotaxyLeaf": {"isArray": True, "size": 1, "type": "float"},
            # Crown profile arrays (required - 5 variations with 100 float values each)
            "plantProfile_1": {"isArray": True, "size": 1, "type": "float"},
            "plantProfile_2": {"isArray": True, "size": 1, "type": "float"},
            "plantProfile_3": {"isArray": True, "size": 1, "type": "float"},
            "plantProfile_4": {"isArray": True, "size": 1, "type": "float"},
            "plantProfile_5": {"isArray": True, "size": 1, "type": "float"},
            "randomAngle": {"isArray": True, "size": 1, "type": "float"},
            "randomAngleChild": {"isArray": True, "size": 1, "type": "float"},
            "trunkGrowth": {"isArray": True, "size": 1, "type": "float"},
        },
        "points": {
            "attributes": {
                # LOD attributes
                "LODArray_endCapSegments": {"isArray": False, "size": 1, "type": "int"},
                "LODArray_keepPTs": {"isArray": False, "size": 1, "type": "int"},
                "LOD_branchPscaleGradient": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                },
                "LOD_canopyGradient": {"isArray": False, "size": 1, "type": "float"},
                "LOD_groundGradient": {"isArray": False, "size": 1, "type": "float"},
                "LOD_hullGradient": {"isArray": False, "size": 1, "type": "float"},
                "LOD_mainTrunkGradient": {"isArray": False, "size": 1, "type": "float"},
                "LOD_plantPscaleGradient": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                },
                "LOD_totalPscaleGradient": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                },
                # Position attribute
                "P": {"isArray": False, "size": 3, "type": "float"},  # Flattened xyz
                # Branch/hierarchy attributes
                "branchGradient": {"isArray": False, "size": 1, "type": "float"},
                "generation": {"isArray": False, "size": 1, "type": "int"},
                "lengthFromRoot": {"isArray": False, "size": 1, "type": "float"},
                "lengthFromSeed": {"isArray": False, "size": 1, "type": "float"},
                "plantGradient": {"isArray": False, "size": 1, "type": "float"},
                # Bud attributes
                # budDevelopment: 6-element int array per point [gen, cycle, age, 0, 0, max_age]
                # Required by PVMaterialSettings.cpp: BudDevelopment[0]=gen, BudDevelopment[2]=age
                "budDevelopment": {"isArray": True, "size": 1, "type": "int"},
                "budDirection": {"isArray": True, "size": 3, "type": "float"},
                "budHormoneLevels": {"isArray": True, "size": 1, "type": "float"},
                "budLateralMeristem": {"isArray": False, "size": 1, "type": "int"},
                "budLightDetected": {"isArray": True, "size": 1, "type": "float"},
                "budNumber": {"isArray": False, "size": 1, "type": "int"},
                "budStatus": {"isArray": False, "size": 1, "type": "int"},
                # Scale/radius
                "pscale": {"isArray": False, "size": 1, "type": "float"},
                # UV coordinates
                "uv_base": {"isArray": False, "size": 3, "type": "float"},
                "uv_base_unmodified": {"isArray": False, "size": 3, "type": "float"},
                "uv_metric": {"isArray": False, "size": 3, "type": "float"},
                "uv_out": {"isArray": False, "size": 3, "type": "float"},
                # Light simulation
                "njord_pixelIdx": {"isArray": False, "size": 1, "type": "float"},
            },
            "positions": [],  # List of [x, y, z]
        },
        "primitives": {
            "attributes": {
                # Branch hierarchy
                "branchGeneration": {"isArray": False, "size": 1, "type": "int"},
                "branchHierarchyNumber": {"isArray": False, "size": 1, "type": "int"},
                "branchNumber": {"isArray": False, "size": 1, "type": "int"},
                "branchParentNumber": {"isArray": False, "size": 1, "type": "int"},
                "branchSourceBudNumber": {"isArray": False, "size": 1, "type": "int"},
                # Compound branch info
                "compoundBranchGeneration": {
                    "isArray": False,
                    "size": 1,
                    "type": "int",
                },
                "compoundBranchNumber": {"isArray": False, "size": 1, "type": "int"},
                "compoundBranchParentNumber": {
                    "isArray": False,
                    "size": 1,
                    "type": "int",
                },
                # Parent/child relationships
                "children": {"isArray": True, "size": 1, "type": "int"},
                "parents": {"isArray": True, "size": 1, "type": "int"},
                # Instancer data (for twigs/leaves) - isArray=True, per-branch variable-length arrays
                "instancer_LFR": {"isArray": True, "size": 1, "type": "float"},
                "instancer_N": {"isArray": True, "size": 3, "type": "float"},
                "instancer_UP": {"isArray": True, "size": 3, "type": "float"},
                "instancer_name": {"isArray": True, "size": 1, "type": "string"},
                "instancer_pivot": {"isArray": True, "size": 3, "type": "float"},
                "instancer_scale": {"isArray": True, "size": 1, "type": "float"},
                # Metadata
                "path": {"isArray": False, "size": 1, "type": "string"},
                "pivotPointLocation": {"isArray": False, "size": 3, "type": "float"},
                "plantNumber": {"isArray": False, "size": 1, "type": "int"},
                "shop_materialpath": {"isArray": False, "size": 1, "type": "string"},
                "streamName": {"isArray": False, "size": 1, "type": "string"},
            },
            "points": [],  # List of [point_index_arrays]
        },
    }


def create_empty_pve_preset() -> dict[str, Any]:
    """
    Create an empty PVE preset with proper structure and empty value arrays.

    Returns:
        Dictionary with PVE structure, all attributes have empty value arrays
    """
    schema = get_pve_schema()

    # Convert schema to actual preset structure
    preset = {
        "globalAttributes": {},
        "points": {"attributes": {}, "positions": []},
        "primitives": {"attributes": {}, "positions": []},
    }

    # Fill in global attributes with empty values
    for key, spec in schema["globalAttributes"].items():
        preset["globalAttributes"][key] = {
            "isArray": spec["isArray"],
            "size": spec["size"],
            "type": spec["type"],
            "value": (
                []
                if spec["isArray"]
                else (0 if spec["type"] in ["int", "float"] else "")
            ),
        }

    # Fill in point attributes
    for key, spec in schema["points"]["attributes"].items():
        preset["points"]["attributes"][key] = {
            "isArray": spec["isArray"],
            "size": spec["size"],
            "type": spec["type"],
            "values": [],
        }

    # Fill in primitive attributes
    for key, spec in schema["primitives"]["attributes"].items():
        preset["primitives"]["attributes"][key] = {
            "isArray": spec["isArray"],
            "size": spec["size"],
            "type": spec["type"],
            "values": [],
        }

    return preset
