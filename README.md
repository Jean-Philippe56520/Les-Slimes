# Les Slimes — monde artificiel persistant

**Version actuelle : 0.9.0-alpha**

Les Slimes est un projet de vie artificielle déterministe et persistante. Les Slimes ne sont pas des prompts : ils existent dans un moteur Python simulant biologie, génétique, perception, mémoire, apprentissage, relations sociales, culture et environnement.

Le cap est de construire un **unique monde canonique**, persistant et partagé, visible comme une application web animée, gouverné progressivement par plusieurs assistants IA autonomes mais extérieurs aux Slimes.

## Principes

1. Les Slimes existent sans LLM.
2. Le moteur Python définit les lois du monde.
3. GitHub est la source de vérité du code et des lois.
4. La base persistante est la source de vérité de l'état réel du monde.
5. Drive conserve rapports, archives, snapshots, expériences et mémoire lisible des dieux ; jamais la base transactionnelle.
6. Même seed + configuration + version + commandes ordonnées doivent rester reproductibles lorsque le protocole le prévoit.
7. L'interface web représente le moteur ; elle ne simule jamais une seconde réalité.
8. Toute intervention humaine ou divine doit rester attribuable et journalisée.

## Repo unique autorisé aux agents

`Jean-Philippe56520/Les-Slimes`

Toutes les opérations GitHub des assistants Les Slimes doivent rester limitées à ce dépôt. Un accès technique éventuel à un autre repo ne constitue jamais une autorisation.

# Un seul monde canonique

Il existe un seul monde Les Slimes officiel et persistant.

Il possède :
- une horloge canonique ;
- un état officiel ;
- une histoire ;
- une chaîne de commandes ;
- une persistance active unique.

Le Père, Ordre, Chaos et tous les futurs dieux observent et influencent **ce même monde**.

Le monde canonique ne change pas de mode. Les restrictions concernent les permissions, budgets et sanctions des acteurs.

Les expériences, benchmarks et tests utilisent des copies/forks explicitement **non canoniques**, isolés et incapables d'écrire dans le monde officiel.

Le code actuel possède encore des notions `sandbox`, `observation` et `experiment` héritées du laboratoire initial. Elles sont considérées comme legacy à refactorer, pas comme l'architecture cible.

# Architecture cible

```text
                         Jean-Philippe
                            LE PERE
                               |
                    +----------+----------+
                    |                     |
                 ORDRE                  CHAOS
                    |                     |
                    +---- Conseil divin --+
                               |
                   commandes / lois / débats
                               |
                               v
+---------------------------------------------------------------+
|                   MONDE CANONIQUE LES SLIMES                  |
|                                                               |
| React + TypeScript + PixiJS                                   |
| carte vivante animée                                          |
|              |                                                |
|              v                                                |
| API / Command Queue                                           |
|              |                                                |
|              v                                                |
| Python World Worker                                           |
| horloge + ticks + catch-up + writer unique                    |
|              |                                                |
|              v                                                |
| persistance canonique                                         |
| SQLite maintenant -> PostgreSQL durable plus tard             |
+---------------------------------------------------------------+
        |                                      |
        v                                      v
 Streamlit Lab                           Google Drive
 science/admin/debug              rapports/snapshots/journaux
```

## Temps du monde

Le monde ne doit pas dépendre d'une page ouverte ni nécessairement d'un CPU actif en continu.

Il doit persister notamment :
- `tick_duration_seconds` ;
- `last_simulated_at_utc` ;
- version Git ;
- RNG ;
- digest.

Après interruption, le runtime calcule les ticks dus et les rejoue exactement dans l'ordre par batches bornés. Une optimisation ne doit jamais changer les lois du moteur.

## World Worker

Cible :
- horloge canonique ;
- exécution des ticks ;
- traitement déterministe des commandes ;
- writer unique ;
- heartbeat/checkpoints ;
- reprise/catch-up ;
- rapports ;
- sauvegardes.

