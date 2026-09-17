# Les Slimes — état courant du projet

Ce fichier sert de point de reprise après changement ou réinitialisation de conversation.

## Repo canonique

- Repo unique : `Jean-Philippe56520/Les-Slimes`
- Branche : `main`
- Frontend cible : React + TypeScript + PixiJS sur Netlify
- Streamlit actuel : prototype/laboratoire secondaire, pas l'application cible
- Aucun autre repo n'est dans le périmètre Les Slimes.

## Décision d'architecture

Il existe **un seul monde Les Slimes canonique**, persistant et partagé.

Il ne change jamais de mode.
Les anciens modes `sandbox`, `observation`, `experiment` encore présents dans le moteur sont legacy et doivent être refactorés.

Les restrictions portent sur les permissions/budgets des acteurs.
Les expériences utilisent des forks non canoniques isolés incapables d'écrire dans le monde officiel.

## Architecture cible

- moteur et lois : Python dans `src/les_slimes/` ;
- runtime : World Worker avec horloge canonique, ticks, catch-up, heartbeat, checkpoints et writer unique ;
- commandes : queue persistante, ordonnée, idempotente ;
- frontend principal : React + TypeScript + PixiJS ;
- frontend hébergé sur Netlify ;
- Streamlit : Lab science/admin/debug uniquement ;
- persistance actuelle : SQLite ;
- production future : PostgreSQL durable à choisir après validation ; Supabase n'est pas obligatoire ;
- Drive : rapports, snapshots, expériences et mémoire des dieux, jamais DB active.

## Runtime canonique désormais implémenté

Le socle temps/persistance a été ajouté sur `main` :

- `tick_duration_seconds` dans la configuration ;
- métadonnées UTC canoniques persistées ;
- `CanonicalRuntime.advance_to(target_time)` ;
- calcul exact des ticks complets dus ;
- catch-up par batches bornés ;
- réconciliation du temps canonique depuis le tick réellement sauvegardé ;
- test prouvant qu'exécution continue et interruption + reload + catch-up convergent vers le même digest ;
- command queue SQLite persistante et ordonnée ;
- clé d'idempotence pour empêcher les doublons de requête ;
- lease de writer exclusif ;
- `CanonicalWorldWorker` comme chemin cible unique de mutation ;
- événement `command_applied` persisté avec le monde pour permettre une reprise après crash sans double effet ;
- premières commandes allowlistées : dépôt de nourriture et émission de signal.

PR intégrées :
- `#2 feat: add canonical time catch-up runtime` ;
- `#3 feat: add canonical command queue and writer lease`.

## État technique déjà présent

Le repo contient :
- moteur 2D déterministe ;
- RNG dédié/restaurable ;
- génétique, reproduction, filiation ;
- énergie/santé/âge/mortalité ;
- ressources ;
- mémoire spatiale ;
- relations sociales ;
- signaux symboliques/apprentissage ;
- transmission Slime -> Slime ;
- DSL comportemental ;
- mystères persistants ;
- SQLite transactionnel ;
- événements/checkpoints ;
- digest d'état ;
- rapports analytiques ;
- Inbox Observateur ;
- tests déterminisme/persistance ;
- horloge canonique + catch-up ;
- writer lease ;
- command queue ;
- CI.

## Dette/écart vers la cible

À construire/refactorer maintenant :
1. permissions/identités acteurs à la place des modes globaux ;
2. retirer les mutations directes de Streamlit et le réduire à un Lab client ;
3. forks d'expériences isolés ;
4. renforcer le worker H24 : heartbeat réel, supervision et stratégie de reprise ;
5. identité/budgets/sanctions/journaux des dieux ;
6. API ;
7. React/TypeScript/PixiJS ;
8. stratégie de persistance distante PostgreSQL ;
9. automatisation Drive/rapports ;
10. création des GPT Projects Ordre et Chaos ;
11. tâches planifiées quotidiennes et hebdomadaires des dieux.

## Point de vigilance runtime

