#!/bin/bash
# Arrêt des serveurs locaux ParkEco (Mac : 8766, iPhone : 8767 HTTPS, 8768 HTTP)

parkeco_stop_port() {
  local PORT="$1"
  local killed=0

  pkill -f "python3 -m http.server ${PORT}" 2>/dev/null && killed=1
  pkill -f "serve_iphone_test.py ${PORT}" 2>/dev/null && killed=1
  pkill -f "serve_iphone_test.py --http ${PORT}" 2>/dev/null && killed=1
  pkill -f "cloudflared tunnel --url http://127.0.0.1:${PORT}" 2>/dev/null && killed=1

  local attempt
  for attempt in 1 2 3; do
    local pids
    pids=$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null)
    [ -z "$pids" ] && break
    kill $pids 2>/dev/null
    sleep 1
    pids=$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null)
    [ -z "$pids" ] && break
    kill -9 $pids 2>/dev/null
    sleep 1
    killed=1
  done

  if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "❌ Le port $PORT est encore occupé."
    echo "   Processus :"
    lsof -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null
    return 1
  fi

  return 0
}

parkeco_stop_serveur() {
  local ok=0
  parkeco_stop_port 8766 || ok=1
  parkeco_stop_port 8767 || ok=1
  parkeco_stop_port 8768 || ok=1
  return "$ok"
}
