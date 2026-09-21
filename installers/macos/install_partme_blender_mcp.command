#!/bin/bash
set -euo pipefail

version="0.7.0-rc.2"
dry_run="false"
case "${1:-}" in
  --version) printf 'PartMe Blender MCP installer %s\n' "$version"; exit 0 ;;
  --dry-run) dry_run="true" ;;
  "") ;;
  *) printf 'Usage: %s [--dry-run|--version]\n' "$0" >&2; exit 2 ;;
esac

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
runtime_archive="$script_dir/partme-blender-mcp-runtime-$version.zip"
install_root="$HOME/Library/Application Support/PartMe/BlenderMCP/$version"
python_cmd=""
for candidate in python3.13 python3.12 python3.11 python3; do
  resolved=$(command -v "$candidate" || true)
  if [ -n "$resolved" ] && "$resolved" -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 1)' 2>/dev/null; then
    python_cmd="$resolved"
    break
  fi
done

[ -n "$python_cmd" ] || { echo "Python 3.11, 3.12, or 3.13 was not found." >&2; exit 1; }
[ -f "$runtime_archive" ] || { echo "Runtime archive is missing: $runtime_archive" >&2; exit 1; }

printf 'Runtime: %s\nInstall: %s\nPython: %s\n' "$runtime_archive" "$install_root" "$python_cmd"
if [ "$dry_run" = "true" ]; then
  echo "Dry run only; no files changed."
  exit 0
fi

mkdir -p "$install_root"
"$python_cmd" -m venv "$install_root/venv"
"$install_root/venv/bin/python" -m pip install --disable-pip-version-check "$runtime_archive"
"$install_root/venv/bin/python" -m partme_blender_mcp --help >/dev/null 2>&1 || true
printf 'Installed. MCP command: %s -m partme_blender_mcp\n' "$install_root/venv/bin/python"
echo "Install the adjacent Add-on ZIP from Blender Preferences > Add-ons > Install from Disk."
