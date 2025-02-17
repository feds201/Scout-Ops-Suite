@echo off
setlocal

REM Set the base directory where the project folder is located
set "BASE_DIR=P:\FEDS201\Scouting_Suite"

REM Create the 'assets' folder if it doesn't exist
if not exist "%BASE_DIR%\assets" mkdir "%BASE_DIR%\assets"

REM Run the separate build scripts
call "%BASE_DIR%\buildAndroid.bat"
@REM call "%BASE_DIR%\buildWeb.bat"
call "%BASE_DIR%\buildWindows.bat"

echo "All builds successfully moved to the assets folder."

endlocal
pause
