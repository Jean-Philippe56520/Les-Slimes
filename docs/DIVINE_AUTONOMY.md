# Autonomie divine confinée

Ce document définit l'architecture cible d'autonomie d'Ordre, de Chaos et du Créateur.

## Principe

Ordre et Chaos conservent une forte capacité d'analyse, d'expérimentation et de proposition de Lois, mais leur surface technique est confinée à l'univers Les Slimes.

Le confinement réduit la largeur d'accès, pas la profondeur technique : un dieu doit pouvoir lire le code, rechercher, modifier sa branche, exécuter les Épreuves, inspecter les résultats et préparer une proposition de Loi sans disposer d'un accès général à des environnements extérieurs.

Le Créateur, représenté par `father`, reste l'autorité souveraine qui peut transformer une proposition divine en Loi effectivement intégrée à `main`.

## Frontière des dieux

La politique `DivineAccessPolicy` est fail-closed et s'applique à Ordre et Chaos avant tout adaptateur réel.

Elle impose notamment :

- repo GitHub unique `Jean-Philippe56520/Les-Slimes` ;
- aucune écriture directe sur `main` ;
- Ordre écrit seulement sous `god/order/*` ;
- Chaos écrit seulement sous `god/chaos/*` ;
- Drive limité à la racine LES_SLIMES et aux descendants reconnus par le manifest canonique ;
- API limitée aux routes divines explicitement allowlistées ;
- routes `/admin/...` interdites aux dieux ;
- absence de surface Web générale ;
- chemins de workspace relatifs et sans traversée hors périmètre.

Une capacité technique disponible en dessous d'un adaptateur ne constitue jamais une autorisation pour le dieu qui utilise cet adaptateur.

## Ateliers législatifs

Chaque dieu travaille dans un atelier isolé dérivé de `main` :

- `god/order/<slug>` pour Ordre ;
- `god/chaos/<slug>` pour Chaos.

Une Loi candidate comporte au minimum :

- auteur divin ;
- proposition persistante ;
- branche ;
- PR ;
- SHA exact de la tête ;
- SHA de `main` ayant servi de base ;
- résultats des Épreuves requises ;
- état de gouvernance ;
- preuves techniques/scientifiques ;
- résultats expérimentaux lorsque requis.

Ordre et Chaos peuvent proposer, corriger ou retirer leurs travaux. Ils ne possèdent jamais l'autorité de merge sur `main`.

## Cycle souverain du Créateur

`SovereignCreatorCycle` sépare la décision politique du droit technique de promulguer.

Le Créateur peut décider :

- accepter ;
- refuser ;
- attendre ;
- demander un amendement ;
- demander une expérience supplémentaire.

Même une décision `accept` ne produit une `MergeAuthorization` que si tous les garde-fous mécaniques sont satisfaits :

- acteur divin reconnu ;
- branche divine correcte ;
- PR ouverte et mergeable ;
- `main` de référence encore courant ;
- SHA complets et liés à la revue ;
- toutes les Épreuves requises passées ;
- gouvernance éligible ;
- preuves complètes ;
- expérience isolée ou combinée passée lorsqu'elle est obligatoire.

L'autorisation de merge lie le numéro de PR, le SHA exact de la tête et le SHA exact de la base examinée. Une modification postérieure exige donc une nouvelle revue souveraine.

## Lois concurrentes

Deux Lois vertes séparément ne sont jamais supposées compatibles.

Lorsque leurs effets peuvent interagir, le Créateur peut imposer une Épreuve combinée comparant notamment :

- contrôle ;
- Ordre seul ;
- Chaos seul ;
- Ordre + Chaos.

L'intégration de plusieurs Lois reste une décision souveraine distincte de l'acceptation individuelle de chacune.

## Héraut

Le Héraut transmet les demandes, arguments et décisions selon la gouvernance. Il ne reçoit pas implicitement les pouvoirs techniques de `father` et n'est pas une voie indirecte permettant à un dieu de contourner sa frontière.

## Activation progressive

L'activation doit suivre trois étapes :

1. **shadow** : cycles et décisions réels, aucune promulgation automatique ;
2. **promulgation contrôlée** : le Créateur peut merger automatiquement les Lois satisfaisant les garde-fous ;
3. **autonomie souveraine** : cycles planifiés complets, avec possibilité normale de ne promulguer aucune Loi.

Les connecteurs génériques ne doivent être retirés aux dieux qu'une fois les adaptateurs confinés suffisamment complets pour préserver leurs capacités de travail dans Les Slimes.
