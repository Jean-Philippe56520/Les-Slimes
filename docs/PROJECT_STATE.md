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

`acteur -> permission -> gouvernance -> command queue persistante -> CanonicalWorldWorker -> moteur Python -> persistance`

Les expériences sont explicitement non canoniques et structurellement isolées de la persistance officielle.

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
- acteurs persistants : `father`, `order`, `chaos`, `observer`, `system` ;
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
- Ordre et Chaos démarrent au niveau Observation ; Père au niveau Transgression ;
- budgets append-only : `miracle`, `legislative`, `favor`, `transgression_debt` ;
- le Père n'est pas limité par les budgets d'exécution mais toutes ses interventions restent auditées ;
- sanctions déclaratives allowlistées : suspension, refus Miracle/Décret, gel de budget, plafond de pouvoir ;
- `GovernancePolicy` centralise identité, permission, niveau, sanction et budget ;
- une commande issue de l'Observateur exige aussi `observer.apply_proposal` ;
- chaque commande mutante crée une intervention divine attribuée ;
- revalidation de la gouvernance juste avant commit ;
- débit budget + état d'intervention + audit écrits dans la même transaction SQLite que `save_world` ;
- crash après commit mais avant `mark_applied` réconcilié sans double débit ;
- audit append-only chaîné par hash et validation de chaîne ;
- journaux et propositions divines persistants ;
- proposition possible même avec budget d'exécution nul ;
- stockage minimal du Conseil divin et positions réelles d'Ordre/Chaos ;
- `GovernanceAdminService` : seul le Père peut modifier permissions, pouvoir, budgets, sanctions ou suspension ;
- aucune commande canonique ne permet à un dieu de s'auto-attribuer budget/pouvoir/permission ;
- la Transgression n'est pas un bypass exécutable : elle reste une classification gouvernée/auditable ;
- CLI Père : `governance-status`, `governance-budget`, `governance-power`, `governance-permission`, `governance-active`, `governance-sanction`, `governance-sanction-lift` ;
- CLI journal/proposition : `governance-journal`, `governance-proposal` ;
- le Lab Streamlit affiche la gouvernance en lecture seule ; administration complète réservée au CLI jusqu'à l'API authentifiée ;
- la gouvernance ne modifie pas `World.state_digest()` ;
- les forks expérimentaux ne recopient aucune table `divine_*`.

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

PR intégrées ou en cours :
- `#2 feat: add canonical time catch-up runtime` ;
- `#3 feat: add canonical command queue and writer lease` ;
- `#4 refactor: replace world modes with actor permissions` ;
- `#5 refactor: enforce canonical command boundary` ;
- `#6 feat: isolate scientific experiment forks` ;
- `#7 feat: harden canonical world worker for H24` ;
- `#8 feat: add persistent divine governance`.

## État technique moteur

Le repo contient notamment : moteur 2D déterministe, RNG dédié/restaurable, génétique, reproduction, filiation, énergie/santé/âge/mortalité, ressources, mémoire spatiale, relations sociales, signaux et apprentissage, transmission Slime -> Slime, DSL comportemental, mystères persistants, SQLite transactionnel, événements/checkpoints, digest d'état, rapports analytiques, Inbox Observateur, runtime H24, gouvernance divine persistante et CI.

## Dette prioritaire

1. construire l'API Python/FastAPI et l'authentification du Père/acteurs ;
2. construire React + TypeScript + PixiJS ;
3. choisir et migrer vers la persistance PostgreSQL durable de production ;
4. définir le déploiement/supervision du worker canonique ;
5. automatiser rapports/Drive ;
6. créer Ordre/Chaos comme GPT Projects autonomes puis leurs tâches planifiées ;
7. exporter Conseil/journaux vers Drive sans en faire une source transactionnelle.

## Point de vigilance

Le runtime SQLite est conçu et testé pour un fonctionnement continu contrôlé sur un hôte unique, avec fencing, heartbeat, takeover et reprise déterministe. La gouvernance est persistante dans cette même base canonique mais séparée du digest biologique.

Cela ne signifie pas encore que l'ensemble est prêt pour une production publique H24 : la persistance durable distante, l'orchestration/supervision du processus, les sauvegardes opérationnelles, l'authentification et l'exposition réseau restent à définir.

Une ancienne base contenant une metadata `mode` reste lisible : le loader l'ignore et la clé est supprimée au prochain `save_world`.

## Gouvernance divine

Ordre favorise stabilité, structures, continuité, résilience et transmission fiable. Chaos favorise diversité, variation, exploration et nouveauté. Aucun dieu ne commande directement un Slime.

Jean-Philippe est le Père : budgets, récompenses, sanctions, permissions et Constitution.

Les dieux ne peuvent pas sortir du repo autorisé, falsifier l'audit, augmenter leurs propres droits, supprimer sauvegardes/CI/rollback, pousser des secrets ou écrire dans la base active en contournant command queue + worker.

## Lecture obligatoire

Toujours lire au début d'une nouvelle conversation :
1. `docs/PROJECT_STATE.md`
2. `docs/PROJECT_INSTRUCTIONS.md`
3. `README.md`
4. `docs/DIVINE_GOVERNANCE.md`
5. `docs/SCIENTIFIC_PROTOCOL.md`
6. `docs/OBSERVER_CONTRACT.md`
7. `config/default.yaml`

Si moteur/persistance concernés, lire aussi `src/les_slimes/world/engine.py`, `src/les_slimes/database/sqlite_repo.py`, `src/les_slimes/observer/proposals.py` et les tests pertinents.

## Prochaine action recommandée

Construire l'API Python/FastAPI au-dessus du runtime et de la gouvernance existants, avec authentification explicite du Père et des acteurs. Ensuite construire React + TypeScript + PixiJS.
