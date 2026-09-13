# Validation — 0.9.0-alpha

## Suite automatisée

**23 tests** au dernier passage de validation, couvrant :

- même seed -> même état ;
- sauvegarde/reprise SQLite exacte ;
- famine et mortalité ;
- reproduction/filiation ;
- mémoire et capacité bornée ;
- alignement YAML/Python ;
- apprentissage signal -> nourriture ;
- relations sociales ;
- transmission Slime -> Slime ;
- détection de signal partagé ;
- modes Observation/Experiment ;
- persistance du mode ;
- expériences multi-seeds reproductibles ;
- DSL de comportements + validation ;
- persistance des règles ;
- Inbox Observateur ;
- mystères + persistance + proposition IA.

## Baseline complète finale

Seed `428719` :

- 5 000 ticks : 150 Slimes, 57 naissances, 7 décès ;
- 10 000 ticks : 136 Slimes, 85 naissances, 49 décès ;
- 20 000 ticks : 107 Slimes, 164 naissances, 157 décès, génération max 4 ;
- 30 000 ticks : 138 Slimes, 266 naissances, 228 décès, génération max 5.

À 30 000 ticks :

- temps observé dans l'environnement de construction : 32,349 s ;
- digest : `e36c0bcf9a7d000efc3b4fcaed1493854a00c4e25fdb74a3530b094c58cd3acf` ;
- sauvegarde/rechargement : digest strictement identique.

## Contrôles indépendants à 20 000 ticks

Seed `9137` :

- population 119 ;
- naissances 170 ;
- décès 151 ;
- génération max 5 ;
- digest `7661e7d21e92d7df8c390fe513efeb81b9fc3703688e47ad19ec8dfbbaef79c9`.

Seed `20260913` :

- population 124 ;
- naissances 193 ;
- décès 169 ;
- génération max 5 ;
- digest `d98fa652aff1aff960887131b236e17fc41cb932dc461f9118ae67d686c982c5`.

Ces contrôles montrent une dynamique de turnover sans extinction immédiate ni croissance exponentielle sur les seeds testés. Ils ne constituent pas une calibration statistique définitive.

## Performance sociale

Une première implémentation conservait presque toutes les relations et dégradait fortement le temps de calcul à long terme. Le modèle final borne la mémoire sociale à **24 relations par Slime**, ce qui :

- réduit la complexité ;
- correspond mieux à une capacité cognitive limitée ;
- conserve les relations les plus familières.

Sur le seed de référence :

- 20 000 ticks complets passent en environ 20 s dans l'environnement de construction ;
- aucune corruption d'état observée.

## Stress test mécanique

Scénario volontairement simplifié : 10 Slimes, reproduction désactivée, durée de vie prolongée.

- 100 000 ticks terminés sans erreur ;
- population finale 10 ;
- digest déterministe validé.

## Limites de validation

- pas de prétention à un réalisme biologique ;
- le détecteur d'émergence reste heuristique ;
- le langage reste associatif et non compositionnel ;
- le runtime Streamlit n'a pas pu être démarré dans l'environnement de construction faute de package Streamlit disponible hors réseau, mais tout le code a été compilé statiquement et la logique métier est couverte par tests.
