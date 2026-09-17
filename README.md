# Les Slimes — monde artificiel persistant

**Version actuelle : 0.12.0-alpha**

Les Slimes est un projet de vie artificielle déterministe et persistante. Les Slimes ne sont pas des prompts : ils existent dans un moteur Python simulant biologie, génétique, perception, mémoire, apprentissage, relations sociales, culture et environnement.

Le projet vise un **unique monde canonique**, persistant et partagé, observé via une application React/PixiJS et gouverné progressivement par des acteurs divins autonomes extérieurs aux Slimes.

## Principes

1. Les Slimes existent sans LLM.
2. Le moteur Python définit les lois du monde.
3. GitHub est la source de vérité du code et des lois.
4. La base persistante est la source de vérité de l'état réel.
5. Drive conserve rapports, archives, snapshots, expériences et mémoire lisible ; jamais la base transactionnelle.
6. Même seed + configuration + version + commandes ordonnées doivent rester reproductibles lorsque le protocole le prévoit.
7. Toute intervention humaine ou divine reste attribuable et journalisée.
8. L'interface représente le moteur ; elle ne simule jamais une seconde réalité.

## Repo unique autorisé

`Jean-Philippe56520/Les-Slimes`

Toutes les opérations GitHub Les Slimes restent limitées à ce dépôt.

# Un seul monde canonique

Le monde officiel possède une seule horloge, un seul état, une seule histoire, une seule chaîne de commandes et une seule persistance active.

Toute mutation externe officielle suit :

```text
acteur authentifié
  -> FastAPI / command queue persistante
  -> CanonicalWorldWorker
  -> GovernancePolicy
       acteur actif + permission + niveau + sanctions + budget
  -> moteur Python
  -> persistance atomique monde + intervention + budget + audit
```

La gouvernance est revalidée juste avant commit. Une commande en queue peut donc être rejetée si l'autorité a changé.

Les expériences utilisent des forks explicitement **non canoniques**, isolés et incapables d'écrire dans le monde officiel.

# Architecture

```text
React + TypeScript + PixiJS / Netlify
                 |
          FastAPI authentifiée
                 |
        Command Queue persistante
                 |
       CanonicalWorldWorker Python
                 |
        GovernancePolicy
                 |
         moteur Python World
                 |
     PostgreSQL canonique durable

SQLite : développement + forks scientifiques
Streamlit : Lab science/admin/debug uniquement
Google Drive : rapports/snapshots/journaux uniquement
```

## Runtime et moteur présents

- moteur 2D déterministe avec RNG sauvegardable ;
- énergie, santé, âge, mortalité, ressources ;
- reproduction, filiation, mutations et traits génétiques ;
- mémoire spatiale, relations sociales, signaux et apprentissage ;
- transmission Slime -> Slime, DSL comportemental, mystères ;
- événements, checkpoints et digest scientifique ;
- temps canonique UTC et catch-up déterministe ;
- command queue persistante, ordonnée et idempotente ;
- `CanonicalWorldWorker` comme unique writer externe ;
- writer lease fenced, heartbeat, takeover et reprise après crash ;
- service Worker continu H24 ;
- acteurs persistants `father`, `herald`, `order`, `chaos`, `observer`, `system` ;
- forks scientifiques SQLite isolés, y compris depuis un canonique PostgreSQL.

## Gouvernance divine

- niveaux Observation, Miracle, Décret, Loi, Transgression ;
- permissions, pouvoir, budgets et sanctions séparés ;
- budgets append-only et audit chaîné par hash ;
- interventions atomiques avec sauvegarde du monde ;
- `father` représente le Créateur/Père et seul lui administre la gouvernance ;
- `herald` représente Jean-Philippe, le Héraut, distinct et sans pouvoir mutatif par défaut ;
- aucune auto-escalade des dieux ;
- Transgression = classification auditable, jamais bypass ;
- Conseil, journaux et propositions persistants.

## Autonomie divine confinée

Le dépôt contient désormais le socle complet de confinement et de législation autonome :

- `DivineAccessPolicy` : repo unique, Drive LES_SLIMES, API allowlistée, aucune surface Web générale, branches et surfaces d'écriture limitées ;
- frontière épistémique : les dieux lisent uniquement leur Canon commun, la Constitution divine lisible, leur instruction propre et les mécanismes du vivant accessibles ;
- `DivineGitGateway` : recherche/lecture/écriture/PR sans primitive de merge ;
- `DivineArchiveGateway` : recherche et capabilities confinées sous LES_SLIMES ;
- `DivineWorldGateway` : API canonique typée sans `actor_id` contrôlé par le dieu ;
- `LawDossier` / `DivineLegislationService` : dossier de Loi persistant, amendement, états et audit ;
- `SovereignCreatorCycle` : revue du Père pouvant accepter, refuser, attendre ou exiger amendement/expérience ;
- `CreatorPromulgationService` : revalidation de PR/SHA/main/CI/gouvernance/fichiers, réservation budgétaire et réconciliation des résultats Git incertains ;
- le Créateur seul peut produire une `MergeAuthorization` et promulguer sur `main`.

