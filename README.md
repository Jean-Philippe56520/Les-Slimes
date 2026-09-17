# Les Slimes — monde de vie artificielle persistante

**Version actuelle : 0.9.0-alpha**

Les Slimes est un projet de vie artificielle déterministe. Les créatures ne sont pas des prompts : leur existence repose sur un moteur Python simulant biologie, génétique, perception, mémoire, apprentissage, relations sociales, culture et environnement.

Le cap V1.0 est un monde persistant dont le temps ne s'arrête jamais, observable comme une vraie application web animée, avec une gouvernance externe progressivement assurée par plusieurs assistants IA autonomes.

## Principes

1. Les Slimes existent sans LLM.
2. Le moteur Python reste l'autorité sur les lois du monde.
3. GitHub est la source de vérité du code et des lois.
4. La base persistante est la source de vérité de l'état réel du monde.
5. Drive conserve rapports, archives, snapshots, expériences et mémoire lisible des IA ; ce n'est jamais la base transactionnelle.
6. Même seed + configuration + version + commandes ordonnées doivent rester reproductibles lorsque le protocole le prévoit.
7. L'animation web représente le moteur ; elle ne simule jamais une seconde réalité.
8. Toute intervention humaine ou IA doit être attribuable et journalisée.
9. Les expériences verrouillées restent protégées de toute intervention.
10. Aucun agent IA autorisé sur Les Slimes ne peut agir sur un autre dépôt Git.

## Repo verrouillé

Le seul dépôt autorisé aux assistants Les Slimes est :

`Jean-Philippe56520/Les-Slimes`

Toute écriture GitHub automatisée doit cibler exactement ce dépôt. Les agents ne doivent jamais créer, modifier, supprimer, commenter, brancher ou pousser dans un autre repo.

Cette limitation est une méta-loi et n'est pas transgressable par un dieu.

## Ce qui fonctionne actuellement

Le moteur possède déjà notamment :

- monde 2D continu ;
- énergie, santé, âge, mortalité et ressources ;
- reproduction, filiation et mutations ;
- six traits génétiques ;
- mémoire spatiale ;
- relations sociales ;
- signaux symboliques neutres et apprentissage ;
- transmission Slime -> Slime ;
- règles comportementales déclaratives ;
- mystères persistants ;
- modes `sandbox`, `observation`, `experiment` ;
- SQLite transactionnel ;
- sauvegarde/restauration du RNG ;
- digest déterministe ;
- événements et checkpoints ;
- rapports analytiques ;
- Inbox Observateur ;
- tests de déterminisme et de persistance.

Le code courant implémente encore principalement un Observateur IA allowlisté. La gouvernance divine décrite ci-dessous est une cible à construire progressivement.

# Architecture cible

```text
                           Jean-Philippe
                              LE PERE
                                 |
                      +----------+----------+
                      |                     |
                  DIEU ORDRE            DIEU CHAOS
                      |                     |
                      +------ Conseil ------+
                                 |
                   propositions / actions /
                     décrets / lois / débats
                                 |
                                 v
+----------------------------------------------------------------+
|                    LES SLIMES PLATFORM                          |
|                                                                |
|  React + TypeScript + PixiJS                                   |
|  application principale, carte vivante animée                  |
|                   |                                            |
|                   v                                            |
|             API / Command Queue                                |
|                   |                                            |
|                   v                                            |
|            Python World Worker                                 |
|    horloge + ticks + catch-up + writer unique                  |
|                   |                                            |
|                   v                                            |
|          persistance canonique                                 |
|       SQLite dev -> PostgreSQL futur                           |
+----------------------------------------------------------------+
            |                              |
            v                              v
      Streamlit Lab                  Google Drive
 science / admin / debug        rapports / archives /
                               snapshots / Conseil IA
```

## Python World Worker

Le worker doit :

- posséder l'horloge canonique ;
- exécuter les ticks ;
- traiter les commandes dans un ordre stable ;
- être le seul écrivain logique du monde ;
- publier heartbeat/checkpoints ;
- reprendre après interruption ;
- rejouer exactement les ticks manquants.

Le temps biologique ne doit jamais dépendre d'une page web ouverte.

## Web App

L'interface principale cible devient :

- React ;
- TypeScript ;
- PixiJS ;
- déploiement Netlify.

Elle affichera les Slimes comme des créatures vivantes : déplacement interpolé, zoom, sélection individuelle, ressources, mystères, relations, lignées, événements et historique.

Le navigateur n'invente jamais un comportement. Il anime seulement les états calculés par Python.

## Streamlit

Streamlit devient **Les Slimes Lab** :

- métriques ;
- génomes ;
- lignées ;
- relations ;
- expériences ;
- déterminisme ;
- checkpoints ;
- administration ;
- diagnostic.

Il ne doit plus être la plateforme principale ni l'horloge du monde.

## Horloge et persistance

Persister au minimum :

- `tick_duration_seconds` ;
- `last_simulated_at_utc` ;
- `last_heartbeat_at_utc` ;
- worker/lease actif ;
- version Git ;
- digest.

Après une interruption, le runtime calcule le nombre exact de ticks dus et les rejoue dans l'ordre.

Dev/tests : SQLite.

Production future : PostgreSQL durable. Supabase reste une option, pas une dépendance obligatoire ; Netlify Database ou un autre PostgreSQL pourront être comparés lorsque la plateforme sera prête.

Drive peut conserver des snapshots cohérents, mais ne doit jamais héberger la base active comme mécanisme transactionnel.

# Gouvernance divine

