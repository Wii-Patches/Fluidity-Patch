#!/bin/zsh
# Build the standalone GUI patcher app with PyInstaller.
# Output: tools/dist/Fluidity-Patcher.app (macOS) or dist/Fluidity-Patcher/ (other OSes).
# Needs pycryptodome (pip install pycryptodome).
set -eu
cd "${0:a:h}"
command -v pyinstaller >/dev/null || { echo "pyinstaller not found (pip install pyinstaller tkinterdnd2 pycryptodome)"; exit 1; }
pyinstaller --noconfirm Fluidity-Patcher.spec
echo "built: tools/dist/Fluidity-Patcher"
