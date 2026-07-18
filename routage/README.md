# Routage — ParkEco (hybride)

ParkEco calcule un **itinéraire réel** qui évite les zones fermées, l’affiche sur Leaflet, puis envoie le suivi GPS vers **Google Maps**.

## Local

```bash
cd "/Users/jean-claude/Documents/codage/parking_ok"
python3 appli/serve_iphone_test.py --http 8768 "$(pwd)"
# → http://127.0.0.1:8768/routage/
```

Clé ORS locale : `routage/.ors_api_key` (gitignoré). Proxy : `POST /api/route`.

## Production (GitHub Pages) — corriger l’erreur 405

GitHub Pages est **statique** : `POST /api/route` → **405**.  
Le site appelle alors OpenRouteService **depuis le navigateur**.

Créer sur GitHub le fichier public `routage/ors_key.js` (une seule ligne) :

```js
window.PARKECO_ORS_KEY='VOTRE_CLE_OPENROUTESERVICE';
```

(GitHub → Add file → path `routage/ors_key.js`)

Ne pas committer `.ors_api_key`. La clé dans `ors_key.js` est visible dans le navigateur (hébergement statique).

## Article

`/actu/tour-de-france-2026-paris-circulation-stationnement/`
