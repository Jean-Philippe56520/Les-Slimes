# Autonomie divine confinée

Ce document définit l'architecture d'autonomie d'Ordre, de Chaos et du Créateur.

## Principe

Ordre et Chaos conservent une forte capacité d'analyse, d'expérimentation et de proposition, mais **GitHub leur est strictement accessible en lecture seule**.

Le confinement réduit la largeur d'accès, pas la profondeur technique. Un dieu peut lire et rechercher le code, comprendre les tests, travailler sur une copie non canonique, exécuter des Épreuves, produire un patch et des tests puis constituer un dossier de Loi. Il ne possède cependant aucun credential ni aucune primitive permettant de créer une branche, commit, push ou pull request GitHub.

Le Créateur, représenté par `father`, est le seul acteur de cette architecture qui transforme une proposition divine acceptée en implémentation Git puis, éventuellement, en Loi promulguée sur `main`.

## Frontière des dieux

`DivineAccessPolicy` est fail-closed :

- repo GitHub unique `Jean-Philippe56520/Les-Slimes`, lecture seule pour Ordre et Chaos ;
- surface de connaissance filtrée ;
- aucun Web général ;
- Drive limité à LES_SLIMES ;
- API limitée aux routes allowlistées ; `/admin/...` interdit ;
- Mondes d'Épreuve non canoniques et incapables d'écrire dans le monde officiel ;
- aucun credential Git d'écriture dans l'environnement divin.

Une capacité technique sous-jacente ne constitue jamais une permission.

## Ateliers Drive

Le manifest canonique définit :

- `50_DIVINE_WORKSHOPS` : `1qNxcE9R0DewgB8iQPwFXaS2WXcz_fU1k` ;
- `ORDER_PROPOSALS` : `1VbYXIt8hU4UEAVYIvWMob7SL0G3-lcOC` ;
- `CHAOS_PROPOSALS` : `1i5L-8aOCvrwc3Buck3hhJnFydvlFXc2v` ;
- `CREATOR_REVIEW` : `1i0vMELFu0Ijw7ZhP4430GgZ3lq3TXArt`.

Ordre écrit uniquement dans `ORDER_PROPOSALS`. Chaos écrit uniquement dans `CHAOS_PROPOSALS`. Le Créateur peut lire les ateliers divins et écrit ses dossiers de reprise dans `CREATOR_REVIEW`.

Drive reste une Archive lisible, jamais la source transactionnelle du statut d'une proposition.

## Atelier technique non canonique

Pour préserver leur profondeur de développement, Ordre et Chaos peuvent travailler dans une copie isolée de `main` sans credential Git d'écriture. Ils peuvent y modifier des fichiers, exécuter tests et expériences, calculer un diff ou patch et produire les artefacts nécessaires.

Cet atelier :
- ne peut pas pousser vers GitHub ;
- ne peut pas écrire dans la persistance canonique ;
- ne dispose pas de Web général ;
- n'élargit pas la surface de connaissance du dieu ;
- ne devient jamais une seconde source de vérité.

## Proposition de Loi

Le dossier persistant `LawDossier` contient notamment :

- auteur ;
- observation, hypothèse, bénéfice attendu et risque ;
- SHA exact de `main` utilisé comme source ;
- identifiant de l'artefact Drive ;
- digest du manifest ;
- digest du patch ;
- fichiers visés ;
- preuves et expériences.

Les fichiers visés restent limités aux surfaces ordinaires du vivant et à leurs tests non protecteurs. Gouvernance, identité, authentification, persistance canonique, frontière divine, déploiement, CI, sauvegardes et tests protecteurs restent hors périmètre.

La base persistante conserve le statut officiel : `proposed`, `needs_evidence`, `needs_amendment`, `waiting`, `blocked`, `accepted`, `rejected`, `promulgated` ou `superseded`.

## Revue souveraine

`SovereignCreatorCycle` peut : accepter, refuser, attendre, demander un amendement ou demander une expérience.

Une décision `accept` ne produit plus une autorisation de merge. Elle produit seulement une `ImplementationAuthorization` : le Créateur est autorisé à reprendre le dossier vérifié.

La revue lie notamment auteur, proposition, SHA source, artefact Drive, digests et fichiers visés. Une dérive impose une nouvelle revue.

## Implémentation du Créateur

Si le Créateur décide d'implémenter une proposition acceptée :

1. il repart du `main` examiné ;
2. crée `father/law-<proposal_id>-<slug>` ;
3. écrit lui-même le code et les tests ;
4. ouvre la pull request ;
5. exécute les Épreuves ;
6. attache une `CreatorImplementation` au dossier persistant.

Le jeu de fichiers implémentés doit correspondre exactement au périmètre accepté. Une modification supplémentaire exige une nouvelle décision ou un dossier amendé.

## Promulgation

`CreatorPromulgationService` revalide immédiatement avant merge :

- repo, branche `father/law-*`, PR, head SHA et base SHA ;
- ensemble réel des fichiers ;
- surface législative autorisée ;
- checks requis ;
- gouvernance actuelle du dieu proposant ;
- budget législatif.

Le budget reste imputé au dieu dont la proposition est promulguée. La saga de réservation et la réconciliation d'un résultat Git incertain restent en vigueur.

## Lois concurrentes

Deux propositions valides séparément ne sont jamais supposées compatibles. Le Créateur peut exiger contrôle / Ordre / Chaos / combinaison avant toute implémentation ou promulgation.

## Activation progressive

1. **shadow** : propositions Drive et décisions réelles, aucune implémentation automatique ;
2. **implémentation contrôlée** : le Créateur peut reprendre et promulguer une proposition conforme ;
3. **autonomie souveraine** : cycles planifiés Ordre → Chaos → Créateur.

« Aucune Loi » reste toujours un résultat normal.
