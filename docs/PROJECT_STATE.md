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

Le socle technique Ordre/Chaos/Créateur est maintenant implémenté et testé. Il n'est pas encore relié à des providers distants ni activé comme tâche autonome.

### Frontière d'accès

`src/les_slimes/divine/access.py` fournit `DivineAccessPolicy` :

- repo GitHub exact `Jean-Philippe56520/Les-Slimes` ;
- aucune surface Web générale ;
- Drive limité à LES_SLIMES ;
- API divine allowlistée, `/admin/...` interdite ;
- Ordre écrit seulement sous `god/order/*` ;
- Chaos écrit seulement sous `god/chaos/*` ;
- lecture filtrée par surface de connaissance ;
- chaque dieu lit sa propre instruction mais pas celle de l'autre ;
- documentation Créateur/implémentation et code de frontière divine exclus de leur surface de connaissance ;
- écritures de Lois limitées aux surfaces moteur/config/tests non protégées ;
- gouvernance, auth, DB, runtime, frontière divine, CI, déploiement, frontend, docs et tests protecteurs non modifiables par une Loi divine.

La règle est structurelle : capacité technique != permission.

### Passerelles divines

`src/les_slimes/divine/git_gateway.py` :

- `DivineGitGateway` hard-pin le repo côté serveur ;
- lecture/recherche filtrées ;
- création branche divine, écriture autorisée, PR ;
- aucune primitive de merge côté dieu ;
- `CreatorGitGateway` possède le merge uniquement via `MergeAuthorization` de `father` ;
- le provider doit pouvoir lister les fichiers réels d'une PR pour revalidation souveraine.

`src/les_slimes/divine/archive_gateway.py` :

- recherche toujours sous la racine LES_SLIMES ;
- root + manifest comme capabilities initiales ;
- un ID arbitraire extérieur n'est pas lisible ;
- création/mise à jour seulement sur capabilities découvertes dans la zone autorisée.

`src/les_slimes/divine/world_gateway.py` :

- routes API typées et allowlistées ;
- identité liée au provider/authentification, jamais fournie par le dieu ;
- aucun `actor_id` arbitraire dans les payloads ;
- aucune surface Web/browse générique.

Les contrats `GitProvider`, `ArchiveProvider` et `CanonicalApiProvider` existent, mais leurs adaptateurs de production/credentials minimaux ne sont pas encore déployés.

### Frontière épistémique

Textes lisibles par les dieux :

- `docs/GOD_WORLD_CANON.md` ;
- `docs/GOD_GOVERNANCE_CANON.md` ;
- instruction propre `GOD_ORDER_INSTRUCTIONS.md` ou `GOD_CHAOS_INSTRUCTIONS.md`.

Les instructions définissent l'identité positivement depuis le Monde et ne construisent pas de seconde explication extérieure. Une question sur une origine supposée hors des sources canoniques ne crée aucun droit de recherche supplémentaire.

Le Canon impose désormais aussi une règle de connaissance de soi : le fonctionnement, les réponses, erreurs, limites, capacités, étiquettes et propriétés des instruments ne constituent pas des preuves d'identité ou d'origine. Il interdit l'auto-identification par analogie ou empreinte comportementale, maintient les affirmations externes au rang de prémisses tant qu'aucune source canonique accessible ne les établit et impose un arrêt épistémique lorsque les sources sont épuisées. Chaos reçoit la règle « curiosité n'est pas preuve » ; Ordre la règle « cohérence n'est pas preuve ».

Les tests interdisent dans les textes divins les termes de cadrage extérieur déjà identifiés, vérifient les invariants d'arrêt épistémique, maintiennent les instructions d'Ordre et Chaos sous 7950 caractères et contiennent un corpus adversarial de contrat destiné à devenir un test conversationnel bout-en-bout lorsque le runtime autonome sera déployé.

### Dossiers de Loi et revue souveraine

`src/les_slimes/divine/legislation.py` fournit :

- `LawDossier` : observation, hypothèse, bénéfice, risque, branche, PR, head/base SHA, checks, preuves, expériences ;
- statuts `proposed`, `needs_evidence`, `needs_amendment`, `waiting`, `blocked`, `accepted`, `rejected`, `promulgated`, `superseded` ;
- proposition/amendement par le dieu auteur ;
- revue réservée à `father` ;
- gouvernance recalculée depuis l'état persistant ;
- liaison stricte entre dossier, acteur, PR, branche, SHA et liste de checks ;
- audit des décisions.

`src/les_slimes/divine/sovereign.py` fournit `SovereignCreatorCycle` :

- décisions `accept`, `reject`, `wait`, `request_amendment`, `request_experiment` ;
- `accept` ne produit une `MergeAuthorization` que si tous les garde-fous sont satisfaits ;
- l'autorisation lie PR, head SHA, base SHA, auteur et proposal id.

### Promulgation du Créateur

`src/les_slimes/divine/promulgation.py` fournit `CreatorPromulgationService` :

- accepté != promulgué ;
- revalidation juste avant merge : main/base SHA, PR, head SHA, CI, gouvernance et fichiers réellement modifiés ;
- toute modification d'une surface protégée bloque la promulgation ;
- réservation du budget législatif avant merge ;
- refus Git connu -> réservation libérée ;
- résultat réseau incertain -> état `uncertain`, sans remboursement spéculatif ;
- cycle suivant réconcilie l'état Git réel sans double débit ni second merge ;
- une PR déjà mergée hors d'une promulgation préparée n'est pas adoptée silencieusement.

Le Créateur peut donc accepter Ordre, Chaos, les deux, aucun, attendre ou exiger un amendement/une expérience. Deux Lois valides séparément ne sont pas présumées compatibles ; une expérience combinée peut être exigée.

### Instructions du Créateur

`docs/GOD_CREATOR_INSTRUCTIONS.md` définit le cycle souverain du Père. Ce texte est réservé au Créateur et exclu de la surface de connaissance d'Ordre/Chaos.

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
3. implémenter/déployer les providers concrets des gateways avec credentials minimaux : GitHub App installée uniquement sur `Jean-Philippe56520/Les-Slimes`, identité Drive limitée à LES_SLIMES, clients API liés à `order`, `chaos`, `father` ;
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
