# Historique — Routage / Tour de France (arrêt soir 17 juillet 2026)

Reprendre ici demain. Session Cursor précédente = hybride + article + sélecteur d’heure.

---

## Relancer en 30 secondes

```bash
cd "/Users/jean-claude/Documents/codage/parking_ok"
# Clé déjà dans routage/.ors_api_key (gitignoré)
python3 appli/serve_iphone_test.py --http 8768 "$(pwd)"
# Mac :  http://127.0.0.1:8768/routage/
# iPhone (même Wi‑Fi) : http://<IP-Mac>:8768/routage/
# Si Wi‑Fi bloque iPhone↔Mac : tunnel cloudflared (voir plus bas)
```

Ou double-clic : `appli/lancer_test_iphone.command` (port **8768**).

Article : http://127.0.0.1:8768/actu/tour-de-france-2026-paris-circulation-stationnement/

---

## Objectif produit

1. **Article** explique l’événement (TdF + Paris Respire le dimanche 26 juillet).  
2. **Outil Maps minimaliste** calcule un trajet qui évite les zones **actives à l’heure choisie**.  
3. **Export Google Maps** pour le GPS au volant (hybride).  
4. **2ᵉ outil** : parking hors zones (même heure / mêmes couches) — **pas encore au niveau du routage**.

---

## Décisions validées (ne pas rouvrir)

| Sujet | Décision |
|--------|----------|
| Architecture | **Hybride** : ORS calcule → Leaflet affiche → Maps guide |
| Waypoints seuls | **Abandonné** (zigzags) — ancien `…/chemin/` |
| Navigation native ParkEco | **Non** |
| Appli parking `index.html` | **Ne pas toucher** depuis ce chantier |
| Heure | Défaut **Maintenant** + sélecteur ; filtre zones actives |
| Couches | **Mixer** Tour de France + Paris Respire à la même heure |
| Export Maps | Coords `/dir/…` (pas `via:` — cassé sur Maps web) ; ~4 points clés |

---

## Fait (17 juillet)

### Routage `/routage/`
- UI type Maps (peu de texte, carte large, barre Maps après calcul)
- Titre : **Itinéraire pour éviter les zones fermées**
- OpenRouteService via `/api/route` (`api/route.js` + `serve_local.py` / `serve_iphone_test.py`)
- Clé : `routage/.ors_api_key` (gitignoré) — **déjà installée**
- Suggestions adresses : API `api-adresse.data.gouv.fr`
- Sélecteur **Quand** (Maintenant / datetime-local)
- Charge `donnée/tour_de_france_2026_zones.geojson` + `donnée/paris_respire_secteurs.geojson`
- Filtre horaires TdF (`active_start` / `active_end`) + logique Paris Respire (jours / créneaux / buffer 1 h)
- `?quand=2026-07-26T12:00` supporté (liens article)
- Légende : Tour (rouge) / Respire (orange) / itinéraire (bleu)

### Données TdF
- `construction_base/fab_tour_de_france.py` → event **2026-07-26** + horaires structurés par secteur (approx. base 2025)
- Régénérer : `python3 construction_base/fab_tour_de_france.py`

### Article
- URL : `/actu/tour-de-france-2026-paris-circulation-stationnement/`
- Source JSON : `donnée/parkeco_actualites.json` → `python3 construction_base/fab_seo_pages.py`
- 2 CTA : parking carte `?quand=…` + `/routage/?quand=…`
- Maillage 14 juillet / Paris Respire
- Ancienne page `/tour-de-france-paris-circulation-stationnement/` → **redirige** vers le nouvel article
- Outils carte/chemin sous `tour-de-france-paris-circulation-stationnement/` **conservés** (URLs outils)

### Divers
- iPhone : souvent besoin tunnel si isolation Wi‑Fi  
  `cloudflared tunnel --url http://127.0.0.1:8768`
- Word clé ORS : ne plus versionner ; utiliser `.ors_api_key`

---

## À faire demain (ordre suggéré)

1. ~~**Outil parking hors zones**~~ → **FAIT** (18 juil.) : `/tour-de-france-paris-circulation-stationnement/carte/` — rayon 1 km, flag dans/hors zone (TdF + Respire), sélecteur d’heure + `?quand=`
2. Peaufiner IHM iPhone (si besoin) après test réel.
3. Mettre `ORS_API_KEY` sur **Vercel** quand déploiement.
4. Quand l’arrêté officiel 2026 sort : corriger polygones + horaires dans `fab_tour_de_france.py`.
5. Optionnel : commit Git (seulement si demandé).

---

## Fait (18 juillet — matin)

### Parking `/tour-de-france-paris-circulation-stationnement/carte/`
- Remplace le placeholder « bientôt »
- Destination + **Quand** (Maintenant / datetime)
- Tous les parkings `app_parkings.json` dans **1 km**
- Flag **Dans zone fermée** / **Hors zone** (union TdF actifs + Paris Respire actifs)
- Carte : zones rouge/orange + pastilles vertes (hors) / rouges (dans)
- Lien article déjà OK avec `?quand=2026-07-26T12:00`
- **Sans** toucher à `index.html` (outil autonome, comme `/routage/`)

---

## Fichiers clés

| Chemin | Rôle |
|--------|------|
| `routage/index.html` | Appli routage + horaires |
| `routage/.ors_api_key` | Clé ORS (secret local) |
| `api/route.js` | Proxy prod |
| `appli/serve_iphone_test.py` | Serveur LAN + `/api/route` |
| `donnée/tour_de_france_2026_zones.geojson` | Zones TdF |
| `donnée/paris_respire_secteurs.geojson` | Zones Respire |
| `donnée/parkeco_actualites.json` | Article |
| `actu/tour-de-france-2026-paris-circulation-stationnement/` | Page article générée |

---

## Sources

- TdF 2025 (réf. provisoire) : https://www.paris.fr/pages/les-restrictions-de-circulation-et-de-stationnement-pour-le-tour-de-france-2025-31895  
- Paris Respire opendata : dataset secteurs  
- Gabarit article : `14-juillet-paris-circulation-stationnement/`
