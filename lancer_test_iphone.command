#!/bin/bash
# Test ParkEco sur iPhone (même Wi‑Fi) sans mise en ligne sur parkeco.fr
cd "$(dirname "$0")"
PORT=8766

# Arrête un ancien serveur sur ce port
if lsof -i :$PORT >/dev/null 2>&1; then
  PIDS=$(lsof -t -i :$PORT 2>/dev/null)
  if [ -n "$PIDS" ]; then
    kill $PIDS 2>/dev/null
    sleep 1
  fi
fi

# Adresse locale du Mac sur le Wi‑Fi
MAC_IP=""
for IFACE in en0 en1; do
  IP=$(ipconfig getifaddr "$IFACE" 2>/dev/null)
  if [ -n "$IP" ]; then
    MAC_IP="$IP"
    break
  fi
done

if [ -z "$MAC_IP" ]; then
  echo "⚠️  Impossible de trouver l’adresse IP du Mac (Wi‑Fi déconnecté ?)."
  echo "   Branchez le Mac au Wi‑Fi, puis relancez ce script."
  read -r -p "Appuyez sur Entrée pour fermer…"
  exit 1
fi

IPHONE_URL="http://${MAC_IP}:${PORT}/"
MAC_URL="http://127.0.0.1:${PORT}/"

echo "Démarrage du serveur (accessible sur le réseau local)…"
nohup python3 -m http.server "$PORT" --bind 0.0.0.0 >/tmp/parking-http-iphone-$PORT.log 2>&1 &
disown
sleep 1

if ! lsof -i :$PORT >/dev/null 2>&1; then
  echo "❌ Le serveur n’a pas démarré. Voir /tmp/parking-http-iphone-$PORT.log"
  read -r -p "Appuyez sur Entrée pour fermer…"
  exit 1
fi

printf '%s' "$IPHONE_URL" | pbcopy 2>/dev/null

echo ""
echo "══════════════════════════════════════════════════════"
echo "  ParkEco — test iPhone (sans parkeco.fr)"
echo "══════════════════════════════════════════════════════"
echo ""
echo "  1. iPhone sur le MÊME Wi‑Fi que ce Mac"
echo "  2. Safari sur l’iPhone → ouvrir :"
echo ""
echo "     $IPHONE_URL"
echo ""
echo "  (URL copiée dans le presse-papiers — collez sur l’iPhone)"
echo ""
echo "  Mac (optionnel) : $MAC_URL"
echo ""
echo "  Pour arrêter : fermez ce terminal ou tuez le port $PORT"
echo "══════════════════════════════════════════════════════"
echo ""

open -a Safari "$MAC_URL" 2>/dev/null || open "$MAC_URL" 2>/dev/null

read -r -p "Serveur actif. Appuyez sur Entrée pour arrêter le serveur et fermer…"

if lsof -i :$PORT >/dev/null 2>&1; then
  kill $(lsof -t -i :$PORT 2>/dev/null) 2>/dev/null
  echo "Serveur arrêté."
fi
