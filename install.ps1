$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceDir = Join-Path $scriptDir "URDF_Exporter"
$targetBase = Join-Path $env:APPDATA "Autodesk\Autodesk Fusion 360\API\Scripts"
$targetDir = Join-Path $targetBase "URDF_Exporter"

if (-not (Test-Path $sourceDir -PathType Container)) {
    Write-Error "URDF_Exporter directory not found. Make sure install.ps1 is in the fusion2urdf project root."
}

if ((Test-Path $targetBase) -and -not (Test-Path $targetBase -PathType Container)) {
    Write-Error "Target path exists but is not a directory: $targetBase"
}

if (-not (Test-Path $targetBase)) {
    New-Item -ItemType Directory -Path $targetBase -Force | Out-Null
}

if (Test-Path $targetDir -PathType Container) {
    $response = Read-Host "Detected an existing URDF_Exporter. Remove and reinstall? (y/N)"
    if ($response -ne "y") {
        Write-Host "Installation canceled."
        exit 0
    }

    Remove-Item -Path $targetDir -Recurse -Force
    Write-Host "Previous version removed."
}

Write-Host "Installing URDF_Exporter..."
Copy-Item -Path $sourceDir -Destination $targetBase -Recurse -Force
Write-Host "URDF_Exporter installation complete!"
Write-Host "Source: $sourceDir"
Write-Host "Target: $targetDir"
Write-Host ""
Write-Host "Usage:"
Write-Host "1. Open Fusion 360"
Write-Host "2. Go to Scripts and Add-Ins (Shift+S)"
Write-Host "3. Select URDF_Exporter and run"
Write-Host "4. Choose automatic cleanup to keep files tidy"
Write-Host ""
Write-Host "Installation complete! Restart Fusion 360 to load the new version."
