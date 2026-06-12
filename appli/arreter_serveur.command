#!/bin/bash
# Arrête tous les serveurs ParkEco locaux (Mac + iPhone)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=parkeco_stop_serveur.sh
source "$SCRIPT_DIR/parkeco_stop_serveur.sh"

PORT=8766

if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Arrêt du serveur sur le port $PORT…"
  if parkeco_stop_serveur; then
    echo "✓ Port $PORT libéré."
  else
    read -r -p "Appuyez sur Entrée pour fermer…"
    exit 1
  fi
else
  parkeco_stop_serveur >/dev/null 2>&1
  echo "• Port $PORT déjà libre."
fi

read -r -p "Appuyez sur Entrée pour fermer…"
