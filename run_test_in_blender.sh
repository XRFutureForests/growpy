#!/bin/bash
# Run test_skeletal_assembly.py in Blender's Python environment

# Find Blender executable
if [ -f "/Applications/Blender.app/Contents/MacOS/Blender" ]; then
    BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
elif command -v blender &> /dev/null; then
    BLENDER="blender"
else
    echo "Error: Blender not found"
    echo "Please install Blender or update the BLENDER path in this script"
    exit 1
fi

# Run test in Blender's background mode with Python script
$BLENDER --background --python src/growpy/cli/test_skeletal_assembly.py -- --output-dir data/output/test_assembly

echo ""
echo "Test complete! Check data/output/test_assembly/ for results"