## Application web

Le frontend principal cible est :
- React ;
- TypeScript ;
- PixiJS ;
- Netlify pour le frontend.

PixiJS anime visuellement les positions/états calculés par Python. Le navigateur ne décide jamais du comportement réel des Slimes.

Streamlit reste un laboratoire scientifique secondaire.

# Persistance

Actuellement : SQLite transactionnel.

Production future : PostgreSQL durable après validation. Supabase reste une option, pas une obligation.

Google Drive n'est jamais utilisé comme base active. Il sert aux rapports, archives, snapshots, expériences et mémoire externe des dieux.

# Gouvernance divine

Première phase : deux GPT Projects autonomes.

## Ordre

Favorise stabilité, structures, continuité, résilience, coopération durable et transmission fiable.
Risques : rigidité, homogénéisation, stagnation.

## Chaos

Favorise diversité, variation, exploration, nouveauté et rupture des équilibres stériles.
Risques : instabilité, bruit, pertes de lignées, emballements.

Aucun dieu n'est intrinsèquement bon ou mauvais. Sa doctrine oriente ses hypothèses mais ne commande jamais directement les Slimes.

### Niveaux de pouvoir

1. Observation.
2. Miracle : primitive moteur existante.
3. Décret : règle via DSL.
4. Loi : modification limitée du moteur avec budget.
5. Transgression : modification interne hors budget/autorité, rare et sanctionnable.

Jean-Philippe est le Père : budgets, récompenses, sanctions, permissions et Constitution divine.

Les méta-lois de sécurité, l'audit, les sauvegardes, l'identité des auteurs et le confinement au repo ne sont pas des jouets du système divin.

Voir :
- `docs/PROJECT_INSTRUCTIONS.md`
- `docs/DIVINE_GOVERNANCE.md`
- `docs/GOD_ORDER_INSTRUCTIONS.md`
- `docs/GOD_CHAOS_INSTRUCTIONS.md`
- `docs/PROJECT_STATE.md`

# Ce qui fonctionne aujourd'hui

Le moteur possède déjà notamment :
- monde 2D continu ;
- énergie, santé, âge, mortalité et ressources ;
- reproduction, filiation et mutations ;
- six traits génétiques ;
- mémoire spatiale ;
- relations sociales ;
- signaux symboliques et apprentissage ;
- transmission Slime -> Slime ;
- règles comportementales déclaratives ;
- mystères persistants ;
- SQLite transactionnel ;
- sauvegarde/restauration RNG ;
- digest déterministe ;
- événements/checkpoints ;
- rapports analytiques ;
- Inbox Observateur ;
- tests de déterminisme/persistance.

## Écart actuel vers la cible

Le code actuel est encore un laboratoire :
- pas encore de runtime canonique H24/catch-up final ;
- Streamlit peut encore muter directement le monde ;
- pas encore de command queue canonique complète ;
- pas encore de React/PixiJS ;
- pas encore de gouvernance divine persistée ;
- Ordre et Chaos ne sont pas encore créés comme GPT Projects autonomes ;
- leurs tâches planifiées ne sont pas encore créées ;
- les modes legacy sont encore présents dans le code ;
- PostgreSQL distant n'est pas encore choisi.

# Prochaine étape recommandée

Avant de construire l'interface graphique :

1. geler/retester la baseline ;
2. concevoir `advance_to(target_time)` et le catch-up déterministe ;
3. ajouter writer unique + command queue idempotente ;
4. modéliser identité/budgets/sanctions/journaux des dieux ;
5. refactorer les modes legacy vers permissions acteurs + forks d'expériences ;
6. seulement ensuite construire API puis React/PixiJS ;
7. créer Ordre/Chaos et leurs tâches planifiées quand la couche de gouvernance sait réellement les accueillir.

Pour reprendre le projet dans une nouvelle conversation, lire d'abord `docs/PROJECT_STATE.md` puis `docs/PROJECT_INSTRUCTIONS.md`.
