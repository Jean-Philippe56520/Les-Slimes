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

Toute mutation externe officielle suit :

`acteur -> command queue persistante -> CanonicalWorldWorker -> GovernancePolicy -> moteur Python -> persistance atomique monde + intervention + budget + audit`

La gouvernance est vérifiée à l'exécution puis revalidée juste avant commit. Une commande peut donc être mise en queue puis rejetée si l'autorité a changé ; ce refus reste auditable et terminal une fois persisté.

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
- séparation temps canonique simulé / wall-clock du processus ;
- writer lease exclusif avec token de fencing et génération ;
- validation du lease dans la même transaction SQLite que `save_world` ;
- un writer expiré/zombie ne peut plus committer après takeover ;
- heartbeat réel entre batches de catch-up et pendant l'idle ;
- `CanonicalWorkerService` pour boucle persistante H24 sur un hôte ;
- identité d'instance unique par défaut ;
- arrêt propre et libération du lease ;
- métriques santé : tick, retard, ticks dus, backlog, plus ancienne commande, lease ;
- CLI `worker-run` et `worker-status` ;
- événements `command_applied` pour reprise après crash sans double effet ;
- test crash/takeover == exécution continue au même digest ;
- test de concurrence : une seule acquisition de lease gagne ;
- acteurs persistants : `father`, `herald`, `order`, `chaos`, `observer`, `system` ;
- `father` = Créateur souverain ; `herald` = Jean-Philippe, Héraut distinct sans pouvoir mutatif par défaut ;
- registre central des commandes : nourriture, signal, ajout/retrait règle comportementale, ajout/retrait mystère ;
- validation des payloads avant queue ;
- provenance `source_proposal_id` pour les commandes issues de l'Observateur ;
- CLI mutatif converti en enqueue/worker ;
- Streamlit Lab lecture/admin + enqueue, sans simulation concurrente ;
- Observateur convertit ses propositions en commandes mais ne modifie plus directement `World` ;
- tests architecturaux protégeant la frontière canonique.

## API canonique présente

- application FastAPI créée par `les_slimes.api.app:create_app` ;
- l'API ne prend jamais le writer lease et ne modifie jamais directement `World` ;
- lectures publiques : `/health`, `/world`, `/world/slimes` ;
- identité authentifiée : `/me` ;
- commandes externes : `POST /commands` vers la command queue uniquement ;
- journaux/propositions : lecture et écriture attribuées ;
- lecture de la gouvernance persistante ;
- routes administratives réservées au Créateur et routées par `GovernanceAdminService` ;
- identité résolue côté serveur depuis un Bearer token, jamais depuis un `actor_id` métier fourni par le client ;
- les schémas mutatifs utilisent `extra=forbid`, donc une tentative d'injecter `actor_id` dans une commande est rejetée ;
- configuration par empreintes SHA-256 de jetons de haute entropie dans `LES_SLIMES_AUTH_TOKEN_HASHES_JSON` ;
- aucun token ou secret n'est stocké dans GitHub ;
- authentification absente = échec fermé des routes protégées ;
- acteur inactif = accès authentifié refusé ;
- `herald` ne peut pas accéder aux routes d'administration du Créateur ;
- tests API couvrant attribution, usurpation, Héraut/Créateur, journal/proposition et non-mutation des lectures.

Voir `docs/API.md`.

## Gouvernance persistante présente

