# Les Slimes — Artificial Life Lab

**Version actuelle : 0.9.0-alpha**

Les Slimes est un environnement de vie artificielle déterministe et persistant. Les créatures ne sont pas des prompts : elles possèdent un génome, une physiologie, une mémoire, des relations sociales et des apprentissages. Un Observateur LLM peut analyser le monde et proposer des règles, événements ou mystères via une interface déclarative contrôlée.

L'objectif V1.0 est désormais de transformer le laboratoire actuel en **monde artificiel persistant fonctionnant 24 h/24**, indépendamment de l'ouverture de Streamlit ou de la présence d'un LLM.

## Principes non négociables

1. Les Slimes existent sans LLM.
2. Le moteur Python est l'autorité sur les lois biologiques et comportementales.
3. GitHub est la source de vérité du code.
4. La base persistante est la source de vérité du monde et de son histoire.
5. Streamlit est une interface d'observation et de commande, jamais l'horloge du monde.
6. Google Drive est destiné aux rapports, archives, snapshots et échanges avec l'Observateur, jamais à la base active.
7. Toute intervention IA passe par : analyse -> proposition déclarative -> validation -> allowlist -> application par le moteur -> journalisation.
8. Les modes `observation` et `experiment` restent non modifiables par l'humain ou l'IA.
9. Même seed + même configuration + même version + mêmes commandes ordonnées doivent rester reproductibles lorsque le protocole le prévoit.

## Ce qui fonctionne aujourd'hui

### Vie artificielle

- monde 2D continu ;
- énergie, santé, âge, satiété et mortalité ;
- ressources alimentaires et pression écologique ;
- reproduction, filiation et mutations ;
- 6 traits génétiques : vitesse, métabolisme, perception, fertilité, curiosité, sociabilité ;
- mémoire spatiale des ressources avec renforcement et oubli ;
- génération et lignées.

### Société et culture

- relations de familiarité/confiance ;
- mémoire sociale bornée pour rester scalable ;
- attraction vers des individus familiers ;
- quatre signaux symboliques neutres `S1..S4` ;
- association apprise `signal -> nourriture` ;
- extinction d'une association non récompensée ;
- réponse comportementale à un signal appris ;
- émission d'un signal appris par un Slime ;
- transmission Slime -> Slime testée automatiquement.

### Interaction humaine

En Sandbox, l'humain peut actuellement :

- déposer de la nourriture ;
- émettre S1..S4 ;
- entraîner progressivement une association ;
- observer les individus, souvenirs, relations et apprentissages.

### Émergence

Le moteur calcule notamment :

- distributions génétiques ;
- adoption des signaux ;
- clusters sociaux ;
- individus socialement centraux ;
- candidats heuristiques à l'émergence.

Une détection n'est jamais présentée comme une preuve scientifique : elle doit être reproduite sur plusieurs seeds/conditions.

### Observateur IA sécurisé

Le workflow actuel est :

```text
Simulation
   ↓
rapport structuré
   ↓
LLM / analyste
   ↓
proposition JSON
   ↓
validation allowlist
   ↓
Inbox Observateur
   ↓
application contrôlée en Sandbox
   ↓
journal d'événements + persistance
```

L'Observateur peut proposer :

- une observation ;
- une hypothèse ;
- une expérience ;
- un comportement déclaratif ;
- un événement de monde ;
- un mystère.

Il ne peut jamais exécuter du Python arbitraire ni écrire directement dans la base du monde.

### Mystères

Un mystère est un objet persistant dont l'effet est masqué dans l'interface publique. Effets allowlistés actuels :

- variation d'énergie ;
- variation de santé ;
- amplification de souvenirs ;
- impulsion de signal.

Les activations et découvertes sont journalisées.

## Modes

- `sandbox` : interactions et propositions applicables ;
- `observation` : monde lisible/exécutable, interventions verrouillées ;
- `experiment` : environnement verrouillé destiné aux expériences reproductibles.

