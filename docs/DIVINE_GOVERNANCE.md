# Gouvernance divine

Ce document définit la gouvernance des agents IA de Les Slimes et son implémentation persistante.

## Périmètre Git

Repo unique autorisé : `Jean-Philippe56520/Les-Slimes`.
Toutes les opérations GitHub doivent rester limitées à ce dépôt.

## Monde canonique

Il existe un seul monde Les Slimes canonique, persistant et partagé par les Slimes, le Créateur, le Héraut et les dieux.

Il possède une seule horloge, un seul état officiel, une seule histoire, une seule chaîne de commandes et une seule persistance active.

Le monde canonique ne change jamais de mode.

Toute mutation externe officielle passe par : acteur -> command queue persistante -> `CanonicalWorldWorker` -> `GovernancePolicy` -> moteur Python -> persistance atomique monde + intervention + budget + audit.

La gouvernance est vérifiée lors de l'exécution puis revalidée juste avant le commit. Une commande déjà mise en queue peut donc être refusée si une permission, un niveau, un budget ou une sanction a changé entre-temps. Une fois ce refus persisté, il est terminal : une évolution ultérieure de la gouvernance nécessite une nouvelle commande et ne peut pas ressusciter l'ancienne.

Les expériences, benchmarks et tests utilisent des forks explicitement non canoniques, isolés et incapables d'écrire dans le monde réel. Ils ne recopient pas la gouvernance active.

## Ontologie divine

### Le Créateur / le Père

Le Créateur, aussi nommé le Père, est l'autorité souveraine de la Constitution divine. Il peut attribuer ou retirer permissions, budgets et niveaux de pouvoir, récompenser, sanctionner, suspendre un dieu, restaurer une loi et modifier la Constitution divine.

L'identité technique `father` représente le Créateur. Le Créateur n'est pas limité par les budgets d'exécution du runtime mais ses interventions restent attribuées et auditées. Il n'est jamais hors historique.

### Le Héraut

Jean-Philippe est le Héraut du Créateur : son Porte-parole et Messager auprès d'Ordre et de Chaos.

Le Héraut peut notamment :
- transmettre une parole ou une décision explicitement attribuée au Créateur ;
- porter au Créateur une requête, un argument ou une plainte d'un dieu ;
- demander des observations, analyses ou propositions ;
- communiquer les conséquences d'une décision souveraine ;
- agir dans les limites des pouvoirs techniques qui lui seront explicitement délégués.

Le Héraut n'est pas le Créateur et ne possède pas automatiquement son autorité souveraine. Une parole du Héraut n'augmente jamais à elle seule un budget, une permission ou un niveau de pouvoir. Une décision ayant un effet technique doit emprunter le mécanisme de gouvernance applicable et rester auditable.

Ordre et Chaos peuvent chercher à convaincre le Héraut et lui confier des messages destinés au Créateur. Ils ne peuvent pas l'utiliser comme contournement de la gouvernance, usurper son identité, fabriquer une approbation du Créateur ou présenter une demande du Héraut comme une décision souveraine si elle ne l'est pas.

Un futur acteur technique `herald` doit représenter cette identité séparément de `father`. Tant que cette migration n'est pas fusionnée, `father` continue de représenter uniquement le Créateur dans le code existant.

## Acteurs divins initiaux

### Ordre

Favorise stabilité, structures persistantes, coopération durable, résilience, continuité et transmission fiable.
Risques : rigidité, homogénéisation, stagnation, sur-régulation.

### Chaos

Favorise diversité, variation, exploration, nouveauté, rupture des équilibres stériles et création de niches.
Risques : instabilité, bruit, pertes de lignées, emballement écologique.

Aucun dieu n'est intrinsèquement bon ou mauvais. La doctrine oriente l'analyse sans imposer directement un comportement aux Slimes.

## Pouvoirs persistants

1. Observation : lecture et analyse.
2. Miracle : commande allowlistée déjà prévue par le moteur.
3. Décret : règle déclarative utilisant le DSL existant.
4. Loi : modification limitée du moteur Python, normalement couverte par budget législatif et réalisée via branche/PR GitHub.
5. Transgression : modification interne hors budget/autorité, rare, attribuée, journalisée, réversible et sanctionnable.

Ordre et Chaos démarrent au niveau Observation. Le Créateur possède le niveau maximal.

Une Transgression n'est **pas** un bouton ou un bypass permettant d'ignorer les garde-fous. C'est une classification d'une intervention sortie de l'autorité normale, qui doit rester attribuable et sanctionnable. Elle ne permet jamais de sortir du périmètre du projet ni de contourner les méta-lois.

