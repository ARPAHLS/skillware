#!/usr/bin/env bash
# Reinstall Skillware in editable dev mode after removing overlapping PyPI installs.
# See CONTRIBUTING.md and issue #333.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python}"

echo "Uninstalling existing skillware registrations..."
"$PY" -m pip uninstall skillware -y || true

echo "Installing editable dev dependencies from ${ROOT}..."
cd "$ROOT"
"$PY" -m pip install -e ".[dev,all]"

echo "Install health:"
"$PY" -m skillware doctor --install