Le mode est inclus dans le digest d'état et persiste avec le monde.

## Déterminisme et persistance actuels

SQLite est actuellement la source de vérité locale. Sont sauvegardés :

- Slimes et génomes ;
- souvenirs ;
- relations sociales ;
- apprentissages de signaux ;
- signaux récemment entendus ;
- ressources ;
- règles comportementales ;
- mystères et états de découverte ;
- propositions Observateur ;
- événements et checkpoints ;
- état exact du générateur pseudo-aléatoire.

Une simulation sauvegardée puis rechargée doit continuer avec le même digest qu'une exécution ininterrompue.

# Cap V1.0 — Monde persistant 24 h/24

## Architecture cible

```text
                         Jean-Philippe
                              |
                              v
                     Streamlit / Lab
                    lecture + commandes
                              |
                              v
                  Command Queue persistante
                              |
                              v
+---------------------------------------------------------+
|                  HOTE TOUJOURS ACTIF                    |
|                                                         |
|     Python World Worker                                 |
|     - horloge de simulation                             |
|     - rattrapage après interruption                     |
|     - validation des commandes                          |
|     - seul écrivain logique du monde                    |
|     - checkpoints / rapports                            |
|                |                                        |
|                v                                        |
|       Repository de persistance                         |
+----------------+----------------------------------------+
                 |
                 | production après validation
                 v
          Supabase PostgreSQL
          état durable du monde
                 |
                 +--------------------+
                 |                    |
                 v                    v
          rapports quotidiens    snapshots / exports
                 |                    |
                 +---------> Google Drive
                                   |
                                   v
                         Observateur ChatGPT
                         analyse quotidienne
                                   |
                         propositions allowlistées
                                   |
                                   v
                            Command Queue
```

### Rôle de chaque composant

**World Worker**

- tourne indépendamment de Streamlit ;
- avance le monde en ticks ;
- possède l'horloge canonique ;
- traite les commandes dans un ordre déterministe ;
- sauvegarde et checkpoint le monde ;
- génère les rapports quotidiens ;
- publie un heartbeat ;
- reprend automatiquement après interruption.

**Streamlit**

- observe le monde ;
- affiche métriques, Slimes, histoire et santé du worker ;
- dépose des commandes ;
- ne doit plus appeler directement `World.step()` en production ;
- ne doit jamais être nécessaire à la survie du monde.

**Supabase PostgreSQL — cible production**

- devient la persistance durable distante seulement après migration validée ;
- stocke état, commandes, événements, checkpoints et métadonnées runtime ;
- ne remplace pas le moteur Python ;
- ne maintient pas Streamlit artificiellement éveillé ;
- n'exécute pas la biologie des Slimes.

**Google Drive**

- rapports quotidiens ;
- snapshots et archives exportées ;
- journal lisible de l'Observateur ;
- bilans destinés à Jean-Philippe ;
- jamais base transactionnelle active.

**ChatGPT / Observateur**

- intervient périodiquement, par exemple une fois par 24 h ;
- lit les métriques et événements produits par le moteur ;
- distingue observation, corrélation, hypothèse, expérience et conclusion ;
- peut ne rien proposer si aucune intervention n'est justifiée ;
- ne modifie jamais directement la base ;
- ne modifie jamais le code moteur automatiquement ;
- soumet uniquement des propositions déclaratives compatibles avec le mode et l'allowlist.

## Horloge de simulation

Le monde doit conserver une correspondance explicite entre temps réel et ticks, par exemple au lancement expérimental :

```text
1 tick = 60 secondes réelles
```

Cette valeur doit être configurable et persistée.

Le runtime conserve notamment :

- `tick_duration_seconds` ;
- `last_simulated_at_utc` ;
- `last_heartbeat_at_utc` ;
- `worker_id` / lease ;
- version Git du moteur ;
- digest du dernier état sauvegardé.