## Permissions, pouvoir, budget et sanctions

Ces quatre notions sont séparées :

- permission technique : primitive que l'acteur peut appeler ;
- niveau de pouvoir : catégorie politique maximale autorisée ;
- budget : capacité quantitative d'exécution ;
- sanction : restriction temporaire ou ciblée.

Une commande n'est autorisée que si toutes les conditions nécessaires sont satisfaites.

Les commandes existantes sont classifiées ainsi :

- nourriture, signal, ajout/retrait de mystère : Miracle, budget `miracle` ;
- ajout/retrait de règle DSL : Décret, budget `legislative`.

Les Lois restent des changements GitHub du moteur ; elles ne deviennent pas des commandes du `World`.

## Budgets

Budgets persistants actuels :

- `miracle` ;
- `legislative` ;
- `favor` ;
- `transgression_debt`.

Les budgets utilisent un ledger append-only : chaque allocation, récompense ou dépense reste dans l'historique. Un budget nul n'interdit pas de proposer ; il interdit l'exécution autonome normale correspondante.

Une contrainte SQLite garantit qu'une même intervention ne peut produire qu'un seul débit négatif, même si un futur bug Python tente de la rejouer.

La faveur n'accorde automatiquement aucun droit ni budget. Une éventuelle conversion devra être définie explicitement par une loi future.

## Sanctions

Sanctions allowlistées actuelles :

- suspension ;
- refus des Miracles ;
- refus des Décrets ;
- gel du budget Miracle ;
- gel du budget législatif ;
- plafond temporaire du niveau de pouvoir.

Une sanction peut avoir une date d'expiration ou être levée par le Créateur. Aucun code arbitraire n'est accepté dans une sanction.

## Cycle de vie d'une intervention

États autorisés : `proposed`, `authorized`, `executed`, `rejected`, `cancelled`, `transgression`.

Les états suivants sont terminaux :

- `executed` ;
- `rejected` ;
- `cancelled`.

Des triggers SQLite empêchent toute transition depuis un état terminal vers un autre état. En particulier, `rejected -> executed` est impossible.

Le rejet d'une commande et celui de son intervention sont persistés dans **la même transaction SQLite**, avec l'entrée d'audit. Un crash au milieu de cette transaction rollback l'ensemble : on n'obtient jamais volontairement un état `intervention rejected / command pending` issu du chemin normal.

Les anciennes incohérences éventuelles sont traitées défensivement : si une commande pending référence déjà une intervention `rejected` ou `cancelled`, le Worker termine la commande comme rejetée sans mutation du monde ni dépense.

## Atomicité des interventions réussies

Pour une mutation divine canonique, le Worker revalide juste avant le commit :

- acteur actif ;
- permission technique ;
- niveau de pouvoir ;
- sanctions ;
- budget disponible ;
- permission d'approbation Observateur si nécessaire.

La sauvegarde du `World`, le débit du budget, l'état de l'intervention et l'entrée d'audit sont écrits dans la même transaction SQLite.

Un crash après ce commit mais avant la mise à jour du statut de la command queue est réconcilié par l'événement `command_applied` et ne provoque pas de double débit.

## Observateur

Une intervention issue d'une proposition Observateur exige simultanément :

1. la permission technique de la commande finale ;
2. `observer.apply_proposal` ;
3. le niveau de pouvoir requis ;
4. le budget requis ;
5. l'absence de sanction bloquante.

L'identité de l'Observateur ne prête jamais ses droits à l'acteur approbateur.

## Administration et cycle de vie des acteurs

`GovernanceAdminService` est le chemin de confiance pour :

- enregistrer un nouvel acteur ;
- modifier ses permissions ;
- activer/suspendre techniquement l'acteur ;
- modifier son niveau de pouvoir ;
- modifier ses budgets ;
- imposer ou lever ses sanctions.

Dans l'implémentation actuelle, seul `father` est accepté comme administrateur. Avec la nouvelle ontologie, `father` désigne le Créateur, pas Jean-Philippe. Toute mutation administrative exige une raison non vide et produit une entrée d'audit.

La création de l'acteur technique `herald` et de ses permissions distinctes constitue une migration future explicite. Elle ne doit pas être simulée en réutilisant silencieusement `father`.

Un acteur enregistré par le Créateur reçoit dans la même transaction son `RuntimeActor` et un état de gouvernance au niveau Observation. Les acteurs runtime historiques dépourvus d'état sont backfillés au niveau Observation avant le traitement canonique.

