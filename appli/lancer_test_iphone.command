#!/bin/bash
# 2/ ParkEco — test sur iPhone (même Wi‑Fi, sans parkeco.fr)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=parkeco_stop_serveur.sh
source "$SCRIPT_DIR/parkeco_stop_serveur.sh"
cd "$ROOT"
PORT=8768
LOG="/tmp/parking-http-iphone-$PORT.log"

if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Ancien serveur iPhone détecté — arrêt automatique…"
  parkeco_stop_port "$PORT" || exit 1
fi

MAC_IP=""
for IFACE in en0 en1; do
  IP=$(ipconfig getifaddr "$IFACE" 2>/dev/null)
  if [ -n "$IP" ]; then
    MAC_IP="$IP"
    break
  fi
done

if [ -z "$MAC_IP" ]; then
  echo "⚠️  Wi‑Fi du Mac introuvable. Branchez le Mac au Wi‑Fi."
  read -r -p "Appuyez sur Entrée pour fermer…"
  exit 1
fi

IPHONE_URL="http://${MAC_IP}:${PORT}/"

echo "Démarrage du serveur iPhone (HTTP, réseau local)…"
nohup python3 "$SCRIPT_DIR/serve_iphone_test.py" --http "$PORT" "$ROOT" >"$LOG" 2>&1 &
disown
sleep 1

if ! lsof -i :$PORT >/dev/null 2>&1; then
  echo "❌ Le serveur n’a pas démarré. Voir $LOG"
  read -r -p "Appuyez sur Entrée pour fermer…"
  exit 1
fi

printf '%s' "http://${MAC_IP}:${PORT}/routage/" | pbcopy 2>/dev/null

echo ""
echo "══════════════════════════════════════════════════════"
echo "  ParkEco — test iPhone"
echo "══════════════════════════════════════════════════════"
echo ""
echo "  1. iPhone sur le MÊME Wi‑Fi que ce Mac"
echo "  2. Safari → ouvrir :"
echo ""
echo "     http://${MAC_IP}:${PORT}/routage/"
echo ""
echo "  (copiée dans le presse-papiers)"
echo ""
echo "  Si Safari dit « impossible d’ouvrir » (Wi‑Fi isolé) :"
echo "  utilisez le tunnel Cloudflare (demandez à Cursor) ou"
echo "  testez d’abord le rendu mobile dans Safari Mac :"
echo "  Développement → Mode Responsive → iPhone"
echo ""
echo "  ⚠  Ne fermez PAS cette fenêtre tant que vous testez."
echo "     Entrée = arrêt du serveur."
echo ""
echo "  Pour arrêter aussi : double-clic « arreter_serveur.command »"
echo "══════════════════════════════════════════════════════"
echo ""

read -r -p "Serveur actif. Appuyez sur Entrée pour arrêter…"
parkeco_stop_port "$PORT"
echo "Serveur iPhone arrêté."
