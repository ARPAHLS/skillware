#!/usr/bin/env sh
# Rebuild a contributor checkout without leaving stale package metadata behind.
set -eu

# Delete only incomplete Skillware metadata that pip cannot uninstall safely.
python - <<'PY'
import shutil
import site
from pathlib import Path

for root in map(Path, site.getsitepackages()):
    for dist_info in root.glob("skillware-*.dist-info"):
        if (dist_info / "METADATA").is_file() and (dist_info / "RECORD").is_file():
            continue
        print(f"Removing orphan metadata: {dist_info}")
        shutil.rmtree(dist_info)
PY

# Remove the old distribution before installing the full editable developer set.
python -m pip uninstall skillware -y || true
python -m pip install -e ".[dev,all]"
