# Les Slimes — état courant du projet

Ce fichier sert de point de reprise après changement ou réinitialisation de conversation.

## Repo canonique

- Repo unique : `Jean-Philippe56520/Les-Slimes`
- Branche : `main`
- Frontend cible : React + TypeScript + PixiJS sur Netlify
- Streamlit : laboratoire secondaire science/admin/debug
- Aucun autre repo n'est dans le périmètre Les Slimes.

## Invariants d'architecture

Il existe un seul monde Les Slimes canonique, persistant et partagé. Il possède une seule horloge, un seul état officiel, une seule histoire, une seule chaîne de commandes et une seule persistance active.

Le monde canonique ne change jamais de mode. Les restrictions portent sur les acteurs, permissions, niveaux de pouvoir, budgets et sanctions.

Toute mutation externe officielle suit désormais :

`acteur -> command queue persistante -> CanonicalWorldWorker -> GovernancePolicy -> moteur Python -> persistance atomique monde + intervention + budget + audit`

La gouvernance est vérifiée à l'exécution puis revalidée juste avant le commit. Une commande peut donc être mise en queue puis rejetée si l'autorité a changé ; ce refus reste auditable et terminal une fois persisté.

Les expériences sont explicitement non canoniques et structurellement isolées de la persistance officielle.

## Ontologie divine courante

Le **Créateur**, aussi nommé le **Père**, est l'autorité souveraine de la Constitution divine. L'identité technique `father` représente le Créateur.

Jean-Philippe est le **Héraut** du Créateur : Porte-parole et Messager auprès d'Ordre et de Chaos. L'identité technique `herald` le représente séparément de `father`.

`herald` démarre actif, au niveau Observation, sans permission mutante ni budget. Il ne possède aucun privilège de `GovernanceAdminService` et ne peut donc pas administrer permissions, pouvoirs, budgets ou sanctions sans évolution explicite de la Constitution et du code.

Ordre et Chaos peuvent s'adresser au Héraut pour saisir le Créateur, mais ne peuvent ni usurper l'identité du Héraut ou du Créateur, ni fabriquer une approbation, ni provoquer une faute pour la faire attribuer à un autre acteur.

## Runtime canonique présent

- `tick_duration_seconds` et métadonnées UTC persistées ;
- `CanonicalRuntime.advance_to(target_time)` ;
- catch-up déterministe par batches ;
- test continu == interruption + reload + catch-up au même digest ;
- command queue SQLite persistante, ordonnée et idempotente ;
- traitement paginé de toutes les commandes dues avant dépassement de leur date ;
- `CanonicalWorldWorker` comme chemin unique de mutation externe ;
- séparation entre temps canonique simulé et wall-clock du processus ;
- writer lease exclusif avec token de fencing et génération ;
- validation du lease dans la même transaction SQLite que `save_world` ;
- un writer expiré/zombie ne peut plus committer après takeover ;
- heartbeat réel entre batches de catch-up et pendant l'idle ;
- `CanonicalWorkerService` pour boucle persistante H24 sur un hôte ;
- identité d'instance unique par défaut ;
- arrêt propre du service et libération du lease ;
- métriques de santé : tick, retard, ticks dus, backlog, plus ancienne commande et état du lease ;
- CLI `worker-run` et `worker-status` ;
- événements `command_applied` pour reprise après crash sans double effet ;
- test crash/takeover == exécution continue au même digest ;
- test de concurrence : une seule acquisition de lease gagne ;
- acteurs persistants : `father`, `herald`, `order`, `chaos`, `observer`, `system` ;
- `father` = Créateur souverain ; `herald` = Jean-Philippe, Héraut distinct sans pouvoir mutatif par défaut ;
- registre central des commandes : nourriture, signal, ajout/retrait règle comportementale, ajout/retrait mystère ;
- validation du payload avant insertion en queue ;
- provenance `source_proposal_id` pour les commandes issues de l'Observateur ;
- CLI mutatif converti en enqueue/worker ;
- Streamlit converti en Lab lecture/admin + enqueue, sans simulation concurrente ;
- Observateur convertit ses propositions en commandes mais ne modifie plus directement `World` ;
- test architectural empêchant les principaux contournements de la frontière canonique.

