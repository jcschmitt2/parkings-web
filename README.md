# FindParking Paris

Application web pour trouver le parking le plus proche à Paris et comparer voirie vs parking.

## Site en ligne (GitHub Pages)

**URL** : https://jcschmitt2.github.io/parkings-web/

Activation (une seule fois) :

1. Repo [parkings-web](https://github.com/jcschmitt2/parkings-web) → **Settings** → **Pages**
2. **Source** : Deploy from a branch
3. **Branch** : `main` → dossier `/ (root)` → **Save**
4. Attendre 1–3 min, puis ouvrir l’URL ci-dessus

- Page principale : `/appli/findparking.html` (ou `/` via redirection)
- Données : `donnée/app_parkings.json`, `donnée/tarifs_paris_arrondissements.json`, `donnée/images/`

## Mise à jour locale

```bash
cd construction_base && python3 fab_base_appli.py
```

Puis commit + push → Vercel redéploie automatiquement.
