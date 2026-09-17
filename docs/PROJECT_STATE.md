# Les Slimes — état courant du projet

Ce fichier sert de point de reprise après changement ou réinitialisation de conversation.

## Repo canonique

- Repo unique : `Jean-Philippe56520/Les-Slimes`
- Branche de référence : `main`
- Moteur : Python dans `src/les_slimes/`
- Frontend principal : React + TypeScript + PixiJS dans `frontend/`, cible Netlify
- Streamlit : laboratoire secondaire science/admin/debug
- Aucun autre repo n'est dans le périmètre Les Slimes.

## Invariant central

Il existe un seul monde canonique, persistant et partagé : une horloge, un état officiel, une histoire, une command queue et une persistance active.

Toute mutation externe officielle suit :

`acteur authentifié -> API/command queue -> CanonicalWorldWorker -> GovernancePolicy -> moteur Python -> persistance atomique monde + intervention + budget + audit`

L'API ne simule aucun tick et ne mute jamais directement `World`. La gouvernance est revalidée juste avant commit. Les expériences sont explicitement non canoniques et isolées.

## Ontologie divine

- `father` = le Créateur/Père, autorité souveraine ;
- `herald` = Jean-Philippe, Héraut/Porte-parole/Messager, acteur distinct ;
- `order` = Ordre ;
- `chaos` = Chaos ;
- `observer` = Observateur ;
- `system` = mécanismes techniques.

`herald` démarre actif, niveau Observation, budget nul et aucune permission mutante. Il n'est pas administrateur de la gouvernance. Seul `father` peut actuellement administrer permissions, pouvoir, budgets et sanctions via `GovernanceAdminService`.

Ordre et Chaos ne peuvent pas usurper une identité, fabriquer une approbation, cacher l'auteur d'une action ou provoquer une violation pour la faire attribuer à un autre acteur.

## Moteur biologique présent

- monde 2D continu ;
- énergie, santé, âge, mortalité ;
- ressources alimentaires ;
- reproduction, filiation, mutations et traits génétiques ;
- mémoire spatiale ;
- relations sociales ;
- signaux et apprentissage ;
- transmission Slime -> Slime ;
- DSL comportemental ;
- mystères persistants ;
- RNG dédié sauvegardable/restaurable ;
- événements/checkpoints ;
- `World.state_digest()` déterministe.

## Runtime canonique présent

- métadonnées UTC et `tick_duration_seconds` ;
- `CanonicalRuntime.advance_to(target_time)` ;
- catch-up déterministe par batches ;
- continu == interruption/reload/catch-up au même digest dans les tests ;
- command queue persistante, ordonnée et idempotente ;
- commandes paginées et provenance `source_proposal_id` ;
- `CanonicalWorldWorker` comme writer officiel ;
- temps simulé séparé du wall-clock du processus ;
- writer lease exclusif avec token de fencing + génération ;
- heartbeat et takeover ;
- writer expiré/zombie empêché de committer ;
- reprise après crash via événement `command_applied` sans double effet ;
- `CanonicalWorkerService` pour boucle H24 ;
- arrêt SIGINT/SIGTERM propre et libération du lease ;
- métriques santé : tick, retard, ticks dus, backlog, plus ancienne commande, lease ;
- CLI historique `worker-run`/`worker-status` et entrée production `les-slimes-production`.

## Gouvernance persistante présente

- `PowerLevel` : Observation, Miracle, Décret, Loi, Transgression ;
- permission technique, niveau, budget et sanction séparés ;
- budgets append-only : `miracle`, `legislative`, `favor`, `transgression_debt` ;
- sanctions déclaratives allowlistées ;
- `GovernancePolicy` fail-closed ;
- double autorisation pour les propositions Observateur mutantes ;
- intervention divine attribuée pour chaque mutation ;
- sauvegarde monde + débit budget + état intervention + audit dans la même transaction ;
- rejet commande + intervention transactionnel ;
- statuts terminaux `executed`, `rejected`, `cancelled` protégés par la base ;
- index empêchant un double débit négatif par intervention ;
- audit append-only chaîné par hash ;
- journaux, propositions et Conseil divin persistants ;
- aucune commande d'auto-escalade ;
- Transgression = classification auditable, jamais bypass ;
- gouvernance exclue du digest biologique.

## API canonique présente

FastAPI fournit la frontière réseau :

- lectures publiques : `/health`, `/world`, `/world/slimes`, `/world/foods` ;
- identité : `/me` ;
- `POST /commands` -> queue uniquement ;
- lecture/écriture journaux et propositions ;
- lecture gouvernance ;
- routes `/admin/...` Créateur uniquement via `GovernanceAdminService`.

Authentification :

- Bearer token -> résolution serveur vers acteur persistant ;
- jamais de confiance dans un `actor_id` métier fourni par le client ;
- empreintes SHA-256 configurées via `LES_SLIMES_AUTH_TOKEN_HASHES_JSON` ;
- aucun secret dans GitHub ;
- configuration absente = routes protégées fail-closed ;
- acteur inactif = accès refusé ;
- `herald` ne peut pas utiliser les routes Créateur ;
- schémas mutatifs `extra=forbid` ;
- allowlist CORS configurable via `LES_SLIMES_CORS_ORIGINS`.

Voir `docs/API.md`.

## Persistance PostgreSQL présente

La couche de persistance est maintenant abstraite par `RelationalRepository`.

### SQLite

Reste utilisé pour :

- développement local ;
- compatibilité historique ;
- Lab ;
- forks/expériences non canoniques.

### PostgreSQL

