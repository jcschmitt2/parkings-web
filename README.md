# FindParking Paris

Application web pour trouver le parking le plus proche à Paris et comparer voirie vs parking.

## Site en ligne

- Page principale : `/appli/findparking.html`
- Données : `donnée/app_parkings.json`, `donnée/tarifs_paris_arrondissements.json`, `donnée/images/`

## Déploiement Vercel

1. Pousser ce dépôt sur GitHub
2. [vercel.com](https://vercel.com) → **Add New Project** → importer le repo
3. Framework Preset : **Other** (site statique, pas de build)
4. Root Directory : laisser vide (racine du repo)
5. **Deploy**

## Mise à jour locale

```bash
cd construction_base && python3 fab_base_appli.py
```

Puis commit + push → Vercel redéploie automatiquement.
