# Les Slimes — monde artificiel persistant

**Version actuelle : 0.9.0-alpha**

Les Slimes est un projet de vie artificielle déterministe et persistante. Les Slimes ne sont pas des prompts : ils existent dans un moteur Python simulant biologie, génétique, perception, mémoire, apprentissage, relations sociales, culture et environnement.

Le cap est un **unique monde canonique**, persistant et partagé, visible comme une application web animée, gouverné progressivement par plusieurs assistants IA autonomes mais extérieurs aux Slimes.

## Principes

1. Les Slimes existent sans LLM.
2. Le moteur Python définit les lois du monde.
3. GitHub est la source de vérité du code et des lois.
4. La base persistante est la source de vérité de l'état réel du monde.
5. Drive conserve rapports, archives, snapshots, expériences et mémoire lisible des dieux ; jamais la base transactionnelle.
6. Même seed + configuration + version + commandes ordonnées doivent rester reproductibles lorsque le protocole le prévoit.
7. Toute intervention humaine ou divine doit rester attribuable et journalisée.
8. L'interface représente le moteur ; elle ne simule jamais une seconde réalité.

## Repo unique autorisé aux agents

`Jean-Philippe56520/Les-Slimes`

Toutes les opérations GitHub des assistants Les Slimes restent limitées à ce dépôt.

# Un seul monde canonique

Le monde officiel possède une seule horloge, un seul état, une seule histoire, une seule chaîne de commandes et une seule persistance active.

Le monde canonique ne change jamais de mode. Les restrictions concernent les identités, permissions, niveaux de pouvoir, budgets et sanctions des acteurs.

Toute mutation externe officielle suit :

```text
acteur
  -> command queue persistante
  -> CanonicalWorldWorker
  -> GovernancePolicy
       acteur actif + permission + niveau + sanctions + budget
  -> moteur Python
  -> persistance atomique monde + intervention + budget + audit
```

La gouvernance est vérifiée à l'exécution puis revalidée juste avant commit. Une commande peut donc être mise en queue puis rejetée si l'autorité a changé ; ce refus reste auditable.

Les expériences, benchmarks et tests utilisent des copies/forks explicitement **non canoniques**, isolés et incapables d'écrire dans le monde officiel.

# Architecture cible

```text
React + TypeScript + PixiJS / Netlify
                 |
                API
                 |
        Command Queue persistante
                 |
       CanonicalWorldWorker Python
                 |
        GovernancePolicy
                 |
         moteur Python World
                 |
        persistance canonique
      SQLite -> PostgreSQL durable

Streamlit Lab : science/admin/debug uniquement
Google Drive : rapports/snapshots/journaux uniquement
```

## Runtime déjà présent

- `tick_duration_seconds` et métadonnées UTC ;
- `CanonicalRuntime.advance_to(target_time)` ;
- catch-up déterministe ;
- command queue SQLite ordonnée, idempotente et paginée ;
- acteurs persistants et permissions ;
- registre central de commandes ;
- commandes nourriture, signal, règles comportementales et mystères ;
- validation des payloads avant mise en queue ;
- provenance Observateur via `source_proposal_id` ;
- CLI mutatif routé par queue/worker ;
- Streamlit réduit à un Lab lecture/admin + enqueue ;
- Observer Inbox sans mutation directe de `World` ;
- forks scientifiques isolés et explicitement non canoniques ;
- writer lease fenced avec token + génération ;
- séparation temps simulé / wall-clock du processus ;
- heartbeat réel entre batches et pendant l'idle ;
- garde transactionnel empêchant un writer zombie de committer ;
- `CanonicalWorkerService` pour boucle H24 sur hôte unique ;
- `worker-run` et `worker-status` ;
- health runtime : tick, retard, ticks dus, backlog et lease ;
- reprise après crash via événement `command_applied` et takeover du lease ;
- tests de concurrence et de digest crash/takeover == exécution continue.

## Gouvernance divine déjà présente

- niveaux : Observation, Miracle, Décret, Loi, Transgression ;
- permissions techniques séparées du niveau de pouvoir ;
- budgets append-only : miracle, législatif, faveur, dette de transgression ;
- sanctions déclaratives et temporaires ;
- `GovernancePolicy` centrale ;
- double autorisation pour les propositions de l'Observateur ;
- intervention attribuée pour chaque mutation divine ;
- débit budget + audit + sauvegarde du monde atomiques ;
- aucun double débit après crash/replay ;
- audit chaîné par hash ;
- journaux, propositions et Conseil divin persistants ;
- seul le Père peut modifier permissions, pouvoirs, budgets et sanctions ;
- aucune commande permettant à un dieu d'augmenter ses propres droits ;
- la Transgression n'est pas un bypass automatique ;
- la gouvernance reste hors du digest biologique ;
- les forks scientifiques ne recopient pas la gouvernance active ;
- administration via CLI Père, affichage lecture seule dans le Lab.

## Moteur déjà présent

Le moteur contient notamment : monde 2D continu, énergie/santé/âge/mortalité, ressources, reproduction/filiation/mutations, six traits génétiques, mémoire spatiale, relations sociales, signaux/apprentissage, transmission Slime -> Slime, DSL comportemental, mystères persistants, RNG sauvegardable, digest déterministe, événements/checkpoints et rapports analytiques.

# Gouvernance divine

Première phase : deux GPT Projects autonomes.

- **Ordre** : stabilité, structures, continuité, résilience, coopération durable, transmission fiable.
- **Chaos** : diversité, variation, exploration, nouveauté, rupture des équilibres stériles.

Aucun dieu ne commande directement les Slimes.

Jean-Philippe est le Père : budgets, récompenses, sanctions, permissions et Constitution divine.

# Persistance

Actuellement : SQLite transactionnel.

Le runtime SQLite est conçu pour un fonctionnement continu contrôlé sur un hôte unique. La production publique H24 demandera encore une persistance PostgreSQL durable, une supervision/orchestration du worker et une stratégie opérationnelle de sauvegarde/reprise.

Supabase reste une option, pas une obligation.

Google Drive n'est jamais utilisé comme base active.

# Prochaines étapes

1. construire l'API Python/FastAPI et l'authentification Père/acteurs ;
2. construire React + TypeScript + PixiJS ;
3. migrer vers une persistance PostgreSQL durable ;
4. définir le déploiement et la supervision du worker canonique ;
5. automatiser rapports/Drive ;
6. créer Ordre/Chaos et leurs tâches planifiées ;
7. exporter journaux/Conseil vers Drive sans changer la source transactionnelle.

Pour reprendre le projet, lire d'abord `docs/PROJECT_STATE.md` puis `docs/PROJECT_INSTRUCTIONS.md`.