`PostgreSQLRepository` est implémenté et testé contre un vrai PostgreSQL 16 dans la CI :

- sérialisation du monde identique au backend SQLite ;
- save/reload au même digest et même état RNG ;
- types `DOUBLE PRECISION`/`BYTEA` ;
- advisory locks transactionnels pour sérialiser les écritures et la prise de lease ;
- fencing/takeover du Worker ;
- guards PostgreSQL pour statuts terminaux et débit unique ;
- séquences synchronisables ;
- mutation gouvernée testée avec monde + budget + audit.

Backend de production sélectionné par `LES_SLIMES_DATABASE_URL`. Le code n'est lié à aucun fournisseur particulier.

## Migration SQLite -> PostgreSQL

`les-slimes-production migrate --sqlite <path>` :

- exige une cible PostgreSQL fraîche ;
- refuse un writer lease SQLite encore valide ;
- verrouille la source pendant le snapshot ;
- copie monde, metadata, événements/checkpoints, command queue, acteurs, gouvernance et audit ;
- ne copie jamais le writer lease ;
- resynchronise les séquences PostgreSQL ;
- vérifie digest source/cible ;
- vérifie nombre de commandes pending ;
- valide la chaîne d'audit.

Cette migration est testée en CI contre PostgreSQL réel.

## Science/forks présents

- scopes `canonical` / `non_canonical_experiment` ;
- runtime canonique refuse une DB expérimentale ;
- runner expérimental refuse une DB canonique ;
- forks SQLite reconstruits dans une nouvelle DB ;
- command queue, lease, runtime actors et tables `divine_*` non copiés ;
- `ExperimentManifest` traçable avec source tick/event/digest/git/config, condition, seed, digests et ticks ;
- reseed RNG explicite ;
- deux forks exacts reproductibles ;
- un canonique PostgreSQL peut produire un fork SQLite non canonique isolé sans donner à l'expérience un accès d'écriture à PostgreSQL.

## Production H24 présente dans le code

Entrée : `les-slimes-production` :

- `init` : initialise une base canonique vide et refuse l'écrasement ;
- `migrate` : migration SQLite -> PostgreSQL ;
- `worker` : service canonique continu ;
- `status` : santé runtime.

Le Dockerfile démarre FastAPI par défaut. `deploy/compose.production.yml` déclare exactement :

- un service API ;
- un service Worker ;
- même `LES_SLIMES_DATABASE_URL` ;
- restart automatique ;
- healthcheck API.

Voir `docs/PRODUCTION.md`.

**État opérationnel :** le code H24 est prêt et testé, mais aucune instance distante réellement active n'est encore prouvée depuis ce projet. Il faut connecter un hébergeur, injecter DSN/secrets, initialiser ou migrer le canonique, démarrer API+Worker puis vérifier `/health`.

## Frontend React/PixiJS

Le frontend principal est présent dans `frontend/` :

- React + TypeScript strict + Vite ;
- PixiJS v8 ;
- représentation du monde 2D et des limites ;
- Slimes avec génération, énergie, santé et direction ;
- ressources alimentaires ;
- tick, population, nourriture, génération max, énergie/santé moyennes ;
- naissances/décès, retard Worker, backlog et comportements dominants ;
- digest scientifique ;
- responsive ;
- polling des projections publiques uniquement ;
- aucune simulation côté navigateur ;
- aucun secret/token dans le frontend ;
- configuration Netlify via `netlify.toml` ;
- build TypeScript/Vite ajouté à la CI.

Voir `docs/FRONTEND.md`.

## Streamlit

Streamlit reste un laboratoire secondaire science/admin/debug. Il ne doit pas devenir le processus qui fait vivre le monde et ne lance aucune simulation canonique concurrente.

## Historique des grandes PR

- #2 temps canonique/catch-up ;
- #3 command queue + writer lease ;
- #4 suppression des modes au profit des permissions acteurs ;
- #5 frontière canonique ;
- #6 forks scientifiques isolés ;
- #7 Worker H24 durci ;
- #8 gouvernance divine persistante ;
- #9 ontologie Créateur/Héraut ;
- #10 acteur runtime `herald` ;
- #11 API/authentification canonique ;
- #12 contrat de backend de persistance ;
- #13 PostgreSQL + migration + runtime H24 de production.

La branche frontend suivante construit la PR #14 React/PixiJS/Netlify.

## Dette prioritaire après frontend

1. connecter un hébergeur réel pour PostgreSQL + API + Worker ;
2. initialiser/migrer le monde canonique réel puis vérifier son fonctionnement H24 ;
3. déployer le frontend sur Netlify et relier API/CORS ;
4. configurer sauvegardes, restauration testée et supervision externe ;
5. automatiser rapports/Drive ;
6. activer Ordre/Chaos comme GPT Projects autonomes et leurs cycles planifiés ;
7. exporter journaux/Conseil vers Drive sans rôle transactionnel.

## Lecture obligatoire

Au début d'une nouvelle conversation :
1. vérifier `main` et les derniers commits ;
2. `docs/PROJECT_STATE.md` ;
3. `docs/PROJECT_INSTRUCTIONS.md` ;
4. `README.md` ;
5. `docs/DIVINE_GOVERNANCE.md` ;
6. `docs/SCIENTIFIC_PROTOCOL.md` ;
7. `docs/OBSERVER_CONTRACT.md` ;
8. `config/default.yaml`.

Si moteur/persistance concernés, lire aussi `src/les_slimes/world/engine.py`, `src/les_slimes/database/sqlite_repo.py`, `src/les_slimes/observer/proposals.py`, le backend de persistance concerné et les tests pertinents.
