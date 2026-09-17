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

Le monde canonique ne change jamais de mode. Les anciens modes globaux ont été supprimés. Les restrictions concernent les identités, permissions, budgets et sanctions des acteurs.

Toute mutation externe officielle suit :

```text
acteur
  -> permission
  -> command queue persistante
  -> CanonicalWorldWorker
  -> moteur Python
  -> persistance
```

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
        horloge + ticks + catch-up
          writer unique + audit
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
- writer lease exclusif ;
- command queue SQLite ordonnée et idempotente ;
- reprise après crash via événement `command_applied` ;
- acteurs persistants et permissions ;
- registre central de commandes ;
- commandes nourriture, signal, règles comportementales et mystères ;
- validation des payloads avant mise en queue ;
- provenance Observateur via `source_proposal_id` ;
- CLI mutatif routé par queue/worker ;
- Streamlit réduit à un Lab lecture/admin + enqueue ;
- Observer Inbox sans mutation directe de `World` ;
- tests empêchant la réintroduction des principaux contournements.

## Moteur déjà présent

Le moteur contient notamment : monde 2D continu, énergie/santé/âge/mortalité, ressources, reproduction/filiation/mutations, six traits génétiques, mémoire spatiale, relations sociales, signaux/apprentissage, transmission Slime -> Slime, DSL comportemental, mystères persistants, RNG sauvegardable, digest déterministe, événements/checkpoints et rapports analytiques.

# Gouvernance divine

Première phase : deux GPT Projects autonomes.

- **Ordre** : stabilité, structures, continuité, résilience, coopération durable, transmission fiable.
- **Chaos** : diversité, variation, exploration, nouveauté, rupture des équilibres stériles.

Aucun dieu ne commande directement les Slimes.

Niveaux de pouvoir : observation, miracle allowlisté, décret via DSL, loi moteur limitée, transgression interne rare et sanctionnable.

Jean-Philippe est le Père : budgets, récompenses, sanctions, permissions et Constitution divine.

# Persistance

Actuellement : SQLite transactionnel.

Production future : PostgreSQL durable après validation. Supabase reste une option, pas une obligation.

Google Drive n'est jamais utilisé comme base active.

# Prochaines étapes

1. formaliser les forks scientifiques non canoniques ;
2. durcir le World Worker H24 : heartbeat réel, supervision, reprise, concurrence ;
3. brancher budgets/sanctions/journaux divins ;
4. construire l'API Python ;
5. construire React + TypeScript + PixiJS ;
6. migrer ensuite vers une persistance PostgreSQL de production ;
7. créer Ordre/Chaos et leurs tâches planifiées lorsque la gouvernance est prête.

Pour reprendre le projet, lire d'abord `docs/PROJECT_STATE.md` puis `docs/PROJECT_INSTRUCTIONS.md`.
