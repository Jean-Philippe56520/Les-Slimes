# Les Slimes — état courant du projet

Ce fichier sert de point de reprise après changement ou réinitialisation de conversation.

## Repo canonique

- Repo unique : `Jean-Philippe56520/Les-Slimes`
- Branche : `main`
- Application Streamlit actuelle : `streamlit_app.py`
- Streamlit public connu : `https://les-slimes.streamlit.app`
- Aucun autre repo n'est dans le périmètre Les Slimes.

## Décision d'architecture la plus récente

Il existe **un seul monde Les Slimes canonique**, persistant et partagé.

Il ne change jamais de mode.
Les anciens modes `sandbox`, `observation`, `experiment` présents dans le code sont legacy et devront être refactorés.

Les restrictions futures portent sur les permissions/budgets des acteurs.
Les expériences utilisent des forks non canoniques isolés incapables d'écrire dans le monde officiel.

## Architecture cible

- moteur et lois : Python dans `src/les_slimes/` ;
- runtime : World Worker avec horloge canonique, ticks, catch-up, heartbeat, checkpoints et writer unique ;
- commandes : queue persistante, ordonnée, idempotente ;
- frontend principal : React + TypeScript + PixiJS ;
- frontend hébergé sur Netlify ;
- Streamlit conservé comme Lab science/admin/debug ;
- persistance actuelle : SQLite ;
- production future : PostgreSQL durable à choisir après validation ; Supabase n'est pas obligatoire ;
- Drive : rapports, snapshots, expériences et mémoire des dieux, jamais DB active.

Le monde peut être H24 logiquement sans CPU H24 : persister `last_simulated_at_utc` puis rejouer exactement les ticks manquants avec une primitive déterministe `advance_to(target_time)`.

## État technique déjà présent

Le repo contient déjà :
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
- CI.

## Dette/écart vers la cible

À construire/refactorer :
1. runtime canonique + `advance_to(target_time)` ;
2. metadata temps réel (`tick_duration_seconds`, `last_simulated_at_utc`, etc.) ;
3. writer unique/lease ;
4. command queue idempotente ;
5. arrêt des mutations directes depuis Streamlit ;
6. permissions acteurs à la place des modes globaux ;
7. forks d'expériences isolés ;
8. identité/budgets/sanctions/journaux des dieux ;
9. API ;
10. React/TypeScript/PixiJS ;
11. stratégie de persistance distante ;
12. automatisation Drive/rapports ;
13. création des GPT Projects Ordre et Chaos ;
14. tâches planifiées quotidiennes et hebdomadaires des dieux.

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
Les dieux ne peuvent pas supprimer audit, sauvegardes, CI, rollback, modifier leurs propres permissions ou écrire directement dans la DB en contournant le moteur.

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

Ne pas commencer par React/PixiJS.
Commencer par le socle scientifique/runtime :

1. inspecter/retester la baseline actuelle ;
2. benchmarker le coût d'un catch-up représentatif ;
3. concevoir et tester `advance_to(target_time)` ;
4. ajouter metadata temps réel + writer unique + command queue ;
5. prouver : exécution continue == interruption + catch-up au même digest ;
6. ensuite seulement intégrer gouvernance divine et frontend.

Dernière décision fonctionnelle importante : **un seul monde canonique partagé, aucun mode global du monde**.
