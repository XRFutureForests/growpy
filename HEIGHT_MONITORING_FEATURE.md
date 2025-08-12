# Height Monitoring & Timeout Protection for Growth Model Generation

## Overview

Added intelligent height monitoring and timeout protection to the `02_create_growth_models.py` script that automatically detects when tree height stops increasing and exits the growth simulation loop early. Additionally, timeout protection prevents the script from getting stuck on problematic species or infinite loops.

## Features Added

### 1. Height Monitoring Parameters
- `--height-threshold`: Minimum height increase per cycle to consider as growth (default: 0.01 units)
- `--max-cycles-without-growth`: Number of consecutive cycles without growth before stopping (default: 10)

### 2. Timeout Protection
- `--timeout`: Maximum time in seconds for growth simulation per seed (default: 60)
- Prevents infinite loops or excessively slow simulations
- Logs warning when timeout occurs with elapsed time and cycle information

### 3. Early Termination Logic
The script monitors height increase between consecutive cycles and:
- Tracks cycles where height increase falls below the threshold
- Resets the counter when significant growth is detected
- Exits the loop when no growth occurs for the specified number of consecutive cycles
- Only starts monitoring after cycle 5 to allow initial tree establishment
- Requires at least 10 cycles before considering early termination

### 3. Enhanced Metadata
- `planned_cycles`: Original number of cycles requested
- `actual_max_cycles`: Maximum cycles actually completed across all seeds
- `avg_actual_cycles`: Average cycles completed across all seeds
- `avg_simulation_time`: Average time taken for simulation across all seeds
- `early_terminations`: Count of seeds that terminated early
- `timeouts`: Count of seeds that hit the timeout limit
- Individual seed metadata includes termination status and timing information

### 4. Improved Logging
- Debug logs show height increase for each cycle
- Warning logs when timeout occurs with timing details
- Info logs when early termination occurs
- Final summary includes early termination and timeout statistics

## Usage Examples

```bash
# Default monitoring (threshold: 0.01, max cycles without growth: 10, timeout: 60s)
python src/growpy/utils/02_create_growth_models.py --species "Fagaceae - European oak"

# Stricter monitoring (more sensitive to growth plateau)
python src/growpy/utils/02_create_growth_models.py --height-threshold 0.005 --max-cycles-without-growth 5

# More lenient monitoring (less sensitive, allows longer plateau periods)
python src/growpy/utils/02_create_growth_models.py --height-threshold 0.02 --max-cycles-without-growth 15

# Custom timeout for slow-growing species
python src/growpy/utils/02_create_growth_models.py --timeout 120 --species "Fagaceae - European oak"

# Very strict timeout for quick testing
python src/growpy/utils/02_create_growth_models.py --timeout 5 --cycles 10

# Verbose mode to see detailed height monitoring and timeout information
python src/growpy/utils/02_create_growth_models.py --species "Betulaceae - Hazel" --verbose
```

## Benefits

1. **Time Savings**: Automatically stops simulation when trees reach growth plateau
2. **Reliability**: Timeout protection prevents infinite loops or stuck simulations
3. **Resource Efficiency**: Reduces computational overhead for problematic trees
4. **Accurate Models**: Still captures the full growth curve up to the plateau or timeout
5. **Configurable**: Allows fine-tuning of sensitivity to growth changes and timeout limits
6. **Transparent**: Provides detailed logging and statistics about early terminations and timeouts
7. **Robust**: Handles both normal and abnormal simulation conditions gracefully

## Testing

The feature was tested with various tree species and parameter combinations:
- Normal growth: Trees continue growing throughout all cycles
- Early termination: Trees stop growing and simulation exits early
- Timeout protection: Long-running simulations are terminated after the timeout limit
- Multiple seeds: Proper handling of different termination points per seed

The implementation correctly handles all scenarios and provides accurate growth models regardless of whether early termination or timeout occurs.