La première phase comporte deux GPT Projects.

## Ordre

Affinités : stabilité, structures durables, coopération persistante, résilience, continuité, transmission fiable.

## Chaos

Affinités : diversité, variation, exploration, nouveauté, rupture de stagnation, création de niches.

Aucun dieu n'est « bon » ou « mauvais ». Leur doctrine influence leurs hypothèses, pas directement les Slimes.

## Niveaux de pouvoir cibles

1. **Observation** : lecture/analyse.
2. **Miracle** : primitive déjà prévue par le moteur.
3. **Décret** : règle via DSL existant.
4. **Loi** : modification limitée du moteur avec budget.
5. **Transgression** : modification exceptionnelle hors budget/autorité, obligatoirement attribuable, auditée et réversible.

Jean-Philippe est le Père. Il attribue budgets, récompenses, sanctions et domaines ; il peut restaurer ou annuler une loi.

Les méta-lois sont décrites dans `docs/DIVINE_GOVERNANCE.md`. Même une transgression ne permet jamais de toucher un autre repo, effacer l'historique, désactiver les tests, supprimer les sauvegardes, pousser des secrets ou augmenter ses propres droits.

## Conseil divin

Ordre et Chaos pourront :

- lire leurs journaux respectifs ;
- contester ou soutenir une proposition ;
- amender une loi ;
- produire une proposition commune ;
- demander une décision du Père ;
- rester en désaccord.

Un agent ne doit jamais inventer la position de l'autre : il doit lire sa contribution persistée.

## Tâches planifiées cibles

Chaque dieu aura au minimum :

### Cycle quotidien
1. vérifier `main` et les derniers commits ;
2. lire le dernier rapport du monde ;
3. lire son journal ;
4. lire le dernier journal de l'autre dieu ;
5. vérifier budgets, sanctions et mode ;
6. analyser ;
7. journaliser ;
8. éventuellement agir ou proposer ;
9. pouvoir conclure `aucune action`.

### Conseil hebdomadaire
1. relire sept jours ;
2. examiner les propositions de lois ;
3. lire les arguments de l'autre dieu ;
4. soutenir, rejeter ou amender ;
5. évaluer les conséquences des interventions ;
6. proposer éventuellement restauration/expérience/loi ;
7. solliciter le Père si nécessaire.

Les horaires d'Ordre et Chaos seront décalés.

## Changements de lois

Une modification substantielle doit normalement utiliser :

- `god/order/<slug>` ;
- `god/chaos/<slug>`.

Avant : `main` à jour, fichiers et tests concernés relus, hypothèse/risque/budget consignés.

Après : syntaxe/imports, tests ciblés, suite complète si moteur/RNG/DB/persistance, déterminisme/save-reload/digest si pertinent, contrôle du diff, auteur et motivation journalisés, push et vérification distante.

# Drive

Racine canonique :

`LES_SLIMES`
ID : `1NzXVNZTIiEeiJCehBfdBNASk3-JRSHFc`

Dossiers existants :

- `00_SYSTEM`
- `10_DAILY_REPORTS`
- `20_OBSERVER`
- `30_SNAPSHOTS`
- `40_EXPERIMENTS`
- `90_BILANS`

Le système sera étendu pour les journaux Ordre/Chaos, débats, propositions de lois et transgressions. Toute modification structurelle devra être reportée dans le manifest Drive.

# Documentation de référence

Avant une évolution significative :

- `README.md`
- `docs/PROJECT_INSTRUCTIONS.md`
- `docs/DIVINE_GOVERNANCE.md`
- `docs/SCIENTIFIC_PROTOCOL.md`
- `docs/OBSERVER_CONTRACT.md`
- `config/default.yaml`

Avant moteur/persistance :

- `src/les_slimes/world/engine.py`
- `src/les_slimes/database/sqlite_repo.py`
- `src/les_slimes/observer/proposals.py`
- modules métier concernés ;
- tests associés.

Instructions dédiées :

- `docs/GOD_ORDER_INSTRUCTIONS.md`
- `docs/GOD_CHAOS_INSTRUCTIONS.md`

# Roadmap

1. geler et mesurer la baseline ;
2. runtime H24 + horloge/catch-up ;
3. writer unique + command queue ;
4. React/TypeScript/PixiJS ;
5. API et intégration Netlify ;
6. endurance et sauvegardes Drive ;
7. gouvernance divine persistante ;
8. tâches planifiées Ordre/Chaos ;
9. budgets, sanctions, Conseil et transgressions ;
10. migration vers PostgreSQL distant lorsque nécessaire ;
11. snapshot `GENESIS` du premier monde canonique.

# Installation locale actuelle

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,dashboard]'
PYTHONPATH=src pytest
```

Sous Windows :

```powershell
.venv\Scripts\activate
pip install -e ".[dev,dashboard]"
$env:PYTHONPATH="src"
pytest
```

Créer un monde :

```bash
PYTHONPATH=src python -m les_slimes init --db data/world.sqlite --config config/default.yaml --mode sandbox --force
```

Simuler :

```bash
PYTHONPATH=src python -m les_slimes simulate --db data/world.sqlite --ticks 5000
```

Streamlit Lab actuel :

```bash
streamlit run streamlit_app.py
```

# Règle scientifique finale

L'objectif n'est pas de créer artificiellement des comportements spectaculaires.

Les Slimes doivent pouvoir surprendre les humains et les dieux.

Une observation ponctuelle n'est jamais une preuve d'émergence ; les interventions divines doivent elles-mêmes être considérées comme des facteurs expérimentaux.
