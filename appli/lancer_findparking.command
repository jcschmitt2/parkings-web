#!/bin/bash
# Lance FindParking depuis la racine du projet (parent de appli/)
cd "$(dirname "$0")/.."
PORT=8766

# Arrête un ancien serveur bloqué sur ce port (sinon Safari ne répond plus).
if lsof -i :$PORT >/dev/null 2>&1; then
  PIDS=$(lsof -t -i :$PORT 2>/dev/null)
  if [ -n "$PIDS" ]; then
    kill $PIDS 2>/dev/null
    sleep 1
  fi
fi

echo "Démarrage du serveur sur http://127.0.0.1:$PORT ..."
python3 -m http.server "$PORT" >/tmp/parking-http-$PORT.log 2>&1 &
sleep 1
URL="http://127.0.0.1:$PORT/appli/findparking.html"
open -a Safari "$URL" 2>/dev/null || open "$URL"
echo "Ouvert : $URL"
echo "Laissez ce terminal ouvert (ou le serveur en arrière-plan)."
