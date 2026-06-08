#!/bin/bash
# Regénère app_parkings.json depuis parkings.csv et photos.csv
cd "$(dirname "$0")"
echo "Fabrication de app_parkings.json…"
python3 fab_base_appli.py
echo ""
echo "Terminé. Rechargez FindParking dans Safari si l'appli est ouverte."
