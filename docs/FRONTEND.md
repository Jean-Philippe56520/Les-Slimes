# Frontend React + TypeScript + PixiJS

Le frontend principal de Les Slimes est une interface d'observation du monde canonique. Il ne simule aucun tick, n'accède jamais directement à PostgreSQL et n'embarque aucun jeton divin.

## Emplacement

`frontend/`

Technologies : React, TypeScript, Vite et PixiJS v8.

## Données utilisées

Le navigateur consomme uniquement les projections publiques :

- `GET /health` ;
- `GET /world` ;
- `GET /world/slimes` ;
- `GET /world/foods`.

Le polling courant est d'environ 1,2 seconde. Le frontend représente l'état canonique reçu ; il ne l'extrapole pas comme une seconde simulation.

## Développement local

API locale :

```bash
uvicorn les_slimes.production:create_api_app --factory --host 127.0.0.1 --port 8000
```

Frontend :

```bash
cd frontend
npm install
npm run dev
```

En développement, l'API par défaut est `http://127.0.0.1:8000`.

## Production Netlify

Le dépôt contient `netlify.toml`. La build publie `frontend/dist`.

Configurer côté Netlify :

- `VITE_API_BASE_URL` = URL HTTPS publique de l'API canonique.

Configurer côté API :

- `LES_SLIMES_CORS_ORIGINS` = origine exacte du site Netlify, sans chemin. Plusieurs origines peuvent être séparées par des virgules.

Aucun `father`, `herald`, token d'Ordre ou token de Chaos ne doit être exposé comme variable `VITE_*` : ces variables sont intégrées au bundle navigateur.

## Visualisation

La scène PixiJS affiche :

- limites du monde 2D ;
- ressources alimentaires ;
- Slimes vivants ;
- couleur selon la génération ;
- rayon selon l'énergie ;
- atténuation si la santé est faible ;
- direction courante.

L'interface React affiche notamment : tick, population, nourriture, génération maximale, énergie/santé moyennes, naissances/décès, retard runtime, backlog de commandes, comportements dominants et digest scientifique.

## Sécurité

Les routes publiques sont volontairement en lecture seule. Les routes mutantes restent authentifiées côté API. CORS est une barrière navigateur supplémentaire, jamais un mécanisme d'authentification.

Le frontend ne doit jamais recevoir :

- DSN PostgreSQL ;
- token Créateur ;
- token Héraut ;
- tokens des dieux ;
- secrets de déploiement.
