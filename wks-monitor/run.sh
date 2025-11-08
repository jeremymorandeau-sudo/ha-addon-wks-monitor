#!/usr/bin/env bash
set -euo pipefail

if [ -f /data/options.json ]; then
  echo "🔧 Chargement des options /data/options.json"
else
  echo "❌ options.json introuvable — add-on Home Assistant requis" >&2
  exit 1
fi

exec python /app/wks_monitor.py