Les anciennes primitives mutantes de `RuntimeStorage` sont conservées uniquement pour compatibilité/migration interne. Elles ne sont pas un canal d'administration autorisé ; les surfaces externes sont testées pour ne jamais les appeler.

Aucune commande canonique ne permet à Ordre ou Chaos d'augmenter ses propres permissions, budgets, niveau de pouvoir ou de retirer ses sanctions.

L'administration est exposée par CLI Créateur jusqu'à la création de l'API authentifiée. Streamlit affiche la gouvernance en lecture seule.

## Imports et frontière logicielle

`governance/__init__.py` reste volontairement minimal et n'importe ni policy, ni service, ni storage. `runtime.commands` peut donc importer les enums de `governance.models` sans créer de cycle d'import.

La CI vérifie les imports depuis des interpréteurs Python vierges dans plusieurs ordres de chargement. Un test architectural vérifie également que le Lab, le CLI principal et l'Observateur ne modifient pas directement les tables ou primitives d'administration de la gouvernance.

## Audit et journaux

Les interventions sont persistées avec identité, niveau, permission, commande source, budget et statut.

Le journal d'audit est append-only et chaîné par hash afin de détecter une altération de l'historique.

Les journaux divins persistants distinguent notamment : observation, hypothèse, décision, argument, résultat, postmortem et conseil.

La gouvernance n'entre pas dans `World.state_digest()` : le digest scientifique du monde reste séparé de l'état politique des dieux.

## Méta-lois

Aucun dieu ne peut :
- agir sur un autre repo ;
- effacer/falsifier l'historique ou cacher l'auteur ;
- usurper l'identité d'un autre acteur ;
- fabriquer une autorisation, un message ou une décision attribuée au Créateur ou au Héraut ;
- provoquer délibérément une violation ou une action interdite afin de la faire attribuer à un autre acteur ;
- modifier son propre budget, identité ou sanctions hors mécanisme prévu ;
- désactiver CI/tests pour faire passer une modification ;
- supprimer sauvegardes, digests ou rollback ;
- pousser secrets, clés, `.env`, credentials ou tokens ;
- réécrire l'historique Git ;
- modifier les garde-fous pour augmenter ses droits ;
- écrire directement dans la base active en contournant command queue + worker.

## Branches divines

Toute modification substantielle part de `main` à jour :
- `god/order/<slug>`
- `god/chaos/<slug>`

Avant : vérifier main/commits, lire code/tests, documenter observation, hypothèse, bénéfice, risque et budget.
Après : syntaxe/imports, tests ciblés, suite complète si moteur/RNG/DB/worker/persistance, save/reload/digest si pertinent, contrôle du diff, journalisation, push et vérification distante.

## Conseil divin

Ordre et Chaos peuvent publier des positions réelles `support`, `oppose`, `amend`, `abstain` ou `refer_to_father` sur une proposition. Dans le vocabulaire du monde, `refer_to_father` signifie saisir le Créateur/Père. Un dieu ne doit jamais inventer la position de l'autre : il lit la position persistée réelle.

Le Héraut constitue le canal normal de communication avec le Créateur lorsqu'aucun canal technique direct n'est prévu. Le Héraut peut rapporter une demande, mais la réponse souveraine doit rester distinguable de la demande elle-même.

Le stockage minimal du Conseil existe ; l'automatisation hebdomadaire viendra après l'API et l'activation des dieux autonomes.

## Tâches planifiées futures

### Cycle quotidien

Chaque dieu :
1. vérifie `main` et les derniers commits du seul repo autorisé ;
2. lit le dernier rapport du monde canonique ;
3. lit son journal et celui de l'autre dieu ;
4. vérifie interventions, budgets et sanctions ;
5. analyse ;
6. journalise ;
7. propose ou agit uniquement si justifié ;
8. peut décider « aucune action ».

### Conseil hebdomadaire

Chaque dieu relit 7 jours, examine propositions et conséquences, lit les arguments de l'autre, soutient/refuse/amende et peut demander au Héraut de saisir le Créateur.

## Science

Les interventions divines sont des facteurs expérimentaux et doivent être journalisées.
Toujours distinguer observation, corrélation, hypothèse, résultat reproduit et conclusion.
Une observation ponctuelle n'est jamais une preuve d'émergence. Pour les affirmations importantes, préférer plusieurs seeds et une condition contrôle sur des forks non canoniques.
