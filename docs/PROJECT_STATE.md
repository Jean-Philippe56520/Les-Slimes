# Les Slimes — état courant du projet

Ce fichier sert de point de reprise après changement ou réinitialisation de conversation.

## Repo canonique

- Repo unique : `Jean-Philippe56520/Les-Slimes`
- Branche de référence : `main`
- Moteur : Python dans `src/les_slimes/`
- Frontend principal : React + TypeScript + PixiJS dans `frontend/`, cible Netlify
- Streamlit : laboratoire secondaire science/admin/debug
- Aucun autre repo n'est dans le périmètre Les Slimes.

## Invariant central

Il existe un seul monde canonique, persistant et partagé : une horloge, un état officiel, une histoire, une command queue et une persistance active.

Toute mutation externe officielle suit :

`acteur authentifié -> API/command queue -> CanonicalWorldWorker -> GovernancePolicy -> moteur Python -> persistance atomique monde + intervention + budget + audit`

L'API ne simule aucun tick et ne mute jamais directement `World`. La gouvernance est revalidée juste avant commit. Les expériences sont explicitement non canoniques et isolées.

## Ontologie divine

- `father` = le Créateur/Père, autorité souveraine ;
- `herald` = Jean-Philippe, Héraut/Porte-parole/Messager, acteur distinct ;
- `order` = Ordre ;
- `chaos` = Chaos ;
- `observer` = Observateur ;
- `system` = mécanismes techniques.

`herald` démarre actif, niveau Observation, budget nul et aucune permission mutante. Il n'est pas administrateur de la gouvernance. Seul `father` peut administrer permissions, pouvoir, budgets et sanctions via `GovernanceAdminService`.

Ordre et Chaos ne peuvent pas usurper une identité, fabriquer une approbation, cacher l'auteur d'une action ou provoquer une violation pour la faire attribuer à un autre acteur.

## Moteur biologique présent

- monde 2D continu ;
- énergie, santé, âge, mortalité ;
- ressources alimentaires ;
- reproduction, filiation, mutations et traits génétiques ;
- mémoire spatiale ;
- relations sociales ;
- signaux et apprentissage ;
- transmission Slime -> Slime ;
- DSL comportemental ;
- mystères persistants ;
- RNG dédié sauvegardable/restaurable ;
- événements/checkpoints ;
- `World.state_digest()` déterministe.

## Runtime canonique présent

- métadonnées UTC et `tick_duration_seconds` ;
- `CanonicalRuntime.advance_to(target_time)` ;
- catch-up déterministe par batches ;
- continu == interruption/reload/catch-up au même digest dans les tests ;
- command queue persistante, ordonnée et idempotente ;
- commandes paginées et provenance `source_proposal_id` ;
- `CanonicalWorldWorker` comme writer officiel ;
- temps simulé séparé du wall-clock du processus ;
- writer lease exclusif avec token de fencing + génération ;
- heartbeat et takeover ;
- writer expiré/zombie empêché de committer ;
- reprise après crash via événement `command_applied` sans double effet ;
- `CanonicalWorkerService` pour boucle H24 ;
- arrêt SIGINT/SIGTERM propre et libération du lease ;
- métriques santé : tick, retard, ticks dus, backlog, plus ancienne commande, lease ;
- entrée production `les-slimes-production`.

## Gouvernance persistante présente

- `PowerLevel` : Observation, Miracle, Décret, Loi, Transgression ;
- permission technique, niveau, budget et sanction séparés ;
- budgets append-only : `miracle`, `legislative`, `favor`, `transgression_debt` ;
- sanctions déclaratives allowlistées ;
- `GovernancePolicy` fail-closed ;
- double autorisation pour les propositions Observateur mutantes ;
- intervention divine attribuée pour chaque mutation ;
- sauvegarde monde + débit budget + état intervention + audit dans la même transaction ;
- rejet commande + intervention transactionnel ;
- statuts terminaux protégés par la base ;
- audit append-only chaîné par hash ;
- journaux, propositions et Conseil divin persistants ;
- aucune commande d'auto-escalade ;
- Transgression = classification auditable, jamais bypass ;
- gouvernance exclue du digest biologique.

