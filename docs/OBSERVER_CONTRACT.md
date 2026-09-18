# Contrat de l'Observateur IA

L'Observateur est externe au cerveau des Slimes. Il lit le monde canonique, formule des observations/hypothèses et peut proposer des interventions déclaratives. Il ne modifie jamais directement le monde.

## Flux canonique

1. `les-slimes report` produit un état condensé et mesurable.
2. Le LLM retourne une proposition JSON.
3. `proposal-import` valide le schéma et place la proposition dans l'Inbox.
4. Un acteur autorisé examine la proposition.
5. Une proposition mutante est convertie en description de commande par `proposal_to_command`.
6. L'acteur approbateur soumet cette commande dans la command queue avec `source_proposal_id`.
7. Le `CanonicalWorldWorker` vérifie identité, permission technique, niveau de pouvoir, sanctions et budget.
8. Une commande provenant de l'Observateur exige en plus `observer.apply_proposal`.
9. Si l'autorisation est valide, l'application du monde, le débit éventuel du budget et l'audit sont persistés atomiquement.
10. Une proposition analytique reste lecture seule et ne crée aucune commande.

L'identité de l'Observateur ne remplace jamais celle de l'acteur qui autorise l'intervention. La provenance distingue qui a proposé et qui a approuvé.

## Double autorisation

Une proposition mutante de l'Observateur ne suffit jamais à donner un pouvoir.

L'acteur approbateur doit posséder simultanément :

- `observer.apply_proposal` ;
- la permission de la commande finale ;
- le niveau de pouvoir requis ;
- le budget requis, sauf exemption explicite du Père ;
- aucune sanction bloquante.

Exemple : une proposition `deposit_food` approuvée par Ordre nécessite à la fois `observer.apply_proposal` et `world.deposit_food`, un niveau Miracle et un budget Miracle disponible.

## Types

- `observation` : lecture seule ;
- `hypothesis` : lecture seule ;
- `experiment_proposal` : lecture seule ;
- `behavior_candidate` : peut devenir `add_behavior_rule` ;
- `world_event_proposal` : peut devenir `deposit_food` ou `emit_signal` ;
- `mystery_proposal` : peut devenir `add_mystery`.

## DSL comportemental

Conditions autorisées : énergie, âge, génération, nombre de souvenirs, nombre de relations, force d'une association de signal.

Actions autorisées : repos, exploration, recherche via mémoire, suivi de signal, suivi social, déplacement vers un point.

Aucune action n'accepte du code.

## Sécurité

L'Observateur ne peut jamais :

- écrire directement dans SQLite ;
- appeler une primitive mutante de `World` depuis son flux externe ;
- exécuter du Python arbitraire ;
- modifier le moteur ;
- injecter une action hors registre de commandes/allowlist ;
- contourner la gouvernance de l'acteur approbateur ;
- prêter ses propres droits à l'acteur approbateur ;
- transformer une hypothèse en conclusion scientifique sans métriques ;
- écrire dans un autre repo.

Toute intervention issue d'une proposition doit être attribuable et traverser la command queue, la gouvernance puis le writer unique.


## Observations périodiques du Monde

L'Observateur et les dieux peuvent travailler à partir d'états datés sans accès direct au moteur. Les exports d'observation sont des projections read-only de la base canonique et doivent toujours conserver tick, horodatage UTC et `state_digest`.

Une suite de snapshots permet d'étudier des trajectoires ; elle ne transforme jamais une corrélation temporelle en preuve causale. Toute conclusion importante reste soumise aux exigences multi-seeds/contrôle du protocole scientifique.

Drive peut archiver ces exports mais ne devient jamais la source transactionnelle du Monde.
