# Architecture V0.1

## Principe

Les Slimes existent sans LLM. Le moteur Python est l'autorité sur les lois physiques et biologiques. SQLite est l'autorité sur l'état persistant.

```text
UI / Streamlit
      |
      v
Simulation Python -----> Event log
      |                    |
      v                    v
  World state --------> SQLite
      |
      +--> Biology
      +--> Genetics
      +--> Memory
      +--> Spatial index
```

## Cycle d'un tick

1. régénération éventuelle d'une ressource ;
2. vieillissement ;
3. évaluation faim/satiété ;
4. perception locale ;
5. consultation éventuelle de la mémoire ;
6. choix de direction ;
7. déplacement ;
8. dépense énergétique ;
9. alimentation éventuelle ;
10. santé/mortalité ;
11. reproduction éventuelle ;
12. émission d'événements.

## Déterminisme

Le monde utilise une instance dédiée de `random.Random`. Son état interne est sauvegardé dans SQLite avec le reste du monde. Un reload ne réinitialise jamais le RNG.

Le `state_digest()` encode les états biologiques, génomes, souvenirs, ressources, compteurs et l'état RNG dans une représentation canonique puis calcule un SHA-256.

## Persistance

La sauvegarde est transactionnelle : état courant, souvenirs, ressources, événements et checkpoint sont écrits dans une transaction SQLite `BEGIN IMMEDIATE`.

## Performance

Les ressources utilisent une grille spatiale. Un Slime ne scanne donc pas l'ensemble des ressources du monde à chaque tick.

## Frontières V0.1

Pas encore de :

- mémoire épisodique générale ;
- relations sociales ;
- culture ;
- langage ;
- agent LLM ;
- modification autonome des règles ;
- moteur graphique Phaser.
