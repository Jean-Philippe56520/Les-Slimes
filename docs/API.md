# API canonique Les Slimes

L'API FastAPI est une frontière réseau du monde canonique. Elle peut lire l'état, écrire des journaux/propositions et placer des commandes dans la command queue. Elle ne modifie jamais directement `World`.

## Invariant d'identité

Le client ne choisit jamais son identité d'acteur.

Flux :

`Bearer token -> authentification serveur -> actor_id persistant -> service/command queue`

Un champ `actor_id` ajouté à un payload de commande est rejeté par le schéma API. Les routes administratives exigent que le jeton résolve réellement l'acteur `father`.

`father` représente le Créateur. `herald` représente Jean-Philippe, le Héraut, sans privilège souverain par défaut.

## Configuration

Base canonique SQLite actuelle :

`LES_SLIMES_DB_PATH=/chemin/vers/world.sqlite`

Authentification :

`LES_SLIMES_AUTH_TOKEN_HASHES_JSON`

La valeur est un objet JSON associant chaque acteur autorisé à l'empreinte SHA-256 d'un jeton aléatoire de haute entropie. Les jetons en clair ne doivent jamais être commités, journalisés ou stockés dans Drive.

Exemple de forme uniquement :

```json
{"father":"<sha256>","herald":"<sha256>","order":"<sha256>","chaos":"<sha256>"}
```

Si aucune configuration d'authentification n'est fournie, les routes protégées échouent fermées avec HTTP 503.

## Lancement de développement

Une base canonique déjà initialisée est requise.

```bash
uvicorn les_slimes.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Le déploiement public, PostgreSQL durable, TLS, rotation des jetons et supervision du processus restent des étapes distinctes de production.

## Routes principales

Lecture publique :

- `GET /health` : tick, retard, backlog et état du writer lease ;
- `GET /world` : métriques et digest du monde ;
- `GET /world/slimes` : projection des Slimes pour l'interface.

Acteur authentifié :

- `GET /me` ;
- `POST /commands` : enqueue uniquement ;
- `GET /governance` ;
- `GET/POST /journals` ;
- `GET/POST /proposals`.

Créateur uniquement :

- `POST /admin/actors` ;
- `PUT /admin/actors/{actor_id}/permissions` ;
- `PUT /admin/actors/{actor_id}/power` ;
- `POST /admin/actors/{actor_id}/budget` ;
- `PUT /admin/actors/{actor_id}/active` ;
- `POST /admin/actors/{actor_id}/sanctions` ;
- `POST /admin/sanctions/{sanction_id}/lift`.

Toutes les mutations administratives passent par `GovernanceAdminService`. Les commandes de monde restent soumises à la gouvernance finale du `CanonicalWorldWorker` au moment de leur exécution et juste avant commit.
