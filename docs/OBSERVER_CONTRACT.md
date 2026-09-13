# Contrat de l'Observateur IA

L'Observateur est externe au cerveau des Slimes. Il analyse le monde, formule des hypothèses et peut proposer des modifications déclaratives en Sandbox.

## Flux

1. `les-slimes report` produit un état condensé et mesurable.
2. Le LLM retourne une proposition JSON.
3. `proposal-import` valide le schéma et place la proposition dans l'Inbox.
4. L'humain peut examiner la proposition.
5. `proposal-apply` ou l'UI tente l'application.
6. Le moteur valide l'action via une allowlist.
7. L'état et l'événement sont persistés.

## Types

- `observation` : lecture seule ;
- `hypothesis` : lecture seule ;
- `experiment_proposal` : lecture seule ;
- `behavior_candidate` : ajoute une règle du DSL comportemental ;
- `world_event_proposal` : nourriture ou signal ;
- `mystery_proposal` : ajoute un mystère allowlisté.

## DSL comportemental

Conditions autorisées : énergie, âge, génération, nombre de souvenirs, nombre de relations, force d'une association de signal.

Actions autorisées : repos, exploration, recherche via mémoire, suivi de signal, suivi social, déplacement vers un point.

Aucune action n'accepte du code.

## Sécurité

Le LLM ne peut jamais :

- écrire directement dans SQLite ;
- exécuter du Python ;
- modifier le moteur ;
- injecter une action hors allowlist ;
- intervenir en Observation/Experiment ;
- transformer une hypothèse en conclusion scientifique sans métriques.
