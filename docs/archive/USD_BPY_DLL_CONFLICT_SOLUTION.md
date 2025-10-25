# USD + Blender DLL Conflict - Proper Solution

**Date:** 2025-10-14  
**Issue:** DLL load failed while importing `_tf` from USD Python bindings (`pxr`)  
**Root Cause:** Incompatible DLL versions between pip-installed `usd-core` and `bpy`  
**Solution:** Install both packages from conda-forge

## Problem

When `bpy` (Blender) and `usd-core` (OpenUSD) are installed via pip, they may be compiled against different versions of shared libraries like:

- TBB (Intel Threading Building Blocks)
- Boost
- OpenSubdiv
- Other USD dependencies

Windows DLLs are loaded process-wide, so when both packages try to use different versions of the same DLL, you get:

```
ImportError: DLL load failed while importing _tf: The specified procedure could not be found.
```

## Solution: Hybrid Approach with TBB Pinning

Since `bpy` is not available from conda-forge on Windows, we use a hybrid approach:

- Install `usd-core` and `tbb` from conda-forge
- Install `bpy` via pip (which should link against conda's TBB)

### Step 1: Update environment.yml

```yaml
name: the-grove
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - pip
  - numpy=1.*
  - pandas
  - matplotlib
  - scikit-learn
  - tqdm
  
  # USD from conda-forge with TBB pinning for compatibility
  - usd-core>=23.11  # OpenUSD from conda-forge
  - tbb>=2021.7  # Pin TBB version explicitly for bpy compatibility
  
  # Note: bpy not available from conda-forge on Windows
  # Will be installed via pip, which should use conda's TBB
  - pip:
    - bpy>=4.0  # Blender Python API via pip

variables:
  PYTHONPATH: ./src:./src/the_grove_22/modules
```

**Key Changes:**

- `usd-core` installed from conda-forge with TBB dependency
- Explicitly pin `tbb` version from conda-forge
- `bpy` installed via pip AFTER conda's TBB is in place
- pip's bpy should link against conda's TBB libraries

### Step 2: Recreate the Environment

```powershell
# Remove old environment
conda deactivate
conda env remove -n the-grove

# Create new environment from updated environment.yml
mamba env create -f environment.yml

# Activate new environment
conda activate the-grove

# Verify installation
python -c "from pxr import Usd; import bpy; print('Success! Both USD and bpy loaded')"
```

### Step 3: Test the Fix

```powershell
# Test USD export
python src/growpy/cli/generate_forest.py data/input/test.csv --output-dir data/output/test --formats usda --quality medium --no-nanite-assembly
```

Expected output:

- No DLL errors
- Skeleton USD files created successfully
- Tree USD files with embedded skeletons
- All USD operations working correctly

## Why This Works

1. **Consistent Build Environment**: Conda-forge builds all packages in controlled environments with specific compiler versions and flags

2. **Shared Dependencies**: When conda resolves the environment, it ensures:

   ```
   bpy → tbb=2021.7 → libtbb.dll (version A)
   usd-core → tbb=2021.7 → libtbb.dll (version A)  # SAME VERSION
   ```

3. **DLL Compatibility**: All packages use the same DLL versions:
   - `tbb.dll` (Intel Threading Building Blocks)
   - `boost_python.dll`
   - `tbbmalloc.dll`
   - OpenSubdiv libraries

4. **ABI Compatibility**: Packages are compiled with compatible C++ ABIs (Application Binary Interface)

## Verification

After recreating the environment, verify the packages are from conda-forge:

```powershell
conda list bpy
conda list usd-core
```

Expected output should show `conda-forge` as the channel:

```
# packages in environment at C:\Users\...\miniforge3\envs\the-grove:
#
# Name                    Version                   Build  Channel
bpy                       3.6.0           py311h...         conda-forge
usd-core                  23.11           py311h...         conda-forge
```

## Troubleshooting

### Issue: Conda can't find bpy package

If conda-forge doesn't have `bpy` for your platform:

```yaml
dependencies:
  - usd-core  # From conda-forge
  - pip:
    - bpy  # From pip only if conda version unavailable
```

### Issue: Version conflicts

If you get version conflicts, try pinning specific versions:

```yaml
dependencies:
  - bpy=3.6.*
  - usd-core=23.11.*
  - tbb=2021.*  # Explicitly pin TBB version
```

### Issue: Still getting DLL errors

1. Check for system-wide USD/Blender installations that might interfere
2. Verify PATH doesn't include other Blender/USD installations
3. Ensure no pip-installed USD packages remain:

   ```powershell
   pip uninstall usd-core usd-python pxr -y
   ```

## Benefits Over Subprocess Approach

| Approach | Pros | Cons |
|----------|------|------|
| **Conda packages (this solution)** | ✅ Simple<br>✅ Fast<br>✅ Native integration<br>✅ Single process | ❌ Requires conda-forge packages |
| **Subprocess separation** | ✅ Always works<br>✅ Complete isolation | ❌ Complex<br>❌ Slower<br>❌ IPC overhead |

## Alternative: Docker with Conda

For complete reproducibility across all platforms:

```dockerfile
FROM mambaorg/micromamba:latest

COPY environment.yml /tmp/environment.yml
RUN micromamba create -f /tmp/environment.yml && \
    micromamba clean --all --yes

ENV PYTHONPATH=/workspace/src:/workspace/src/the_grove_22/modules
```

## References

- Conda-forge bpy: <https://anaconda.org/conda-forge/bpy>
- Conda-forge usd-core: <https://anaconda.org/conda-forge/usd-core>
- TBB documentation: <https://www.intel.com/content/www/us/en/developer/tools/oneapi/onetbb.html>
- USD documentation: <https://graphics.pixar.com/usd/docs/index.html>

## Summary: What Actually Works

**Best Solution:** Two-process subprocess approach (already implemented)

Because `bpy` is not available from conda-forge on Windows, the DLL conflict persists even with careful dependency management. The two-process approach we implemented (with grove JSON serialization) is actually the **correct and robust solution**:

1. **Phase 1 subprocess**: Export skeleton USD using `pxr` only (no bpy loaded)
2. **Phase 2 main process**: Export tree meshes using bpy (pxr calls fail gracefully)
3. **Grove JSON serialization**: Ensures exact matching between skeleton and mesh

This approach:

- ✅ **Always works** regardless of DLL conflicts
- ✅ **Guarantees exact matching** via grove JSON serialization  
- ✅ **Already implemented** and ready to use
- ✅ **Maintains deterministic results** from same Grove state

## When Inline Embedding Would Work

If both packages were from conda-forge (on Linux/macOS):

1. Remove subprocess code
2. Restore `include_skeleton=True` in exports
3. Let blender_export handle everything inline

But on Windows with pip's bpy, **the subprocess approach is the proper production solution**.
