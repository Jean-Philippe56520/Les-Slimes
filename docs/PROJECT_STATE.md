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

Le monde canonique ne change jamais de mode. Les anciens modes globaux ont été retirés du moteur, du digest et de la persistance. Les restrictions portent sur les acteurs, permissions et, à terme, budgets/sanctions.

Toute mutation externe officielle suit désormais :

`acteur -> permission -> command queue persistante -> CanonicalWorldWorker -> moteur Python -> persistance`

Les expériences sont explicitement non canoniques et doivent rester isolées de la persistance officielle.

## Runtime canonique présent

- `tick_duration_seconds` et métadonnées UTC persistées ;
- `CanonicalRuntime.advance_to(target_time)` ;
- catch-up déterministe par batches ;
- test continu == interruption + reload + catch-up au même digest ;
- command queue SQLite persistante, ordonnée et idempotente ;
- lease de writer exclusif ;
- `CanonicalWorldWorker` comme chemin unique de mutation externe ;
- événements `command_applied` pour reprise après crash sans double effet ;
- acteurs persistants : `father`, `order`, `chaos`, `observer`, `system` ;
- permissions vérifiées avant application ;
- registre central des commandes : nourriture, signal, ajout/retrait règle comportementale, ajout/retrait mystère ;
- validation du payload avant insertion en queue ;
- provenance `source_proposal_id` pour les commandes issues de l'Observateur ;
- CLI mutatif converti en enqueue/worker ;
- Streamlit converti en Lab lecture/admin + enqueue, sans simulation concurrente ;
- Observateur convertit ses propositions en commandes mais ne modifie plus directement `World` ;
- test architectural empêchant les principaux contournements de la frontière canonique.

PR intégrées ou en cours :
- `#2 feat: add canonical time catch-up runtime` ;
- `#3 feat: add canonical command queue and writer lease` ;
- `#4 refactor: replace world modes with actor permissions` ;
- `#5 refactor: enforce canonical command boundary`.

## État technique moteur

Le repo contient notamment : moteur 2D déterministe, RNG dédié/restaurable, génétique, reproduction, filiation, énergie/santé/âge/mortalité, ressources, mémoire spatiale, relations sociales, signaux et apprentissage, transmission Slime -> Slime, DSL comportemental, mystères persistants, SQLite transactionnel, événements/checkpoints, digest d'état, rapports analytiques, Inbox Observateur et CI.

## Dette prioritaire

1. formaliser les forks scientifiques isolés : snapshot source, `canonical=false`, interdiction technique d'écriture canonique ;
2. durcir le worker H24 : heartbeat réel pendant longs catch-up, supervision, reprise et tests de concurrence ;
3. brancher budgets/sanctions/journaux divins sur les permissions ;
4. construire l'API Python ;
5. construire React + TypeScript + PixiJS ;
6. choisir la persistance PostgreSQL de production ;
7. automatiser rapports/Drive ;
8. créer Ordre/Chaos comme GPT Projects autonomes puis leurs tâches planifiées.

## Point de vigilance

Le monde n'est pas encore prêt pour production H24. Le worker doit encore être durci avant exposition réseau. Les expériences doivent également être isolées structurellement avant d'être considérées sûres.

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

Construire les forks scientifiques explicitement non canoniques, puis durcir le worker H24. Ne pas démarrer React/PixiJS avant ces deux verrous.