Le writer lease et la command queue constituent le socle, mais le monde n'est pas encore considéré prêt pour la production H24. Avant exposition réseau il faut notamment :
- supprimer la dépendance aux modes legacy ;
- appliquer des permissions d'acteur aux commandes ;
- empêcher les interfaces de muter directement le moteur ;
- durcir le heartbeat du worker pendant les longs catch-up ;
- tester davantage les crash windows et la concurrence.

## Gouvernance divine décidée

Phase initiale : deux GPT Projects autonomes.

### Ordre
Favorise stabilité, structures, continuité, résilience, coopération durable et transmission fiable.

### Chaos
Favorise diversité, variation, exploration, nouveauté et rupture des équilibres stériles.

Ils observent et influencent le même monde.
Aucun ne commande directement un Slime.

Niveaux de pouvoir prévus :
1. observation ;
2. miracle via primitive existante ;
3. décret via DSL ;
4. loi moteur limitée avec budget ;
5. transgression interne rare, journalisée et sanctionnable.

Jean-Philippe est le Père : budgets, récompenses, sanctions, permissions et Constitution.

## Sécurité agents

Repo unique autorisé : `Jean-Philippe56520/Les-Slimes`.
Les autres repos doivent être ignorés même si un connecteur y donne techniquement accès.
Toute action doit rester attribuable/auditable.
Les dieux ne peuvent pas supprimer audit, sauvegardes, CI, rollback, modifier leurs propres permissions ou écrire directement dans la DB en contournant le moteur/command queue.

## Instructions à lire

Toujours lire au début d'une nouvelle conversation :
1. `docs/PROJECT_STATE.md`
2. `docs/PROJECT_INSTRUCTIONS.md`
3. `README.md`
4. `docs/DIVINE_GOVERNANCE.md`

Puis selon le travail :
- `docs/GOD_ORDER_INSTRUCTIONS.md`
- `docs/GOD_CHAOS_INSTRUCTIONS.md`
- `docs/SCIENTIFIC_PROTOCOL.md`
- `docs/OBSERVER_CONTRACT.md`
- `config/default.yaml`
- code/tests concernés.

## Drive canonique

- racine LES_SLIMES : `1NzXVNZTIiEeiJCehBfdBNASk3-JRSHFc`
- 00_SYSTEM : `1uc52qsV_5LUQF-kGbypqXE0iLlHj2V7S`
- manifest : `1F20p302TW9c4ANbbfvhg7OO0l4BBkpMquxxjVTcI91c`
- 10_DAILY_REPORTS : `10qZZQfyCrqfW40k_0sEmI2FQSuDa8T3e`
- 20_OBSERVER : `1Tb6bXKNB1NyDPR3lAdBC1zKEfG-rIQGR`
- inbox : `11Rof4x6im2nUgOKEqUDCPFwcifbd2W_c`
- applied : `1H1NUSOEPTNTtv307L0SKHTUMMyPjnjCJ`
- rejected : `1hr0EO-b0L5nj0ZsLw6qy-S-_3yybS80e`
- journal : `1H5vjNiURRHe53kSIgt3b7hkqYa8Y8Md3`
- 30_SNAPSHOTS : `1Dwj63-958FUAiFZe3cl-P3WyBvfns06r`
- 40_EXPERIMENTS : `1Fl7i_y6NdzpvBG1X-r9-_XjeJY0FRBiR`
- 90_BILANS : `14mgbIOs4654FXhuSosO3Ae-JMUDZb13b`

## Prochaine action recommandée

Le socle temps + queue + writer est désormais présent.

Prochaine séquence :
1. remplacer les modes globaux par des identités/permissions d'acteurs ;
2. faire passer toutes les mutations externes par la command queue ;
3. transformer Streamlit en Lab lecture/admin sans simulation concurrente ;
4. isoler formellement les forks d'expériences ;
5. construire ensuite l'API puis le frontend React/PixiJS.

Dernière décision fonctionnelle importante : **un seul monde canonique partagé, aucun mode global du monde**.
