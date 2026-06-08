# FindParking Paris

Application web pour trouver le parking le plus proche à Paris et comparer voirie vs parking.

## Site en ligne (GitHub Pages)

**URL** : https://parkeco.fr/

- Page principale : `/` (`index.html` à la racine)
- Ancienne URL `/appli/findparking.html` → redirige vers `/`
- Données : `donnée/app_parkings.json`, `donnée/tarifs_paris_arrondissements.json`, `donnée/images/`

## Mise à jour locale

```bash
cd construction_base && python3 fab_base_appli.py
```

Puis commit + push → Vercel redéploie automatiquement.
