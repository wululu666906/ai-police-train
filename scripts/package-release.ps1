# Wrapper: python scripts/package_release.py
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
python (Join-Path $Root "scripts\package_release.py")