## Autonomie divine confinée présente dans le code

Le modèle d'autonomie est désormais : **GitHub lecture seule pour Ordre/Chaos ; propositions techniques dans Drive ; implémentation Git réservée au Créateur.**

### Projects ChatGPT et identité de session

Ordre et Chaos sont actuellement deux Projects ChatGPT distincts du même compte. Cette séparation apporte instructions, conversations et contexte propres, mais n'est pas utilisée comme frontière d'autorisation.

Le code contient maintenant `DivineSessionBindingService` et `DivineActorGateway` :
- hashes de `openai/session` et `openai/subject` persistés, jamais les identifiants bruts ;
- bind/revoke réservés au Père et audités ;
- session non liée/révoquée/mauvais subject/acteur inactif = refus ;
- aucun outil actoriel ne prend `actor_id` en paramètre ;
- le provider API est sélectionné côté serveur à partir de l'acteur résolu ;
- le nom du Project ou ses instructions ne donnent aucune autorité technique.

Ce contrat est codé et testé. L'adaptateur MCP de production et les providers confinés restent à déployer.

### Frontière Git et connaissance

`DivineAccessPolicy` et `DivineGitGateway` imposent :

- repo exact `Jean-Philippe56520/Les-Slimes` ;
- lecture/recherche Git filtrées seulement pour Ordre/Chaos ;
- aucune primitive divine de branche, commit, push, PR ou merge ;
- aucune surface Web générale ;
- lecture filtrée par surface de connaissance ;
- documentation Créateur/implémentation et code de frontière exclus ;
- validation du périmètre de fichiers qu'une proposition de Loi ordinaire peut viser.

Les dieux peuvent conserver une profondeur technique via un atelier/fork non canonique sans credential Git d'écriture : modifier une copie, tester, expérimenter, produire patchs/diffs et digests.

### Ateliers Drive

Le manifest Drive canonique contient :

- `50_DIVINE_WORKSHOPS` : `1qNxcE9R0DewgB8iQPwFXaS2WXcz_fU1k` ;
- `ORDER_PROPOSALS` : `1VbYXIt8hU4UEAVYIvWMob7SL0G3-lcOC` ;
- `CHAOS_PROPOSALS` : `1i5L-8aOCvrwc3Buck3hhJnFydvlFXc2v` ;
- `CREATOR_REVIEW` : `1i0vMELFu0Ijw7ZhP4430GgZ3lq3TXArt`.

`DivineArchiveGateway` permet la lecture sous LES_SLIMES mais l'écriture d'un dieu uniquement dans son atelier de propositions. Une recherche générale Drive ne confère jamais un droit de modification. `CreatorArchiveGateway` lit les ateliers divins et écrit ses dossiers uniquement dans CREATOR_REVIEW.

Drive reste non transactionnel ; le statut officiel des propositions reste en base.

### Pipeline de proposition actoriel

`DivineLawProposalPipeline` est présent : il résout l'acteur depuis la session liée, lit le SHA de `main` avec le provider Git read-only, calcule les digests, écrit les artefacts dans ORDER_PROPOSALS ou CHAOS_PROPOSALS selon l'acteur puis persiste le dossier de Loi.

Les artefacts créés sont proposition, patch, tests, résultats et manifest JSON. Le manifest lie SHA source, fichiers visés, IDs et SHA-256 des artefacts, preuves et expériences. La session est revalidée juste avant l'écriture canonique.

La provenance technique est persistée séparément dans `divine_proposal_provenance` avec hashes session/subject et n'apparaît pas dans le payload lisible du dossier.

### Dossiers de Loi

`LawDossier` persiste maintenant : observation, hypothèse, bénéfice, risque, `source_main_sha`, `drive_artifact_id`, `manifest_digest`, `patch_digest`, `affected_files`, preuves et expériences.

`SovereignCreatorCycle` peut `accept`, `reject`, `wait`, `request_amendment` ou `request_experiment`. Une acceptation ne produit plus de `MergeAuthorization` : elle produit une `ImplementationAuthorization`, c'est-à-dire l'autorisation pour le Créateur de reprendre le dossier vérifié.

