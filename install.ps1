# URDF_Exporter automatic installation script
# This script automatically checks for and removes old versions, then installs the new one

param(
    [switch]$Force = $false
)

# Configure paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$sourceDir = Join-Path $scriptDir "URDF_Exporter"
$targetBase = "${env:APPDATA}\Autodesk\Autodesk Fusion 360\API\Scripts"
$targetDir = Join-Path $targetBase "URDF_Exporter"

Write-Host "URDF_Exporter Automatic Installer" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan

# Check whether the source directory exists
if (-not (Test-Path $sourceDir)) {
    Write-Host "Error: URDF_Exporter directory not found" -ForegroundColor Red
    Write-Host "Make sure this script is in the fusion2urdf project root" -ForegroundColor Red
    exit 1
}

# Check whether the target base directory exists
if (-not (Test-Path $targetBase)) {
    Write-Host "Error: Fusion 360 API Scripts directory not found" -ForegroundColor Red
    Write-Host "Path: $targetBase" -ForegroundColor Red
    Write-Host "Make sure Fusion 360 is installed correctly" -ForegroundColor Red
    exit 1
}

# Check whether an old version already exists
if (Test-Path $targetDir) {
    if (-not $Force) {
        Write-Host "Detected an installed URDF_Exporter" -ForegroundColor Yellow
        Write-Host "Path: $targetDir" -ForegroundColor Yellow
        $response = Read-Host "Remove the old version and install the new one? (y/N)"
        if ($response -ne 'y' -and $response -ne 'Y') {
            Write-Host "Installation canceled" -ForegroundColor Yellow
            exit 0
        }
    }
    
    try {
        Write-Host "Removing old version..." -ForegroundColor Yellow
        Remove-Item -Path $targetDir -Recurse -Force
        Write-Host "Old version removed" -ForegroundColor Green
    } catch {
        Write-Host "Warning: Could not fully remove the old version; will attempt to overwrite" -ForegroundColor Yellow
        Write-Host "Error details: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Copy the new version
try {
    Write-Host "Installing URDF_Exporter..." -ForegroundColor Yellow
    Copy-Item -Path $sourceDir -Destination $targetBase -Recurse -Force
    Write-Host "✓ URDF_Exporter installation complete!" -ForegroundColor Green
    
    # Show installation info
    Write-Host "" -ForegroundColor White
    Write-Host "Installation details:" -ForegroundColor Cyan
    Write-Host "  Source: $sourceDir" -ForegroundColor Gray
    Write-Host "  Target: $targetDir" -ForegroundColor Gray
    
    # Check optional features
    $cleanupScript = Join-Path $targetDir "cleanup_components.py"
    if (Test-Path $cleanupScript) {
        Write-Host "  ✓ Automatic cleanup feature installed" -ForegroundColor Green
    }
    
    Write-Host "" -ForegroundColor White
    Write-Host "Usage:" -ForegroundColor Cyan
    Write-Host "1. Open Fusion 360" -ForegroundColor White
    Write-Host "2. Go to Scripts and Add-Ins (Shift+S)" -ForegroundColor White
    Write-Host "3. Select URDF_Exporter and run" -ForegroundColor White
    Write-Host "4. Choose automatic cleanup to keep files tidy" -ForegroundColor White
    
} catch {
    Write-Host "✗ Installation failed!" -ForegroundColor Red
    Write-Host "Error details: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "" -ForegroundColor White
Write-Host "Installation complete! Please restart Fusion 360 to load the new version." -ForegroundColor Green
