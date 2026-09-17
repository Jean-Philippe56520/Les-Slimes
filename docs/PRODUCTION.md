# Production H24 — Les Slimes

Ce document décrit le déploiement du monde canonique. Il ne crée jamais un second monde et ne transforme pas Drive en persistance transactionnelle.

## Architecture

Deux processus utilisent la même base PostgreSQL canonique :

```text
Internet / frontend
       |
     FastAPI
       |
  PostgreSQL durable
       |
CanonicalWorldWorker
```

L'API lit le monde, authentifie les acteurs et place les commandes dans la queue. Elle ne simule aucun tick et ne modifie jamais directement `World`.

Un seul Worker détient le writer lease canonique à la fois. Le fencing empêche un ancien Worker expiré de committer après takeover.

## Variables d'environnement

### Communes API / Worker

- `LES_SLIMES_DATABASE_URL` : DSN PostgreSQL du monde canonique. Ne jamais commiter cette valeur.

### API

- `LES_SLIMES_AUTH_TOKEN_HASHES_JSON` : objet JSON `actor_id -> SHA-256 du jeton`. Les jetons en clair ne sont jamais stockés dans GitHub ou Drive.

### Worker

- `LES_SLIMES_WORKER_ID` : identité stable de l'instance, optionnelle ;
- `LES_SLIMES_WORKER_POLL_SECONDS` : défaut `1` ;
- `LES_SLIMES_WORKER_LEASE_TTL_SECONDS` : défaut `30` ;
- `LES_SLIMES_WORKER_HEARTBEAT_SECONDS` : défaut `10` ;
- `LES_SLIMES_WORKER_BATCH_SIZE` : défaut `1000` ;
- `LES_SLIMES_WORKER_COMMAND_PAGE_SIZE` : défaut `1000`.

## Initialiser un monde entièrement neuf

Uniquement si aucune histoire canonique n'existe encore dans la cible :

```bash
les-slimes-production init --config config/default.yaml
```

La commande refuse d'écraser un monde déjà présent.

## Migrer le monde SQLite existant

La migration est une opération contrôlée :

1. arrêter le Worker SQLite ;
2. vérifier qu'aucun writer lease valide n'est actif ;
3. configurer `LES_SLIMES_DATABASE_URL` vers une base PostgreSQL fraîche ;
4. sauvegarder le fichier SQLite source ;
5. lancer :

```bash
les-slimes-production migrate --sqlite /chemin/world.sqlite
```

La migration :

- prend un verrou d'écriture SQLite pendant le snapshot ;
- ne copie jamais le writer lease ;
- copie monde, queue, acteurs, gouvernance et audit ;
- resynchronise les séquences PostgreSQL ;
- compare le digest source/cible ;
- compare le nombre de commandes pending ;
- valide la chaîne d'audit ;
- refuse une cible contenant déjà un monde canonique.

Ne démarrer le Worker PostgreSQL qu'après succès de ces validations.

## API

```bash
uvicorn les_slimes.production:create_api_app \
  --factory \
  --host 0.0.0.0 \
  --port 8000
```

`GET /health` expose notamment tick, retard, commandes en attente et writer lease.

## Worker

```bash
les-slimes-production worker
```

Le processus gère SIGINT/SIGTERM, libère proprement le lease et doit être configuré avec redémarrage automatique par l'orchestrateur.

État ponctuel :

```bash
les-slimes-production status
```

## Docker Compose

`deploy/compose.production.yml` lance exactement deux services applicatifs : API et Worker. Les deux utilisent le même `LES_SLIMES_DATABASE_URL`. Le Worker n'est pas répliqué volontairement ; le lease reste néanmoins la protection finale contre les doubles writers.

```bash
docker compose -f deploy/compose.production.yml up -d --build
```

Les secrets viennent de l'environnement de l'hôte ou de son secret manager, jamais du dépôt.

## PostgreSQL durable

Le moteur n'est lié à aucun fournisseur. Une instance PostgreSQL compatible peut être auto-hébergée ou fournie comme service managé. Les exigences minimales sont :

- stockage durable ;
- sauvegardes automatiques ;
- restauration testable ;
- TLS pour les connexions distantes ;
- accès réseau restreint ;
- métriques de disponibilité ;
- version PostgreSQL maintenue.

Supabase peut être utilisé comme hébergeur PostgreSQL, mais son API spécifique n'est pas requise par le moteur.

## Sauvegardes

La sauvegarde PostgreSQL doit couvrir toutes les tables canoniques, notamment : monde, metadata, events/checkpoints, runtime_commands, runtime_actors, divine_* et audit.

Une restauration n'est validée que si :

1. `World.state_digest()` correspond au dernier checkpoint attendu ;
2. la chaîne d'audit est valide ;
3. la queue est cohérente ;
4. aucun writer lease obsolète n'est considéré actif ;
5. un Worker peut reprendre et avancer sans double effet.

## Streamlit

Streamlit reste un Lab secondaire. Il n'est pas le processus qui fait vivre le monde et ne doit jamais lancer une simulation concurrente. Le conteneur principal démarre désormais FastAPI par défaut.

## Frontend

Le frontend React + TypeScript + PixiJS sera servi séparément, typiquement via Netlify. Il consomme l'API et ne contient ni secret Créateur ni accès direct à PostgreSQL.
