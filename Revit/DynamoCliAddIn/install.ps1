# DynamoCliAddIn - Build and Install Script
# Builds the add-in and deploys the .addin manifest to the user's Revit Addins folder.

param(
    [switch]$BuildOnly,
    [switch]$Uninstall,
    [string]$RevitVersion = "2025"
)

$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$ProjectFile = Join-Path $ProjectDir "DynamoCliAddIn.csproj"
$AddinManifest = Join-Path $ProjectDir "DynamoCliAddIn.addin"
$BuildOutput = Join-Path (Join-Path $ProjectDir "bin") "Debug"
$TargetAddinsDir = Join-Path (Join-Path (Join-Path (Join-Path $env:APPDATA "Autodesk") "Revit") "Addins") $RevitVersion
$TargetManifest = Join-Path $TargetAddinsDir "DynamoCliAddIn.addin"

if ($Uninstall) {
    Write-Host "Uninstalling DynamoCliAddIn from Revit $RevitVersion..." -ForegroundColor Yellow
    if (Test-Path $TargetManifest) {
        Remove-Item $TargetManifest -Force
        Write-Host "  Removed: $TargetManifest" -ForegroundColor Green
    } else {
        Write-Host "  Not installed." -ForegroundColor Gray
    }
    exit 0
}

# Build
Write-Host "Building DynamoCliAddIn..." -ForegroundColor Cyan
dotnet build $ProjectFile -c Debug
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "Build succeeded." -ForegroundColor Green

if ($BuildOnly) {
    exit 0
}

# Verify build output
$BuiltDll = Join-Path $BuildOutput "DynamoCliAddIn.dll"
if (-not (Test-Path $BuiltDll)) {
    Write-Host "ERROR: Built DLL not found at: $BuiltDll" -ForegroundColor Red
    exit 1
}

# Create Addins directory if needed
if (-not (Test-Path $TargetAddinsDir)) {
    New-Item -ItemType Directory -Path $TargetAddinsDir -Force | Out-Null
    Write-Host "Created: $TargetAddinsDir" -ForegroundColor Yellow
}

# Generate the .addin manifest pointing to the build output DLL
$AbsDllPath = (Resolve-Path $BuiltDll).Path
$ManifestContent = @"
<?xml version="1.0" encoding="utf-8"?>
<RevitAddIns>
  <AddIn Type="Application">
    <Name>DynamoCliAddIn</Name>
    <Assembly>$AbsDllPath</Assembly>
    <FullClassName>DynamoCliAddIn.App</FullClassName>
    <AddInId>B5F5C6A2-7E3D-4A1B-9C8E-2F6D0E4A3B71</AddInId>
    <VendorId>DynamoNodeContraband</VendorId>
    <VendorDescription>Named Pipe IPC bridge for Dynamo CLI tools</VendorDescription>
  </AddIn>
</RevitAddIns>
"@

Set-Content -Path $TargetManifest -Value $ManifestContent -Encoding UTF8
Write-Host "Installed manifest: $TargetManifest" -ForegroundColor Green
Write-Host "  Assembly: $AbsDllPath" -ForegroundColor Gray
Write-Host ""
Write-Host "Restart Revit $RevitVersion to load DynamoCliAddIn." -ForegroundColor Cyan
