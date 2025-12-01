#!/usr/bin/env bash
set -e

echo "🔧 Chargement des options /data/options.json"

# Restaurer le backup si le patch pose problème
if [ -f "/app/wks_monitor.py.backup.20251201_180411" ]; then
    echo "⚠️ Restauration du backup..."
    cp /app/wks_monitor.py.backup.20251201_180411 /app/wks_monitor.py
    echo "✅ Backup restauré"
fi

# Démarrer l'addon sans patch
echo "🚀 Démarrage de l'addon..."
python3 wks_monitor.py
