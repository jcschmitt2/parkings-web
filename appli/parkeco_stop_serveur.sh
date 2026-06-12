#!/bin/bash
# Arrêt robuste du serveur local ParkEco (port 8766)
parkeco_stop_serveur() {
  local PORT=8766
  local killed=0

  pkill -f "python3 -m http.server ${PORT}" 2>/dev/null && killed=1
  pkill -f "serve_iphone_test.py" 2>/dev/null && killed=1
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
