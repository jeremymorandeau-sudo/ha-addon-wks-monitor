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

# Démarrer l'addon
python3 wks_monitor.py
```

#### **4.4 - Commit :**
En bas de la page :
- Message : "Auto-patch au démarrage"
- Clique **"Commit changes"**

---

### **Étape 5 : Mettre à jour l'addon dans Home Assistant**

1. **Paramètres** → **Modules complémentaires**
2. Trouve **WKS Monitor**
3. Clique sur **⋮** (3 points en haut à droite)
4. Clique sur **"Vérifier les mises à jour"** ou **"Mettre à jour"**
5. Une fois mis à jour, clique sur **"Redémarrer"**

---

### **Étape 6 : Vérifier que ça a marché**

1. Dans l'addon, clique sur **"Journal"** (logs)
2. Tu devrais voir au début :
```
🔧 Premier démarrage - Application du patch...
✅ Patch appliqué avec succès
[MQTT] Subscribed to wks/command/#
```

✅ **Si tu vois ça → C'EST BON !**

---

## 🧪 **Test rapide**

### **Dans Home Assistant → Outils de développement → MQTT**

**Publier sur :**
```
wks/command/set_float_voltage
