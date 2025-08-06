#!/bin/bash
# Script to run GrowPy scripts with proper environment setup

# Activate conda environment
source $(conda info --base)/etc/profile.d/conda.sh
conda activate /Users/maximiliansperlich/Developer/the-grove/.conda

# Set PYTHONPATH
export PYTHONPATH=/Users/maximiliansperlich/Developer/the-grove/src:/Users/maximiliansperlich/Developer/the-grove/src/the_grove_22/modules

# Run the script
python "$@"
