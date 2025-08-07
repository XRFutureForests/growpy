@echo off
echo Starting USD to FBX conversion using conda environment...
echo.

REM Activate conda environment and run conversion
python convert_to_fbx.py

echo.
echo Conversion complete! Check the output directory for FBX files.
pause