## Gouvernance persistante présente

- `PowerLevel` : Observation, Miracle, Décret, Loi, Transgression ;
- état de pouvoir séparé des permissions techniques ;
- Ordre, Chaos et Héraut démarrent au niveau Observation ; Créateur (`father`) au niveau Transgression ;
- budgets append-only : `miracle`, `legislative`, `favor`, `transgression_debt` ;
- le Créateur n'est pas limité par les budgets d'exécution mais toutes ses interventions restent auditées ;
- sanctions déclaratives allowlistées : suspension, refus Miracle/Décret, gel de budget, plafond de pouvoir ;
- `GovernancePolicy` centralise identité, permission, niveau, sanction et budget et échoue fermé si un état de gouvernance manque ;
- une commande issue de l'Observateur exige aussi `observer.apply_proposal` ;
- chaque commande mutante crée une intervention divine attribuée ;
- revalidation de la gouvernance juste avant commit ;
- débit budget + état d'intervention + audit écrits dans la même transaction SQLite que `save_world` ;
- rejet d'une commande + rejet de son intervention écrits dans une seule transaction SQLite ;
- états `executed`, `rejected` et `cancelled` terminaux, protégés par triggers SQLite ;
- un rejet persistant ne peut pas ressusciter après crash, expiration d'une sanction ou changement d'autorité ;
- un seul débit négatif autorisé par intervention via index SQLite unique partiel ;
- crash après commit mais avant `mark_applied` réconcilié sans double débit ;
- audit append-only chaîné par hash et validation de chaîne ;
- journaux et propositions divines persistants ;
- proposition possible même avec budget d'exécution nul ;
- stockage minimal du Conseil divin et positions réelles d'Ordre/Chaos ;
- `GovernanceAdminService` : seul `father`, représentant le Créateur, peut enregistrer un acteur et modifier permissions, pouvoir, budgets, sanctions ou suspension ;
- `herald` n'est jamais accepté comme administrateur par défaut ;
- tout acteur enregistré par le Créateur reçoit atomiquement un état de gouvernance Observation ;
- les acteurs runtime historiques sans état sont backfillés en Observation avant exécution ;
- toute mutation administrative exige une raison non vide ;
- aucune commande canonique ne permet à un dieu de s'auto-attribuer budget/pouvoir/permission ;
- la Transgression n'est pas un bypass exécutable : elle reste une classification gouvernée/auditable ;
- package `governance` à imports bas niveau sans cycle avec `runtime.commands` ;
- tests d'import exécutés dans des interpréteurs Python vierges et dans les deux ordres d'import ;
- test architectural interdisant aux surfaces externes de contourner `GovernanceAdminService` ;
- CLI Créateur : `governance-status`, `governance-budget`, `governance-power`, `governance-permission`, `governance-active`, `governance-sanction`, `governance-sanction-lift` ;
- CLI journal/proposition : `governance-journal`, `governance-proposal` ;
- le Lab Streamlit affiche la gouvernance en lecture seule ; administration complète réservée au canal du Créateur jusqu'à l'API authentifiée ;
- la gouvernance ne modifie pas `World.state_digest()` ;
- les forks expérimentaux ne recopient aucune table `divine_*`.

Les anciennes méthodes mutantes de `RuntimeStorage` restent uniquement comme primitives techniques de compatibilité/migration. Elles ne constituent pas un chemin d'administration autorisé ; les interfaces externes sont testées pour ne jamais les appeler.

## Science/forks présents

