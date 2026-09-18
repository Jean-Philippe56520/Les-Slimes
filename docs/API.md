# API canonique Les Slimes

L'API FastAPI est la frontière réseau du monde canonique. Elle lit l'état, écrit des journaux/propositions et place les commandes dans la command queue. Elle ne modifie jamais directement `World` et ne prend jamais le writer lease.

## Invariant d'identité

Le client ne choisit jamais son identité d'acteur.

Flux :

`Bearer token -> authentification serveur -> actor_id persistant -> service/command queue`

Un champ `actor_id` ajouté à un payload de commande est rejeté par le schéma API. Les routes administratives exigent que le jeton résolve réellement l'acteur `father`.

`father` représente le Créateur. `herald` représente Jean-Philippe, le Héraut, sans privilège souverain par défaut.

## Persistance

En développement, SQLite reste disponible :

`LES_SLIMES_DB_PATH=/chemin/vers/world.sqlite`

En production, le backend canonique peut être PostgreSQL :

`LES_SLIMES_DATABASE_URL=postgresql://...`

Le DSN réel ne doit jamais être commité, journalisé ou stocké dans Drive. La sélection PostgreSQL est provider-neutral : le moteur n'exige aucun fournisseur particulier.

## Authentification

Variable serveur :

`LES_SLIMES_AUTH_TOKEN_HASHES_JSON`

La valeur est un objet JSON associant chaque acteur autorisé à l'empreinte SHA-256 d'un jeton aléatoire de haute entropie. Les jetons en clair ne doivent jamais être commités, journalisés ou stockés dans Drive.

Exemple de forme uniquement :

```json
{"father":"<sha256>","herald":"<sha256>","order":"<sha256>","chaos":"<sha256>"}
```

Si aucune configuration d'authentification n'est fournie, les routes protégées échouent fermées avec HTTP 503. Un acteur inactif est refusé.

## CORS et frontend

Les projections nécessaires au frontend sont publiques et strictement en lecture seule. Pour une origine web séparée, configurer côté API :

`LES_SLIMES_CORS_ORIGINS=https://exemple.netlify.app`

Plusieurs origines exactes peuvent être séparées par des virgules. CORS n'est pas un mécanisme d'authentification : les routes mutantes restent protégées par identité serveur et gouvernance.

Le frontend ne doit jamais recevoir un jeton `father`, `herald`, `order` ou `chaos`, ni un DSN PostgreSQL.

## Lancement

Développement local sur SQLite :

```bash
uvicorn les_slimes.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Production avec backend choisi par variables d'environnement :

```bash
uvicorn les_slimes.production:create_api_app --factory --host 0.0.0.0 --port 8000
```

Voir `docs/PRODUCTION.md` pour le Worker H24, PostgreSQL, migration et supervision.

## Routes principales

Lecture publique :

- `GET /health` : tick, retard, backlog et état du writer lease ;
- `GET /world` : métriques et digest du monde ;
- `GET /world/slimes` : projection des Slimes pour l'interface ;
- `GET /world/foods` : projection des ressources alimentaires.

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


## Administration des sessions divines

Routes Créateur uniquement :

- `POST /admin/divine-sessions/bind` : lie une conversation à `father`, `herald`, `order` ou `chaos`. Corps : `session_id`, `subject_id`, `actor_id`.
- `POST /admin/divine-sessions/revoke` : révoque une conversation liée. Corps : `session_id`, `reason`.

Les identifiants bruts servent uniquement au calcul SHA-256 ; seuls leurs hashes sont persistés. Les routes refusent tout acteur non autorisé et restent protégées par l'authentification Créateur existante.
