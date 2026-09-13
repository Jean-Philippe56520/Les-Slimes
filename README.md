# Les Slimes — Artificial Life Lab

**Version actuelle : 0.9.0-alpha**

Les Slimes est un environnement de vie artificielle déterministe et persistant. Les créatures ne sont pas des prompts : elles possèdent un génome, une physiologie, une mémoire, des relations sociales et des apprentissages. Un Observateur LLM peut analyser la session et proposer des règles, événements ou mystères via une interface déclarative contrôlée.

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

En Sandbox, l'humain peut :

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

Le workflow est :

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
journal d'événements + SQLite
```

L'Observateur peut proposer :

- une observation ;
- une hypothèse ;
- une expérience ;
- un comportement déclaratif ;
- un événement de monde ;
- un mystère.

Il ne peut jamais exécuter du Python arbitraire ni écrire directement dans SQLite.

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

Le mode est inclus dans le digest d'état et persiste dans SQLite.

## Déterminisme et persistance

SQLite est la source de vérité locale. Sont sauvegardés :

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

Une simulation sauvegardée puis rechargée continue avec le même digest qu'une exécution ininterrompue.

## Installation

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

## Créer un monde

```bash
PYTHONPATH=src python -m les_slimes init \
  --db data/world.sqlite \
  --config config/default.yaml \
  --mode sandbox \
  --force
```

## Simuler

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

Ce fichier constitue l'entrée compacte destinée à l'Observateur LLM.

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

## Interaction CLI

```bash
PYTHONPATH=src python -m les_slimes signal \
  --db data/world.sqlite --signal S1 --x 60 --y 40 --radius 12

PYTHONPATH=src python -m les_slimes deposit-food \
  --db data/world.sqlite --x 60 --y 40 --count 5
```

## Interface Streamlit

```bash
streamlit run streamlit_app.py
```

L'interface affiche :

- le monde et ses ressources ;
- les mystères visibles ;
- la fiche de chaque Slime ;
- génome, souvenirs, relations et signaux appris ;
- culture et clusters sociaux ;
- candidats à l'émergence ;
- règles comportementales ;
- Inbox Observateur ;
- checkpoints et événements.

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

## Architecture

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

## Limites actuelles

- reproduction encore asexuée ;
- écologie volontairement abstraite ;
- signaux sémantiques limités à l'association nourriture ;
- pas encore de langage compositionnel ;
- pas encore de moteur graphique Phaser temps réel ;
- l'Observateur LLM est connecté par **rapport/proposition JSON**, pas encore par appel API automatique ;
- SQLite est persistant localement mais un déploiement Streamlit Cloud nécessite une base externe ou un stockage durable pour garantir la mémoire après redéploiement.

La prochaine étape vers V1.0 est le frontend temps réel + stockage serveur durable, sans modifier les lois du moteur validées ici.
