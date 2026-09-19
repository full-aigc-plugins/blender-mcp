param(
  [switch]$DryRun,
  [switch]$Version
)
$ErrorActionPreference = "Stop"
$ReleaseVersion = "0.4.0"
if ($Version) {
  Write-Output "PartMe Blender MCP installer $ReleaseVersion"
  exit 0
}
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeArchive = Join-Path $ScriptDir "partme-blender-mcp-runtime-$ReleaseVersion.zip"
$InstallRoot = Join-Path $env:LOCALAPPDATA "PartMe\BlenderMCP\$ReleaseVersion"
$PythonExe = $null
foreach ($Candidate in @("-3.13", "-3.12", "-3.11")) {
  try {
    $Resolved = & py $Candidate -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $Resolved) { $PythonExe = $Resolved.Trim(); break }
  } catch { }
}
if (-not $PythonExe) { throw "Python 3.11, 3.12, or 3.13 was not found through the py launcher." }
if (-not (Test-Path $RuntimeArchive -PathType Leaf)) { throw "Runtime archive is missing: $RuntimeArchive" }
Write-Output "Runtime: $RuntimeArchive"
Write-Output "Install: $InstallRoot"
if ($DryRun) {
  Write-Output "Dry run only; no files changed."
  exit 0
}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
& $PythonExe -m venv (Join-Path $InstallRoot "venv")
$VenvPython = Join-Path $InstallRoot "venv\Scripts\python.exe"
& $VenvPython -m pip install --disable-pip-version-check $RuntimeArchive
Write-Output "Installed. MCP command: $VenvPython -m partme_blender_mcp"
Write-Output "Install the adjacent Add-on ZIP from Blender Preferences > Add-ons > Install from Disk."