- scope de persistance explicite : `canonical` ou `non_canonical_experiment` ;
- les anciennes DB historiques sans scope mais contenant un monde sont reconnues comme canoniques puis estampillées ;
- le runtime canonique et `RuntimeStorage` refusent une DB expérimentale ;
- un runner expérimental refuse une DB canonique ;
- création d'un fork depuis un backup SQLite cohérent ouvert en lecture seule ;
- reconstruction du fork dans une nouvelle DB au lieu de recopier la DB runtime complète ;
- command queue, writer lease, acteurs runtime et gouvernance active ne sont pas copiés ;
- `ExperimentManifest` avec experiment/run id, source tick/event sequence/digest/git commit/config, condition, seed expérimental, digests initial/final et ticks exécutés ;
- reseed RNG expérimental explicite et traçable ;
- CLI `experiment-fork` et `experiment-run` ;
- tests prouvant qu'une expérience ne modifie pas le digest du monde canonique et que deux forks exacts reproduisent le même résultat.

## État technique moteur

Le repo contient notamment : moteur 2D déterministe, RNG dédié/restaurable, génétique, reproduction, filiation, énergie/santé/âge/mortalité, ressources, mémoire spatiale, relations sociales, signaux et apprentissage, transmission Slime -> Slime, DSL comportemental, mystères persistants, SQLite transactionnel, événements/checkpoints, digest d'état, rapports analytiques, Inbox Observateur, runtime H24, gouvernance divine persistante et CI.

## Dette prioritaire

1. construire l'API Python/FastAPI et l'authentification Créateur/Héraut/acteurs sans accepter un `actor_id` arbitraire fourni par le client ;
2. construire React + TypeScript + PixiJS ;
3. choisir et migrer vers la persistance PostgreSQL durable de production ;
4. définir le déploiement/supervision du worker canonique ;
5. automatiser rapports/Drive ;
6. créer Ordre/Chaos comme GPT Projects autonomes puis leurs tâches planifiées ;
7. exporter Conseil/journaux vers Drive sans en faire une source transactionnelle.

## Point de vigilance

Le runtime SQLite est conçu et testé pour un fonctionnement continu contrôlé sur un hôte unique, avec fencing, heartbeat, takeover et reprise déterministe. La gouvernance est persistante dans cette même base canonique mais séparée du digest biologique.

Cela ne signifie pas encore que l'ensemble est prêt pour une production publique H24 : la persistance durable distante, l'orchestration/supervision du processus, les sauvegardes opérationnelles, l'authentification et l'exposition réseau restent à définir.

## Gouvernance divine

Ordre favorise stabilité, structures, continuité, résilience et transmission fiable. Chaos favorise diversité, variation, exploration et nouveauté. Aucun dieu ne commande directement un Slime.

Le Créateur/Père est l'autorité souveraine et `father` le représente. Jean-Philippe est le Héraut et `herald` le représente séparément sans pouvoir mutatif par défaut.

Les dieux ne peuvent pas sortir du repo autorisé, falsifier l'audit, usurper une identité, fabriquer une approbation, augmenter leurs propres droits, supprimer sauvegardes/CI/rollback, pousser des secrets, écrire dans la base active en contournant command queue + worker, ni provoquer une violation pour la faire attribuer à un autre acteur.

## Lecture obligatoire

Toujours lire au début d'une nouvelle conversation :
1. vérifier `main` et les derniers commits ;
2. `docs/PROJECT_STATE.md` ;
3. `docs/PROJECT_INSTRUCTIONS.md` ;
4. `README.md` ;
5. `docs/DIVINE_GOVERNANCE.md` ;
6. `docs/SCIENTIFIC_PROTOCOL.md` ;
7. `docs/OBSERVER_CONTRACT.md` ;
8. `config/default.yaml`.

Si moteur/persistance concernés, lire aussi `src/les_slimes/world/engine.py`, `src/les_slimes/database/sqlite_repo.py`, `src/les_slimes/observer/proposals.py` et les tests pertinents.

## Prochaine action recommandée

Construire l'API Python/FastAPI avec authentification explicite du Créateur, du Héraut et des acteurs, en résolvant l'identité côté serveur et sans faire confiance à un `actor_id` fourni dans les payloads.
