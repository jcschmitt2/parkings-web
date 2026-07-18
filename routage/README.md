# Routage — ParkEco (hybride)

ParkEco calcule un **itinéraire réel** qui évite les zones fermées **actives à l’heure choisie** (Tour de France + Paris Respire), l’affiche sur Leaflet, puis envoie le suivi GPS vers **Google Maps**.

Voir **`HISTORIQUE.md`** pour l’état du chantier et la reprise.

## Relancer

```bash
cd "/Users/jean-claude/Documents/codage/parking_ok"
python3 appli/serve_iphone_test.py --http 8768 "$(pwd)"
# → http://127.0.0.1:8768/routage/
```

Clé ORS : `routage/.ors_api_key` (déjà en place, gitignoré).

## Article associé

`/actu/tour-de-france-2026-paris-circulation-stationnement/`

## Ne pas faire

- Ne pas reprendre l’ancien essai waypoints seuls (`…/chemin/`).
- Ne pas modifier `index.html` (appli parking principale) depuis ce dossier.
- Ne pas committer `routage/.ors_api_key` ni de Word avec la clé.
