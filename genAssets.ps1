param (
    [string]$BASE_DIR = "P:\FEDS201\Scouting_Suite"
)

# Create the 'assets' folder if it doesn't exist
if (-Not (Test-Path "$BASE_DIR\assets")) {
    New-Item -ItemType Directory -Path "$BASE_DIR\assets"
}

# Run the separate build scripts
& "$BASE_DIR\buildAndroid.ps1" -BASE_DIR $BASE_DIR
# & "$BASE_DIR\buildWeb.ps1" -BASE_DIR $BASE_DIR
& "$BASE_DIR\buildWindows.ps1" -BASE_DIR $BASE_DIR

Write-Host "All builds successfully moved to the assets folder."