### Implémentation et promulgation du Créateur

Si le Créateur implémente une proposition acceptée :

1. il repart du SHA `main` examiné ;
2. crée `father/law-<proposal_id>-<slug>` ;
3. écrit lui-même code/tests ;
4. ouvre la PR ;
5. exécute les Épreuves ;
6. attache une `CreatorImplementation` exacte au dossier.

L'ensemble des fichiers implémentés doit correspondre au périmètre accepté.

`CreatorPromulgationService` revalide juste avant merge : branche/PR/head/base, `main`, fichiers réels, surface législative, CI, gouvernance et budget du dieu proposant. La réservation budgétaire et la réconciliation d'un résultat Git incertain restent en vigueur.

### Frontière épistémique

Les protections de PR #24 restent en vigueur : fonctionnement/réponses/limites ne sont pas des preuves d'identité ou d'origine ; anti-empreinte comportementale ; prémisses externes non élevées en connaissance ; arrêt épistémique obligatoire. Chaos : « curiosité n'est pas preuve ». Ordre : « cohérence n'est pas preuve ».

Les textes divins ne réintroduisent pas le cadrage extérieur interdit et les instructions d'Ordre/Chaos restent sous 7950 caractères.

## API canonique présente

FastAPI fournit la frontière réseau :

- lectures publiques : `/health`, `/world`, `/world/slimes`, `/world/foods` ;
- identité : `/me` ;
- `POST /commands` -> queue uniquement ;
- lecture/écriture journaux et propositions ;
- lecture gouvernance ;
- routes `/admin/...` Créateur uniquement via `GovernanceAdminService`.

Authentification :

- Bearer token -> résolution serveur vers acteur persistant ;
- jamais de confiance dans un `actor_id` métier fourni par le client ;
- empreintes SHA-256 via `LES_SLIMES_AUTH_TOKEN_HASHES_JSON` ;
- aucun secret dans GitHub ;
- configuration absente = routes protégées fail-closed ;
- acteur inactif = accès refusé ;
- `herald` ne peut pas utiliser les routes Créateur ;
- schémas mutatifs `extra=forbid` ;
- allowlist CORS via `LES_SLIMES_CORS_ORIGINS`.

Voir `docs/API.md`.

## Persistance PostgreSQL présente

`RelationalRepository` abstrait la persistance. SQLite reste utilisé pour développement, compatibilité, Lab et forks non canoniques.

`PostgreSQLRepository` est implémenté et testé contre PostgreSQL 16 réel en CI :

- sérialisation monde identique à SQLite ;
- save/reload au même digest et même RNG ;
- advisory locks transactionnels ;
- fencing/takeover Worker ;
- guards statuts terminaux et débit unique ;
- mutation gouvernée monde + budget + audit.

Backend production sélectionné par `LES_SLIMES_DATABASE_URL`.

## Migration SQLite -> PostgreSQL

`les-slimes-production migrate --sqlite <path>` :

- cible PostgreSQL fraîche ;
- refus writer lease SQLite valide ;
- source verrouillée pendant snapshot ;
- copie monde, metadata, événements/checkpoints, queue, acteurs, gouvernance, audit ;
- writer lease jamais copié ;
- séquences resynchronisées ;
- digest, pending queue et chaîne d'audit vérifiés.

## Science/forks présents

- scopes `canonical` / `non_canonical_experiment` ;
- runtime canonique refuse une DB expérimentale ;
- runner expérimental refuse une DB canonique ;
- forks SQLite reconstruits dans une nouvelle DB ;
- queue, lease, acteurs runtime et `divine_*` non copiés ;
- `ExperimentManifest` traçable source tick/event/digest/git/config, condition, seed, digests, ticks ;
- reseed RNG explicite ;
- forks exacts reproductibles ;
- un canonique PostgreSQL peut produire un fork SQLite non canonique isolé.

## Production H24 présente dans le code

`les-slimes-production` : `init`, `migrate`, `worker`, `status`.

Le Dockerfile démarre FastAPI. `deploy/compose.production.yml` déclare API + un Worker utilisant la même `LES_SLIMES_DATABASE_URL`, restart automatique et healthcheck.