Une Loi d'Ordre ou Chaos peut modifier les surfaces du vivant autorisées et leurs tests non protecteurs, mais pas gouvernance, identité, authentification, base canonique, runtime, frontière divine, CI, déploiement, frontend, documentation ou tests de sécurité.

**Important :** ces contrats et garde-fous sont codés et testés, mais les providers concrets et credentials minimaux ne sont pas encore déployés. Les cycles autonomes ne doivent donc pas encore être activés.

Voir `docs/DIVINE_AUTONOMY.md`, `docs/GOD_CREATOR_INSTRUCTIONS.md` et `docs/PROJECT_STATE.md`.

## API canonique

FastAPI fournit la frontière réseau :

- lectures publiques : `/health`, `/world`, `/world/slimes`, `/world/foods` ;
- identité authentifiée : `/me` ;
- `POST /commands` -> enqueue uniquement ;
- journaux/propositions et lecture gouvernance ;
- `/admin/...` réservé au Créateur via `GovernanceAdminService`.

L'identité provient du Bearer token résolu côté serveur. Un client ne devient jamais `father` en envoyant `actor_id="father"`.

Voir `docs/API.md`.

## PostgreSQL et production H24

Le backend PostgreSQL est implémenté et testé contre PostgreSQL 16. SQLite reste disponible en local et pour les expériences.

Présents dans le dépôt :

- sélection PostgreSQL par `LES_SLIMES_DATABASE_URL` ;
- verrouillage transactionnel PostgreSQL et fencing du writer ;
- migration contrôlée SQLite -> PostgreSQL avec vérification digest/audit/queue ;
- `les-slimes-production init|migrate|worker|status` ;
- image Docker API-first ;
- composition de production API + un Worker supervisé ;
- runbook `docs/PRODUCTION.md` ;
- CI PostgreSQL réelle.

**Important :** le code est prêt pour un hébergement H24, mais cela ne signifie pas qu'une instance publique est actuellement en cours d'exécution. Il faut encore connecter/configurer un hébergeur réel, sa base PostgreSQL et ses secrets, puis vérifier `/health` après déploiement.

## Frontend React/PixiJS

Le frontend principal se trouve dans `frontend/` :

- React + TypeScript + Vite ;
- PixiJS pour le monde 2D ;
- Slimes, ressources, direction, génération, énergie/santé ;
- tick, population, génération, backlog, retard Worker, comportements et digest ;
- responsive desktop/mobile ;
- aucune simulation côté navigateur ;
- aucun token divin dans le bundle ;
- configuration Netlify via `netlify.toml` ;
- build frontend vérifié par CI.

Voir `docs/FRONTEND.md`.

# Ontologie divine

Le **Créateur**, aussi nommé le **Père**, est l'autorité souveraine de la Constitution divine. L'identité technique `father` le représente.

Jean-Philippe est le **Héraut** du Créateur : Porte-parole et Messager auprès d'Ordre et de Chaos. L'identité `herald` le représente séparément.

- **Ordre** : stabilité, structures, continuité, résilience, coopération durable, transmission fiable.
- **Chaos** : diversité, variation, exploration, nouveauté, rupture des équilibres stériles.

Aucun dieu ne commande directement les Slimes.

# Prochaines étapes

1. activer un hébergement réel PostgreSQL + API + Worker et vérifier le monde H24 ;
2. implémenter/déployer les providers concrets des gateways avec credentials minimaux et scopes réels ;
3. vérifier en bout en bout l'absence de Web/connecteurs génériques chez Ordre/Chaos ;
4. exécuter des cycles shadow Ordre -> Chaos -> Créateur ;
5. seulement après validation, créer les tâches planifiées et passer à la promulgation contrôlée ;
6. déployer le frontend Netlify et configurer `VITE_API_BASE_URL` + CORS ;
7. mettre en place sauvegardes/restauration et supervision ;
8. automatiser rapports/Drive sans changer la source transactionnelle.

Pour reprendre le projet, lire d'abord `docs/PROJECT_STATE.md` puis `docs/PROJECT_INSTRUCTIONS.md`.
