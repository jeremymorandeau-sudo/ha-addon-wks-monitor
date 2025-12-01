#!/usr/bin/env bash
set -euo pipefail

if [ -f /data/options.json ]; then
  echo "🔧 Chargement des options /data/options.json"
else
  echo "❌ options.json introuvable — add-on Home Assistant requis" >&2
  exit 1
fi

# Patcher wks_monitor.py au premier démarrage si nécessaire
if [ ! -f "/data/wks_patched" ]; then
    echo "🔧 Premier démarrage - Application du patch..."
    python3 patch_wks_monitor.py wks_monitor.py
    if [ $? -eq 0 ]; then
        echo "✅ Patch appliqué avec succès"
        touch /data/wks_patched
    else
        echo "⚠️ Erreur lors du patch - Vérifier les logs"
    fi
fi
