# Environment Setup Script for The Grove
# Fixes USD + Blender DLL conflicts by using conda-forge packages

Write-Host "The Grove Environment Setup" -ForegroundColor Cyan
Write-Host "===========================" -ForegroundColor Cyan
Write-Host ""

# Check if conda/mamba is available
$condaCmd = Get-Command conda -ErrorAction SilentlyContinue
$mambaCmd = Get-Command mamba -ErrorAction SilentlyContinue

if (-not $condaCmd -and -not $mambaCmd) {
    Write-Host "ERROR: Neither conda nor mamba found in PATH" -ForegroundColor Red
    Write-Host "Please install Miniforge or Miniconda first" -ForegroundColor Yellow
    exit 1
}

$envManager = if ($mambaCmd) { "mamba" } else { "conda" }
Write-Host "Using environment manager: $envManager" -ForegroundColor Green
Write-Host ""

# Deactivate current environment if active
Write-Host "Deactivating any active conda environment..." -ForegroundColor Yellow
conda deactivate 2>$null

# Remove old environment if it exists
Write-Host "Checking for existing 'the-grove' environment..." -ForegroundColor Yellow
$envExists = & $envManager env list | Select-String "the-grove"
if ($envExists) {
    Write-Host "Removing old 'the-grove' environment..." -ForegroundColor Yellow
    & $envManager env remove -n the-grove -y
    Write-Host "Old environment removed." -ForegroundColor Green
}
else {
    Write-Host "No existing environment found." -ForegroundColor Green
}
Write-Host ""

# Create new environment
Write-Host "Creating new 'the-grove' environment from environment.yml..." -ForegroundColor Yellow
Write-Host "(This may take several minutes - downloading and compiling packages)" -ForegroundColor Cyan
Write-Host ""

& $envManager env create -f environment.yml

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Environment created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Activate the environment:" -ForegroundColor White
    Write-Host "   conda activate the-grove" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "2. Verify USD and Blender are working:" -ForegroundColor White
    Write-Host "   python -c `"from pxr import Usd; import bpy; print('Success!')`"" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "3. Run a test export:" -ForegroundColor White
    Write-Host "   python src/growpy/cli/generate_forest.py data/input/test.csv --output-dir data/output/test --formats usda --quality medium --no-nanite-assembly" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Environment setup complete!" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "ERROR: Environment creation failed!" -ForegroundColor Red
    Write-Host "Please check the error messages above." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Cyan
    Write-Host "- Network connectivity problems" -ForegroundColor White
    Write-Host "- Insufficient disk space" -ForegroundColor White
    Write-Host "- Package conflicts (try updating mamba/conda)" -ForegroundColor White
    exit 1
}
