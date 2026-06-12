#!/bin/bash
# 1/ ParkEco sur le Mac uniquement (Safari local)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=parkeco_stop_serveur.sh
source "$SCRIPT_DIR/parkeco_stop_serveur.sh"
cd "$ROOT"
PORT=8766

if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Ancien serveur détecté — arrêt automatique…"
  parkeco_stop_serveur || exit 1
fi

echo "Démarrage du serveur Mac sur http://127.0.0.1:$PORT …"
nohup python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$ROOT" >/tmp/parking-http-mac-$PORT.log 2>&1 &
disown
sleep 1

URL="http://127.0.0.1:$PORT/"
open -a Safari "$URL" 2>/dev/null || open "$URL"

echo ""
echo "════════════════════════════════════════"
echo "  ParkEco — Mac"
echo "════════════════════════════════════════"
echo ""
echo "  $URL"
echo ""
echo "  Pour arrêter :"
echo "  • Entrée dans ce terminal, ou"
echo "  • double-clic sur « arreter_serveur.command »"
echo "════════════════════════════════════════"
echo ""

read -r -p "Serveur actif. Appuyez sur Entrée pour arrêter…"
parkeco_stop_serveur
echo "Serveur Mac arrêté."