Au redémarrage, le worker calcule les ticks manquants à partir du dernier temps canonique, puis les exécute par lots bornés. Une interruption de l'hébergement ne doit donc pas créer une interruption biologique silencieuse.

Le rattrapage doit préserver l'ordre exact des ticks et des commandes. Une optimisation de rattrapage ne peut pas remplacer plusieurs ticks par une approximation si cela change les lois du moteur.

## Writer unique et file de commandes

En production, le worker est le seul composant autorisé à appliquer des mutations du monde.

Streamlit et l'Observateur déposent des commandes persistantes telles que :

```text
deposit_food
emit_signal
apply_observer_proposal
add_mystery
```

Chaque commande doit porter au minimum :

- un identifiant stable ;
- une source ;
- un timestamp UTC ;
- un payload validable ;
- une clé d'idempotence ;
- un statut `pending/applied/rejected` ;
- le tick d'application éventuel ;
- le résultat ou motif de rejet.

Le worker trie et applique les commandes selon une règle stable et testée.

## Sécurité du worker

Le lancement H24 doit empêcher deux workers d'écrire simultanément le même monde.

Prévoir :

- lease/lock persistant avec expiration ;
- heartbeat ;
- reprise contrôlée ;
- idempotence des commandes ;
- transactions ;
- arrêt propre ;
- détection d'un digest incohérent ;
- journalisation de toute reprise ou erreur runtime.

## Observateur quotidien

Toutes les 24 h, le moteur produit un paquet de télémétrie immuable contenant au minimum :

- fenêtre temporelle et ticks couverts ;
- version Git ;
- configuration ;
- seed ;
- digest initial/final ;
- population, naissances, morts et générations ;
- évolution génétique ;
- lignées ;
- ressources ;
- apprentissages ;
- signaux ;
- relations et clusters ;
- anomalies statistiques ;
- mystères et découvertes ;
- interventions humaines/IA de la période.

L'Observateur peut produire :

1. observations ;
2. hypothèses ;
3. propositions d'expérience ;
4. éventuellement une intervention Sandbox allowlistée.

Les changements de lois du moteur restent hors de cette boucle quotidienne. Ils nécessitent une proposition structurée, une décision avec Jean-Philippe, une modification Git, des tests et une nouvelle version documentée.

## Budget d'intervention IA

Avant activation de l'Observateur automatique, définir une politique persistée et versionnée, par exemple :

- nombre maximal d'interventions par période ;
- types autorisés ;
- amplitudes maximales ;
- cooldown des mystères ;
- interdiction de modification génétique directe ;
- interdiction de naissance/mort forcée ;
- aucune intervention en `observation` ou `experiment` ;
- possibilité explicite de ne rien faire.

La politique exacte sera validée avant le premier monde canonique.

# Plan d'implémentation

## Phase 0 — Geler la baseline

Avant toute modification runtime :

- exécuter la suite de tests actuelle ;
- mesurer le benchmark actuel ;
- enregistrer un digest de référence ;
- vérifier `save -> reload -> digest` ;
- documenter la version Git de baseline.

**Critère de sortie :** baseline reproductible et mesurée.

## Phase 1 — Runtime H24 local

Créer un module runtime spécialisé sans déplacer la logique métier hors de `world/` :

```text
src/les_slimes/runtime/
├── __init__.py
├── clock.py
└── worker.py
```

Fonctions attendues :

- horloge configurable ;
- boucle worker ;
- traitement par batches ;
- heartbeat ;
- arrêt propre ;
- rattrapage après interruption ;
- limites de catch-up pour éviter une charge incontrôlée.

Ajouter les métadonnées runtime à la persistance SQLite locale.

**Critère de sortie :** test automatisé démontrant qu'une interruption suivie d'un rattrapage produit le même digest qu'une exécution continue équivalente.

## Phase 2 — Writer unique et commandes

Ajouter une command queue persistante.

Refactorer Streamlit afin que :

