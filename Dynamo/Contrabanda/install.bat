@echo off
setlocal enabledelayedexpansion

echo =============================================
echo  Contrabanda - Dynamo Plugin Installer
echo =============================================
echo.

:: -----------------------------------------------------------------------
:: 1. Build
:: -----------------------------------------------------------------------
echo [1/3] Building ContrabandaExtension...
dotnet build "%~dp0ContrabandaExtension.csproj" --configuration Release --output "%~dp0bin\Release" --nologo

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. Make sure the .NET 8 SDK is installed and
    echo        Revit 2025 with Dynamo for Revit is present on this machine.
    pause
    exit /b 1
)
echo       Build succeeded.
echo.

:: -----------------------------------------------------------------------
:: 2. Locate the Dynamo Revit extensions folder
::    Dynamo Revit stores user extensions under:
::      %APPDATA%\Dynamo\Dynamo Revit\<version>\extensions\
::    We scan a list of known version strings (newest first).
:: -----------------------------------------------------------------------
echo [2/3] Locating Dynamo Revit extensions folder...

set BASE=%APPDATA%\Dynamo\Dynamo Revit
set TARGET=

:: Dynamo 3.x (ships with Revit 2025/2026)
for %%V in (3.4 3.3 3.2 3.1 3.0) do (
    if exist "!BASE!\%%V\extensions\" (
        set TARGET=!BASE!\%%V\extensions\Contrabanda
        goto :found
    )
)

:: Dynamo 2.x (ships with Revit 2023/2024)
for %%V in (2.19 2.18 2.17 2.16 2.13 2.12) do (
    if exist "!BASE!\%%V\extensions\" (
        set TARGET=!BASE!\%%V\extensions\Contrabanda
        goto :found
    )
)

echo ERROR: Could not find a Dynamo Revit extensions folder under:
echo        %BASE%
echo.
echo        Please install Dynamo for Revit and run Dynamo at least once
echo        so that the user-profile folders are created.
pause
exit /b 1

:found
echo       Found: !TARGET!
echo.

:: -----------------------------------------------------------------------
:: 3. Deploy
:: -----------------------------------------------------------------------
echo [3/3] Deploying files...

if not exist "!TARGET!" mkdir "!TARGET!"

copy /Y "%~dp0bin\Release\ContrabandaExtension.dll" "!TARGET!\" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy ContrabandaExtension.dll
    pause
    exit /b 1
)

copy /Y "%~dp0ContrabandaExtension.xml" "!TARGET!\" >nul
if errorlevel 1 (
    echo ERROR: Failed to copy ContrabandaExtension.xml
    pause
    exit /b 1
)

echo.
echo =============================================
echo  Installation complete!
echo.
echo  Files deployed to:
echo    !TARGET!
echo.
echo  Next steps:
echo    1. Open (or restart) Revit 2025
echo    2. Launch Dynamo
echo    3. Click the "Contrabanda" menu in Dynamo's menu bar
echo    4. Select "Open Contrabanda"
echo =============================================
echo.
pause