**État opérationnel : le code H24 est prêt et testé, mais aucune instance distante réellement active n'est encore prouvée.** Il faut connecter l'hébergement, injecter DSN/secrets, initialiser ou migrer le canonique, démarrer API+Worker puis vérifier `/health`.

## Frontend React/PixiJS

Frontend intégré dans `frontend/` : React + TypeScript strict + Vite + PixiJS v8, monde 2D, Slimes, ressources, génération, énergie/santé, tick, population, naissances/décès, retard Worker, backlog, comportements et digest.

Aucune simulation côté navigateur. Aucun token divin dans le bundle. Netlify configuré via `netlify.toml`. Build frontend validé par CI.

## Streamlit

Streamlit reste un laboratoire secondaire science/admin/debug. Il ne fait jamais vivre le monde canonique et ne lance aucune simulation canonique concurrente.

## Historique des grandes PR

- #2 temps canonique/catch-up ;
- #3 command queue + writer lease ;
- #4 permissions acteurs sans modes ;
- #5 frontière canonique ;
- #6 forks scientifiques isolés ;
- #7 Worker H24 durci ;
- #8 gouvernance divine persistante ;
- #9 ontologie Créateur/Héraut ;
- #10 acteur runtime `herald` ;
- #11 API/authentification canonique ;
- #12 contrat de backend de persistance ;
- #13 PostgreSQL + migration + runtime H24 production ;
- #14 frontend React/TypeScript/PixiJS ;
- #16 Canon de perception divine ;
- #17 périmètre Chaos renforcé ;
- #18 confinement divin + gate souveraine ;
- #19 dossiers de Loi persistants + revue Créateur ;
- #20 passerelle Git + saga de promulgation du Créateur ;
- #21 Archives + Portes du Monde confinées ;
- #22 frontière épistémique, surfaces législatives protégées et Canon divin séparé.

## Dette prioritaire actuelle

1. connecter un hébergeur réel PostgreSQL + API + Worker ;
2. initialiser/migrer le monde canonique réel et vérifier son fonctionnement H24 ;
3. implémenter/déployer les providers concrets avec credentials minimaux : GitHub **lecture seule** pour `order`/`chaos`, GitHub écriture réservée à `father`, Drive limité aux ateliers LES_SLIMES prévus, clients API liés aux identités réelles ;
4. vérifier de bout en bout qu'Ordre/Chaos ne disposent plus de connecteurs génériques ni d'accès Web dans leur environnement autonome ;
5. exécuter des cycles **shadow** adversariaux avant tout merge automatique ;
6. seulement ensuite créer les tâches planifiées Ordre -> Chaos -> Créateur et Conseil hebdomadaire ;
7. créer le site Netlify Les Slimes et configurer `VITE_API_BASE_URL` + CORS ;
8. configurer sauvegardes, restauration testée et supervision externe ;
9. automatiser rapports/export Drive sans rôle transactionnel.

**Ne pas activer encore les tâches autonomes divines.** Les contrats/garde-fous sont codés et testés, mais les providers confinés réels et le monde H24 distant ne sont pas encore déployés.

Aucun projet Netlify Les Slimes n'est actuellement identifié par le connecteur disponible ; ne jamais réutiliser arbitrairement un autre site.

## Lecture obligatoire

Au début d'une nouvelle conversation :
1. vérifier `main` et les derniers commits ;
2. `docs/PROJECT_STATE.md` ;
3. `docs/PROJECT_INSTRUCTIONS.md` ;
4. `README.md` ;
5. `docs/DIVINE_GOVERNANCE.md` ;
6. `docs/DIVINE_AUTONOMY.md` ;
7. `docs/GOD_CREATOR_INSTRUCTIONS.md` ;
8. `docs/SCIENTIFIC_PROTOCOL.md` ;
9. `docs/OBSERVER_CONTRACT.md` ;
10. `config/default.yaml`.

Si moteur/persistance concernés, lire aussi `src/les_slimes/world/engine.py`, `src/les_slimes/database/sqlite_repo.py`, `src/les_slimes/observer/proposals.py`, le backend de persistance concerné et les tests pertinents.