- l'UI n'avance plus directement le monde en mode production ;
- les interactions deviennent des commandes ;
- le worker soit le seul applicateur des commandes.

Ajouter :

- idempotence ;
- ordre stable ;
- rejets documentés ;
- tests de concurrence et de double application.

**Critère de sortie :** aucune double application d'une même commande et digest stable après reload.

## Phase 3 — Conteneurs et endurance locale

Faire évoluer Docker Compose vers au moins :

```text
slimes-worker
slimes-web
```

avec stockage persistant partagé pour la phase SQLite locale.

Tests obligatoires :

- redémarrage worker ;
- redémarrage machine/containers ;
- coupure simulée ;
- rattrapage ;
- 24 h puis 48 h d'endurance ;
- taille de DB ;
- temps par tick ;
- croissance des événements ;
- CPU/RAM ;
- cohérence des digests/checkpoints.

**Critère de sortie :** monde test stable au moins 48 h avec reprises contrôlées.

## Phase 4 — Gate Supabase production

**Cette phase ne démarre pas tant qu'un projet Supabase dédié `Les Slimes` n'est pas disponible.**

Jean-Philippe est actuellement au maximum de projets disponibles sur son offre ; avant cette phase il faudra débloquer un projet supplémentaire, notamment via le passage au plan adapté.

Le code des phases 0 à 3 ne doit pas dépendre de cette disponibilité.

Une fois le projet créé :

- relever la configuration réelle du projet ;
- vérifier la documentation Supabase courante ;
- concevoir le schéma PostgreSQL ;
- sécuriser les schémas exposés et RLS si une Data API est utilisée ;
- ne jamais exposer une clé `service_role` dans Streamlit public ;
- implémenter un repository PostgreSQL compatible avec les invariants du moteur ;
- migrer un monde de test ;
- comparer les digests et historiques ;
- tester reprise, commandes et transactions ;
- seulement ensuite choisir Supabase comme persistance canonique de production.

Il ne doit jamais exister une période ambiguë où SQLite et PostgreSQL sont simultanément considérés comme deux sources de vérité du même monde.

**Critère de sortie :** migration testée et déterminisme/reload validés.

## Phase 5 — Hébergement permanent

Déployer le `slimes-worker` sur un hôte réellement toujours actif.

Contraintes :

- redémarrage automatique ;
- stockage durable ;
- logs ;
- healthcheck ;
- secrets hors Git ;
- accès réseau minimal ;
- sauvegardes vérifiées.

Streamlit peut rester séparé du worker : son sommeil ou son redémarrage ne doit jamais arrêter le monde.

**Critère de sortie :** worker distant H24 stable, observable et récupérable.

## Phase 6 — Drive et archives

Créer un Drive dédié aux Slimes avec une arborescence stable, par exemple :

```text
LES_SLIMES/
├── 00_SYSTEM/
├── 10_DAILY_REPORTS/
├── 20_OBSERVER/
│   ├── inbox/
│   ├── applied/
│   ├── rejected/
│   └── journal/
├── 30_SNAPSHOTS/
├── 40_EXPERIMENTS/
└── 90_BILANS/
```

Exporter automatiquement les rapports et snapshots selon une politique de rétention.

Drive reste une archive/exchange layer, pas une base transactionnelle.

**Critère de sortie :** restauration testée depuis une sauvegarde et rapport quotidien consultable.

## Phase 7 — Observateur ChatGPT quotidien

Configurer une exécution quotidienne qui :

1. lit le dernier rapport et l'historique utile ;
2. analyse les changements ;
3. classe ses conclusions par niveau de preuve ;
4. écrit son journal ;
5. propose éventuellement une intervention déclarative ;
6. respecte le budget d'intervention et le mode du monde ;
7. ne modifie jamais le moteur automatiquement.

**Critère de sortie :** plusieurs cycles quotidiens consécutifs entièrement journalisés et réversibles.

## Phase 8 — Premier monde canonique

