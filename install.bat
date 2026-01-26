@echo off
chcp 65001 >nul
echo URDF_Exporter Automatic Installer
echo ==============================

set "TARGET_DIR=%APPDATA%\Autodesk\Autodesk Fusion 360\API\Scripts\URDF_Exporter"

if exist "%TARGET_DIR%" (
    echo Detected an existing URDF_Exporter. Removing...
    rmdir /s /q "%TARGET_DIR%" 2>nul
    echo Previous version removed
)

echo Installing new version...
xcopy "URDF_Exporter" "%APPDATA%\Autodesk\Autodesk Fusion 360\API\Scripts\URDF_Exporter\" /E /I /Y >nul

if exist "%TARGET_DIR%" (
    echo ✓ URDF_Exporter installation complete!
    echo.
    echo Usage:
    echo 1. Open Fusion 360
    echo 2. Go to Scripts and Add-Ins (Shift+S)
    echo 3. Select URDF_Exporter and run
    echo 4. Choose automatic cleanup to keep files tidy
) else (
    echo ✗ Installation failed! Check the path and permissions.
)

pause
