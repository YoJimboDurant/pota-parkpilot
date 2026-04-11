#!/usr/bin/env bash

set -euo pipefail

echo "Bootstrapping POTA ParkPilot project structure..."

# ------------------------------------------------------------
# ROOT CHECK
# ------------------------------------------------------------
if [[ ! -d "parkpilot" || ! -d "config" || ! -d "data" || ! -d "scripts" ]]; then
  echo "Error: run this script from the root of your pota-parkpilot project."
  exit 1
fi

# ------------------------------------------------------------
# CREATE SUBDIRECTORIES
# ------------------------------------------------------------
mkdir -p \
  config \
  data/exports \
  data/sessions \
  docs \
  parkpilot/core \
  parkpilot/services \
  parkpilot/storage \
  parkpilot/ui/web/templates \
  parkpilot/utils \
  scripts \
  tests

# ------------------------------------------------------------
# CREATE __init__.py FILES
# ------------------------------------------------------------
touch \
  parkpilot/__init__.py \
  parkpilot/core/__init__.py \
  parkpilot/services/__init__.py \
  parkpilot/storage/__init__.py \
  parkpilot/ui/__init__.py \
  parkpilot/ui/web/__init__.py \
  parkpilot/utils/__init__.py

# ------------------------------------------------------------
# CREATE PLACEHOLDER FILES IF MISSING
# ------------------------------------------------------------
create_file_if_missing() {
  local file_path="$1"
  local file_content="$2"

  if [[ ! -f "$file_path" ]]; then
    cat > "$file_path" <<EOF
$file_content
EOF
    echo "Created: $file_path"
  else
    echo "Exists, skipped: $file_path"
  fi
}

create_file_if_missing "README.md" "# POTA ParkPilot

A Raspberry Pi field companion for POTA activations.

## Goals

- Session-based activation workflow
- Multi-operator support
- WSJT-X integration
- CW logging
- Park-aware operation
- Tablet-friendly web interface
"

create_file_if_missing ".gitignore" "__pycache__/
*.pyc
.git/

.venv/
venv/
env/

data/exports/*
data/sessions/*
!data/exports/.gitkeep
!data/sessions/.gitkeep
"

create_file_if_missing "requirements.txt" "flask
"

create_file_if_missing "config/parkpilot_config.json" '{
  "adif_file": "/home/pi/.local/share/WSJT-X/wsjtx_log.adi",
  "operators": ["KE4MKG", "KS4GY"],
  "activation_target": 10,
  "poll_seconds": 2,
  "window_title": "POTA ParkPilot",
  "count_unique_calls": true,
  "exports_dir": "data/exports",
  "park_source_field": "COMMENT",
  "operator_field": "STATION_CALLSIGN",
  "park_regex": "(K|US)-\\\\d{4,5}"
}'

create_file_if_missing "docs/notes.md" "# ParkPilot Notes

- Build session interface first
- Add simple CW entry inside session app
- Keep existing WSJT-X tracker stable
- Later bridge WSJT-X service into session manager
"

create_file_if_missing "parkpilot/core/models.py" '"""Core data models for ParkPilot."""
'

create_file_if_missing "parkpilot/core/session_manager.py" '"""Session manager for ParkPilot."""

def get_current_session():
    return None
'

create_file_if_missing "parkpilot/services/wsjtx_service.py" '"""WSJT-X service for ParkPilot.

Temporary home for the existing tracker script.
"""
'

create_file_if_missing "parkpilot/storage/db.py" '"""Database helpers for ParkPilot."""
'

create_file_if_missing "parkpilot/ui/web/app.py" 'from flask import Flask

def create_app():
    app = Flask(__name__)

    @app.route("/")
    def index():
        return "ParkPilot web app is alive."

    return app
'

create_file_if_missing "parkpilot/utils/adif.py" '"""ADIF parsing helpers for ParkPilot."""
'

create_file_if_missing "scripts/start_web.py" '#!/usr/bin/env python3

from parkpilot.ui.web.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
'

create_file_if_missing "scripts/start_wsjtx_service.py" '#!/usr/bin/env python3

print("WSJT-X service launcher placeholder")
'

# ------------------------------------------------------------
# CREATE GITKEEP FILES
# ------------------------------------------------------------
touch data/exports/.gitkeep
touch data/sessions/.gitkeep
touch tests/.gitkeep

# ------------------------------------------------------------
# MAKE SCRIPTS EXECUTABLE
# ------------------------------------------------------------
chmod +x scripts/start_web.py
chmod +x scripts/start_wsjtx_service.py

# ------------------------------------------------------------
# DONE
# ------------------------------------------------------------
echo
echo "Bootstrap complete."
echo
echo "Suggested next steps:"
echo "1. Copy your current tracker into parkpilot/services/wsjtx_service.py"
echo "2. Create a virtual environment"
echo "3. pip install -r requirements.txt"
echo "4. Run: python scripts/start_web.py"
echo
echo "Current tree:"
tree -a -I "__pycache__|*.pyc|.git"