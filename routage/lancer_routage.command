#!/bin/bash
# Lance le serveur ParkEco avec proxy de routage (port 8766)
cd "$(dirname "$0")/.." || exit 1
PORT="${PORT:-8766}"
export PORT
# Charge la clé depuis routage/.ors_api_key si absente de l'environnement
if [ -z "$ORS_API_KEY" ] && [ -f routage/.ors_api_key ]; then
  ORS_API_KEY="$(tr -d '\r\n' < routage/.ors_api_key)"
  export ORS_API_KEY
fi
if [ -z "$ORS_API_KEY" ]; then
  echo "Pas de clé trouvée. Placez-la dans routage/.ors_api_key"
  echo
fi
echo "→ http://127.0.0.1:${PORT}/routage/"
open "http://127.0.0.1:${PORT}/routage/" 2>/dev/null || true
exec python3 routage/serve_local.py
