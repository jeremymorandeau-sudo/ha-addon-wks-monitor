#!/usr/bin/with-contenv bashio
echo -e "\033[94m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
echo -e "\033[92m🚀 WKS Monitor v2.0.4-B\033[0m"
echo -e "\033[93m🔧 Mode : Lecture seule (Dry-Run permanent)\033[0m"
echo -e "\033[96m🔗 MQTT : core-mosquitto:1883 (jeremy)\033[0m"
echo -e "\033[94m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"

python3 /wks_monitor.py