Avant lancement :

- figer la version moteur ;
- figer la configuration ;
- fixer l'échelle temps réel/tick ;
- fixer le seed ;
- fixer la politique Observateur ;
- vérifier sauvegarde/restauration ;
- vérifier dashboards et alertes ;
- enregistrer le digest initial ;
- créer un snapshot `GENESIS`.

Après cela seulement, le monde principal peut être déclaré persistant.

# Installation actuelle

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,dashboard]'
```

Sous Windows :

```powershell
.venv\Scripts\activate
pip install -e ".[dev,dashboard]"
```

## Créer un monde local

```bash
PYTHONPATH=src python -m les_slimes init \
  --db data/world.sqlite \
  --config config/default.yaml \
  --mode sandbox \
  --force
```

## Simuler manuellement

```bash
PYTHONPATH=src python -m les_slimes simulate \
  --db data/world.sqlite \
  --ticks 5000
```

## Rapport Observateur

```bash
PYTHONPATH=src python -m les_slimes report \
  --db data/world.sqlite \
  --output observer_report.json
```

## Importer une proposition IA

```bash
PYTHONPATH=src python -m les_slimes proposal-import \
  --db data/world.sqlite \
  --file examples/observer_behavior_proposal.json
```

Lister :

```bash
PYTHONPATH=src python -m les_slimes proposal-list --db data/world.sqlite
```

Appliquer une proposition validée :

```bash
PYTHONPATH=src python -m les_slimes proposal-apply \
  --db data/world.sqlite \
  --id 1
```

Les propositions mutantes ne sont applicables qu'en Sandbox.

## Interface Streamlit actuelle

```bash
streamlit run streamlit_app.py
```

L'interface affiche notamment le monde, les ressources, les Slimes, génomes, souvenirs, relations, apprentissages, clusters, règles, Inbox Observateur, checkpoints et événements.

## Expériences multi-seeds

```bash
PYTHONPATH=src python scripts/run_experiment.py \
  --ticks 10000 \
  --seeds 428719 9137 20260913 \
  --name baseline
```

Résultats CSV + JSON dans `experiments/results/`.

## Tests

```bash
PYTHONPATH=src pytest
```

La suite couvre notamment : déterminisme, reprise SQLite, biologie, mémoire, culture, transmission Slime -> Slime, modes, expériences, règles déclaratives, Inbox Observateur et mystères.

# Architecture du code actuelle

```text
src/les_slimes/
├── analytics/      # émergence et rapport Observateur
├── biology/        # génétique
├── cognition/      # mémoire + DSL de comportements
├── database/       # SQLite transactionnel
├── experiments/    # batch multi-seeds
├── observer/       # validation/application des propositions IA
├── world/          # moteur, spatialisation, modes, mystères
├── cli.py
├── config.py
├── entities.py
└── events.py

dashboard/          # Streamlit
config/             # lois du monde
examples/           # propositions Observateur
schemas/            # contrat JSON
tests/              # invariants scientifiques/techniques
```

Le futur module `runtime/` ne doit contenir que l'orchestration temporelle et opérationnelle. Les lois des Slimes restent dans les modules métier existants.

# Limites actuelles

- le monde n'est pas encore exécuté par un worker H24 ;
- Streamlit peut encore faire avancer la simulation directement ;
- SQLite est uniquement local ;
- le projet Supabase de production n'est pas encore disponible ;
- Drive n'est pas encore connecté au pipeline quotidien ;
- l'Observateur LLM n'est pas encore exécuté automatiquement chaque jour ;
- reproduction encore asexuée ;
- écologie volontairement abstraite ;
- signaux sémantiques limités à l'association nourriture ;
- pas encore de langage compositionnel ;
- pas encore de moteur graphique Phaser temps réel.

La prochaine étape est **Phase 0 puis Phase 1 : geler la baseline et construire le runtime H24 local**, sans attendre Supabase et sans modifier les lois biologiques validées.