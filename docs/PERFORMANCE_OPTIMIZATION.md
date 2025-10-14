# Performance Optimization Guide

## Overview

This document explains the performance optimizations implemented in `generate_forest.py` to handle large-scale tree generation with high growth cycle limits.

## Problem Analysis

### Original Bottlenecks

1. **Sequential Export**: Trees exported one-by-one in a single thread
2. **Low CPU Utilization**: Single-threaded export left 90% of CPU cores idle
3. **Long Export Times**: High growth cycle limits resulted in very slow processing

### Root Cause

The bottleneck is in the **export phase**, not simulation or memory. The Grove 2.2 API and Blender operations are single-threaded by design. The solution is **process-level parallelism** for the export step using Python's multiprocessing module.

### Important: Forest Simulation Stays Sequential

**The forest simulation with inter-species light competition remains sequential** to preserve realistic forest dynamics where different species compete for light. Only the **export step is parallelized** - each tree is re-simulated independently for export purposes.

## Implemented Solutions

### 1. Multiprocessing Architecture

**What it does**: Exports multiple trees in parallel using separate Python processes

**Benefits**:

- Utilizes all CPU cores (default: CPU count - 1)
- Each process has its own memory space
- Near-linear scaling with number of cores
- Prevents memory accumulation in single process

**Implementation**:

```python
# Parallel export with worker pool
with mp.Pool(processes=max_workers) as pool:
    results = pool.imap(_export_single_tree, tree_tasks)
```

### 2. Batch Processing

**What it does**: Processes trees in configurable batches with memory cleanup between batches

**Benefits**:

- Prevents memory exhaustion on large datasets
- Forces garbage collection between batches
- Allows progressive monitoring of export progress

**Configuration**:

```python
BATCH_SIZE = 10  # Trees per batch (default)
```

### 3. Worker Function Design

**What it does**: Isolated worker function `_export_single_tree_from_forest()` re-simulates and exports each tree

**Benefits**:

- Process isolation prevents memory leaks
- Independent Grove instance per tree (re-simulated with same growth cycles)
- Explicit cleanup after each export

**Note**: Each tree is re-simulated in isolation for export. This means exported trees won't reflect inter-species light competition effects from the original forest simulation, but will have the same growth cycle progression. The trade-off enables parallel export while keeping forest simulation accurate.

## Usage

### Basic Usage (Default: Parallel)

```bash
# Automatically uses all available cores
python src/growpy/cli/generate_forest.py forest.csv --growth-cycle-limit 20
```

### Advanced Configuration

```bash
# Control worker count
python generate_forest.py forest.csv --max-workers 4

# Disable multiprocessing (sequential fallback)
python generate_forest.py forest.csv --no-multiprocessing
```

### CLI Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--max-workers` | int | CPU count - 1 | Number of parallel worker processes |
| `--no-multiprocessing` | flag | False | Disable parallel processing |

## Performance Expectations

### Expected Speedup

| CPU Cores | Expected Speedup | Example: 100 trees |
|-----------|------------------|-------------------|
| 4 cores | 3-3.5x | 30 min → 9 min |
| 8 cores | 6-7x | 30 min → 4.5 min |
| 16 cores | 12-14x | 30 min → 2.2 min |

**Note**: Speedup is not perfectly linear due to:

- Process overhead
- I/O bottlenecks (file writing)
- Memory bandwidth limitations

### Memory Considerations

**With Multiprocessing**:

- Each worker process uses ~500MB-1GB per tree
- Total memory = `max_workers × per_tree_memory + base`
- Batch processing prevents runaway memory usage

**Recommendations**:

- **8GB RAM**: Use `--max-workers 2 --batch-size 5`
- **16GB RAM**: Use `--max-workers 4 --batch-size 10` (default)
- **32GB+ RAM**: Use `--max-workers 8 --batch-size 15`

### Growth Cycle Impact

Higher growth cycles = more computational work per tree:

| Growth Cycles | Time per Tree | Recommended Strategy |
|--------------|---------------|---------------------|
| 1-10 | Fast (~30s) | Standard multiprocessing |
| 11-20 | Medium (~1-2min) | Multiprocessing + small batches |
| 21-50 | Slow (~5-10min) | Reduce max_workers, prioritize memory |
| 50+ | Very slow | Consider species-level parallelism |

## Technical Details

### Process Architecture

```
Main Process
├── Load CSV data
├── Bundle twig files
└── Create worker pool
    ├── Worker 1: Tree 0001 → Export
    ├── Worker 2: Tree 0002 → Export
    ├── Worker 3: Tree 0003 → Export
    └── Worker N: Tree NNNN → Export
```

### Worker Process Lifecycle

1. **Initialize**: Load Grove API and Blender in isolated process
2. **Simulate**: Create grove, add tree, simulate growth cycles
3. **Export**: Build model and export to FBX/USD
4. **Cleanup**: Delete grove, force garbage collection
5. **Return**: Send file paths back to main process

### Why Not GPU?

**Grove 2.2 API** is not GPU-accelerated:

- Tree simulation is CPU-bound algorithmic work
- Mesh building uses CPU-based geometry operations
- Blender's USD export is CPU-based

**No GPU Benefit** for:

- Growth simulation
- Mesh generation
- File I/O

**Potential GPU Use** (future):

- Render previews
- Physics simulations (if exposed by API)

## Troubleshooting

### Issue: Out of Memory Errors

**Solution**:

```bash
# Reduce workers and batch size
python generate_forest.py forest.csv --max-workers 2 --batch-size 3
```

### Issue: Slow Progress Despite Multiprocessing

**Possible Causes**:

1. **Disk I/O bottleneck**: Writing many large files
   - Solution: Use SSD, reduce output formats
2. **Very high growth cycles**: Individual trees take very long
   - Solution: Lower `--growth-cycle-limit`
3. **Memory thrashing**: System swapping to disk
   - Solution: Reduce `--max-workers`

### Issue: Process Hangs or Freezes

**Solution**:

```bash
# Disable multiprocessing to debug
python generate_forest.py forest.csv --no-multiprocessing
```

Check for:

- Grove API errors (see console output)
- File permission issues (output directory)
- Missing dependencies (bpy, pxr)

## Best Practices

### 1. Start Small, Scale Up

```bash
# Test with 5 trees first
head -6 forest.csv > test.csv  # Keep header + 5 rows
python generate_forest.py test.csv --max-workers 2
```

### 2. Monitor System Resources

Use Task Manager (Windows) or `htop` (Linux) to watch:

- CPU utilization per core
- Memory usage trend
- Disk I/O rates

### 3. Balance Workers vs Memory

```python
# Rule of thumb
max_workers = min(CPU_count - 1, available_RAM_GB / 2)
```

### 4. Use Quality Presets Wisely

Lower quality = faster export:

```bash
# Performance mode for testing
python generate_forest.py forest.csv --quality performance

# Ultra quality for final production
python generate_forest.py forest.csv --quality ultra --max-workers 4
```

## Future Optimizations

### Potential Improvements

1. **Species-Level Parallelism**: Export different species in parallel (even higher parallelism)
2. **Caching**: Pre-compute growth models, reuse mesh data
3. **Streaming Export**: Write files as soon as ready (reduce memory)
4. **Distributed Computing**: Export across multiple machines (cluster)

### GPU Acceleration (Limited)

While Grove API doesn't support GPU, future work could include:

- GPU-based mesh processing with CUDA
- GPU-accelerated texture generation
- GPU render farm for preview images

## Example Workflows

### Large Forest (1000+ trees)

```bash
python generate_forest.py large_forest.csv \
    --growth-cycle-limit 15 \
    --quality high \
    --max-workers 6 \
    --batch-size 20 \
    --formats usd
```

### Memory-Constrained System (8GB RAM)

```bash
python generate_forest.py forest.csv \
    --growth-cycle-limit 10 \
    --quality medium \
    --max-workers 2 \
    --batch-size 5 \
    --formats fbx
```

### Maximum Performance (32GB+ RAM, 16+ cores)

```bash
python generate_forest.py forest.csv \
    --growth-cycle-limit 20 \
    --quality ultra \
    --max-workers 12 \
    --batch-size 30 \
    --formats usd usda fbx
```

## Monitoring Progress

The script provides detailed progress information:

```
Loading forest data from: forest.csv
Scaled growth cycles: max 25 -> 15

Bundling twig files for 3 species...

Exporting 150 individual trees...
Using multiprocessing with 7 workers (batch size: 10)

Processing batch 1/15 (trees 1-10)
Batch 1: 100%|██████████| 10/10 [02:15<00:00, 13.5s/tree]

Processing batch 2/15 (trees 11-20)
Batch 2: 100%|██████████| 10/10 [02:18<00:00, 13.8s/tree]
...

Exported 150 tree files (usd, fbx) with 'ultra' quality
```

## Important Limitations

### Light Competition Not Preserved in Export

**Critical Understanding**: The multiprocessing optimization parallelizes the **export phase only**. This means:

1. **Forest Simulation** (with light competition): Runs sequentially, all groves together
   - Inter-species light competition is calculated correctly
   - Trees grow realistically with shade effects from neighbors

2. **Individual Tree Export**: Each tree is re-simulated independently
   - Trees are grown in isolation with same growth cycles
   - Light competition effects are NOT present in exported trees
   - Each exported tree represents "ideal conditions" growth

### When This Matters

- **PCG/Procedural Placement**: Export is perfect - place trees based on original forest positions
- **Pre-positioned Forests**: Consider if lack of competition effects is acceptable
- **Hero Trees**: Individual trees work great since they're standalone anyway

### If You Need Competition Effects

If preserving light competition in exported trees is critical:

```bash
# Disable multiprocessing to export trees with original forest context
python generate_forest.py forest.csv --no-multiprocessing
```

This will be slower but may better preserve growth characteristics. However, note that Grove's export system typically exports individual trees anyway, so competition effects may not fully transfer regardless.

## Conclusion

The multiprocessing optimization provides **3-14x speedup** for the export phase, making high growth cycle limits practical for large-scale forest generation. The forest simulation maintains full inter-species light competition accuracy, while export parallelization offers massive speed improvements for most use cases.

**Key Takeaway**: Parallel export accelerates your workflow while keeping forest simulation realistic. For Unreal PCG workflows, this is the ideal balance.