- `PowerLevel` : Observation, Miracle, Décret, Loi, Transgression ;
- état de pouvoir séparé des permissions techniques ;
- Ordre, Chaos et Héraut démarrent Observation ; Créateur (`father`) Transgression ;
- budgets append-only : `miracle`, `legislative`, `favor`, `transgression_debt` ;
- le Créateur n'est pas limité par les budgets runtime mais reste audité ;
- sanctions déclaratives allowlistées ;
- `GovernancePolicy` centralise identité, permission, niveau, sanction et budget et échoue fermé si l'état manque ;
- une commande issue de l'Observateur exige aussi `observer.apply_proposal` ;
- chaque commande mutante crée une intervention attribuée ;
- revalidation de la gouvernance juste avant commit ;
- débit budget + intervention + audit dans la même transaction SQLite que `save_world` ;
- rejet commande + intervention dans une transaction ;
- états `executed`, `rejected`, `cancelled` terminaux protégés par triggers ;
- un rejet ne ressuscite pas après crash/changement de gouvernance ;
- un seul débit négatif par intervention via index unique partiel ;
- crash après commit avant `mark_applied` réconcilié sans double débit ;
- audit append-only chaîné par hash ;
- journaux et propositions divines persistants ;
- proposition possible avec budget d'exécution nul ;
- stockage minimal du Conseil divin ;
- `GovernanceAdminService` : seul `father` peut enregistrer un acteur et modifier permissions, pouvoir, budgets, sanctions ou suspension ;
- `herald` n'est jamais administrateur par défaut ;
- acteur enregistré -> état Observation atomique ;
- acteurs historiques sans état backfillés Observation ;
- raison non vide obligatoire pour toute mutation administrative ;
- aucune commande canonique d'auto-escalade ;
- Transgression non exécutable comme bypass ;
- imports gouvernance durcis contre les cycles ;
- test architectural interdisant aux surfaces externes de contourner `GovernanceAdminService` ;
- CLI Créateur : `governance-status`, `governance-budget`, `governance-power`, `governance-permission`, `governance-active`, `governance-sanction`, `governance-sanction-lift` ;
- CLI journal/proposition ;
- Lab Streamlit gouvernance lecture seule ;
- gouvernance exclue de `World.state_digest()` ;
- forks expérimentaux sans tables `divine_*`.

Les anciennes méthodes mutantes de `RuntimeStorage` restent seulement des primitives internes de compatibilité/migration, jamais un canal externe autorisé.

## Science/forks présents

- scope explicite `canonical` ou `non_canonical_experiment` ;
- ancienne DB avec monde mais sans scope reconnue puis estampillée canonique ;
- runtime/storage canonique refusent une DB expérimentale ;
- runner expérimental refuse une DB canonique ;
- fork depuis backup SQLite cohérent en lecture seule ;
- reconstruction dans une nouvelle DB au lieu de recopier le runtime complet ;
- queue, lease, acteurs runtime et gouvernance active non copiés ;
- `ExperimentManifest` complet : source tick/event/digest/git/config, condition, seed, digests et ticks ;
- reseed RNG explicite et traçable ;
- CLI `experiment-fork`, `experiment-run` ;
- tests d'isolation canonique et reproductibilité exacte.

## Historique des grandes PR intégrées

- `#2 feat: add canonical time catch-up runtime` ;
- `#3 feat: add canonical command queue and writer lease` ;
- `#4 refactor: replace world modes with actor permissions` ;
- `#5 refactor: enforce canonical command boundary` ;
- `#6 feat: isolate scientific experiment forks` ;
- `#7 feat: harden canonical world worker for H24` ;
- `#8 feat: add persistent divine governance` ;
- `#9 docs: establish Creator and Herald ontology` ;
- `#10 feat: add herald runtime actor`.

## État technique moteur

Le repo contient notamment : moteur 2D déterministe, RNG dédié/restaurable, génétique, reproduction/filiation, énergie/santé/âge/mortalité, ressources, mémoire spatiale, relations sociales, signaux/apprentissage, transmission Slime -> Slime, DSL comportemental, mystères persistants, SQLite transactionnel, événements/checkpoints, digest, rapports analytiques, Inbox Observateur, runtime H24, gouvernance persistante, API authentifiée et CI.

## Dette prioritaire

1. migrer la persistance canonique de production vers PostgreSQL durable sans casser l'atomicité monde/gouvernance ;
2. définir et valider le déploiement/supervision H24 du worker et de l'API ;
3. construire React + TypeScript + PixiJS ;
4. automatiser rapports/Drive ;
5. créer Ordre/Chaos comme GPT Projects autonomes puis leurs tâches planifiées ;
6. exporter Conseil/journaux vers Drive sans en faire une source transactionnelle.

## Point de vigilance

SQLite reste la persistance canonique actuelle. Le runtime SQLite est conçu et testé pour un fonctionnement continu contrôlé sur un hôte unique, avec fencing, heartbeat, takeover et reprise déterministe.

L'API/authentification rend la frontière réseau explicite mais ne transforme pas à elle seule le projet en production publique H24. PostgreSQL durable, orchestration/supervision, sauvegardes opérationnelles, TLS et rotation des credentials restent à finaliser.

Une ancienne base contenant une metadata `mode` reste lisible : le loader l'ignore et la clé est supprimée au prochain `save_world`.

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

Construire la persistance PostgreSQL durable de production en conservant les invariants d'atomicité, de writer unique, de gouvernance et de reproductibilité ; ensuite déployer/superviser réellement le worker et l'API H24.
