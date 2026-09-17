# Contrat de l'Observateur IA

L'Observateur est externe au cerveau des Slimes. Il lit le monde canonique, formule des observations/hypothèses et peut proposer des interventions déclaratives. Il ne modifie jamais directement le monde.

## Flux canonique

1. `les-slimes report` produit un état condensé et mesurable.
2. Le LLM retourne une proposition JSON.
3. `proposal-import` valide le schéma et place la proposition dans l'Inbox.
4. Un acteur autorisé examine la proposition.
5. Une proposition mutante est convertie en description de commande par `proposal_to_command`.
6. L'acteur approbateur soumet cette commande dans la command queue avec `source_proposal_id`.
7. Le `CanonicalWorldWorker` vérifie identité + permission, applique la commande puis persiste l'état et l'événement.
8. Une proposition analytique reste lecture seule et ne crée aucune commande.

L'identité de l'Observateur ne remplace jamais celle de l'acteur qui autorise l'intervention. La provenance doit permettre de distinguer qui a proposé et qui a approuvé.

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
- contourner les permissions de l'acteur approbateur ;
- transformer une hypothèse en conclusion scientifique sans métriques ;
- écrire dans un autre repo.

Toute intervention issue d'une proposition doit être attribuable et traverser la command queue puis le writer unique.
