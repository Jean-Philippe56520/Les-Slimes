from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from les_slimes.analytics import build_world_report
from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.observer import ObserverProposal, apply_proposal
from les_slimes.world.engine import World


st.set_page_config(page_title="Les Slimes — Lab", layout="wide")
st.title("Les Slimes — Lab")
st.caption("Vie artificielle déterministe, apprentissage social et culture rudimentaire")

with st.sidebar:
    st.subheader("Simulation")
    db_path = st.text_input("Base SQLite", str(ROOT / "data" / "world.sqlite"))
    ticks = st.number_input(
        "Ticks à exécuter", min_value=1, max_value=10000, value=250, step=50
    )
    run = st.button("Exécuter", type="primary", use_container_width=True)

repo = SQLiteRepository(db_path)
if not repo.exists():
    st.warning("Aucun monde n'existe encore à cet emplacement.")
    if st.button("Créer le monde par défaut"):
        world = World(WorldConfig.from_yaml(ROOT / "config" / "default.yaml"))
        repo.save_world(world)
        st.rerun()
    st.stop()

world = repo.load_world()
if run:
    world.step(int(ticks))
    repo.save_world(world)
    st.rerun()

metrics = world.metrics()
report = build_world_report(world)

st.caption(f"Mode du monde : **{world.mode.value}**")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Tick", f"{metrics.tick:,}")
c2.metric("Population", metrics.population)
c3.metric("Nourriture", metrics.food_count)
c4.metric("Naissances", metrics.births)
c5.metric("Décès", metrics.deaths)
c6.metric("Génération", metrics.max_generation)

world_tab, inspect_tab, culture_tab, history_tab = st.tabs(
    ["Monde", "Inspecteur", "Culture & société", "Historique"]
)

with world_tab:
    st.subheader("Monde 2D")
    points = [
        {
            "x": s.x,
            "y": s.y,
            "kind": "Slime",
            "size": max(5.0, s.energy / 4.0),
            "id": s.id,
        }
        for s in world.slimes.values()
    ]
    points.extend(
        {
            "x": food.x,
            "y": food.y,
            "kind": "Nourriture",
            "size": 5.0,
            "id": f"FOOD-{food.id}",
        }
        for food in world.foods.values()
    )
    points.extend(
        {
            "x": mystery.x,
            "y": mystery.y,
            "kind": "Mystère",
            "size": max(8.0, mystery.radius * 5.0),
            "id": mystery.id,
        }
        for mystery in world.mysteries.values()
        if mystery.active
    )
    if points:
        st.scatter_chart(
            pd.DataFrame(points),
            x="x",
            y="y",
            color="kind",
            size="size",
            use_container_width=True,
        )

    st.subheader("Interagir avec les Slimes")
    if world.mode.value != "sandbox":
        st.info(
            "Les interventions sont verrouillées dans ce mode. "
            "Utilise un monde Sandbox pour modifier l'environnement."
        )
    else:
        with st.form("player_controls"):
            col_x, col_y = st.columns(2)
            x = col_x.slider("X", 0.0, float(world.config.width), float(world.config.width / 2))
            y = col_y.slider("Y", 0.0, float(world.config.height), float(world.config.height / 2))
            food_count = st.number_input("Nourritures", 1, 20, 3)
            signal = st.selectbox("Signal", World.SIGNALS)
            radius = st.slider(
                "Rayon du signal",
                1.0,
                float(max(world.config.width, world.config.height)),
                float(world.config.signal_radius),
            )
            left, right = st.columns(2)
            add_food = left.form_submit_button("Déposer nourriture", use_container_width=True)
            emit_signal = right.form_submit_button("Émettre signal", use_container_width=True)

        if add_food:
            world.player_deposit_food(x, y, int(food_count))
            repo.save_world(world)
            st.rerun()
        if emit_signal:
            world.player_emit_signal(signal, x, y, radius=radius)
            repo.save_world(world)
            st.rerun()

        st.caption(
            "Pour apprendre un symbole : émettre plusieurs fois le même signal puis déposer "
            "de la nourriture à proximité pendant la fenêtre d'association."
        )

with inspect_tab:
    st.subheader("Inspecteur individuel")
    ids = sorted(world.slimes)
    if not ids:
        st.warning("Population éteinte.")
    else:
        selected = st.selectbox("Slime", ids)
        slime = world.slimes[selected]
        a, b, c = st.columns(3)
        with a:
            st.json(
                {
                    "id": slime.id,
                    "parent": slime.parent_id,
                    "generation": slime.generation,
                    "age_ticks": slime.age_ticks,
                    "energy": round(slime.energy, 3),
                    "health": round(slime.health, 3),
                    "action": slime.current_action,
                    "food_eaten": slime.food_eaten,
                    "offspring": slime.offspring_count,
                    "memory_count": len(slime.memories),
                    "relations": len(slime.relations),
                }
            )
        with b:
            genome_df = pd.DataFrame(
                [{"trait": key, "valeur": value} for key, value in slime.genome.to_dict().items()]
            )
            st.write("**Génome**")
            st.dataframe(genome_df, hide_index=True, use_container_width=True)
        with c:
            signal_rows = [
                {"signal": signal_name, "association_nourriture": strength}
                for signal_name, strength in sorted(slime.signal_food_associations.items())
            ]
            st.write("**Signaux appris**")
            if signal_rows:
                st.dataframe(pd.DataFrame(signal_rows), hide_index=True, use_container_width=True)
            else:
                st.caption("Aucun signal appris.")

        if slime.memories:
            st.write("**Souvenirs alimentaires**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "x": m.x,
                            "y": m.y,
                            "strength": m.strength,
                            "last_seen": m.last_seen_tick,
                        }
                        for m in slime.memories
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )

        if slime.relations:
            st.write("**Relations sociales**")
            relation_rows = [
                {
                    "slime": target_id,
                    "familiarity": relation.familiarity,
                    "trust": relation.trust,
                    "interactions": relation.interactions,
                    "last_tick": relation.last_interaction_tick,
                }
                for target_id, relation in sorted(
                    slime.relations.items(),
                    key=lambda item: item[1].familiarity,
                    reverse=True,
                )[:50]
            ]
            st.dataframe(pd.DataFrame(relation_rows), hide_index=True, use_container_width=True)

with culture_tab:
    st.subheader("Signaux et comportements émergents")
    signal_df = pd.DataFrame.from_dict(report["signals"], orient="index").reset_index()
    signal_df = signal_df.rename(columns={"index": "signal"})
    st.dataframe(signal_df, hide_index=True, use_container_width=True)

    st.subheader("Société")
    social = report["social"]
    a, b = st.columns(2)
    a.metric("Clusters sociaux", social["cluster_count"])
    b.metric("Plus grand cluster", social["largest_cluster_size"])

    st.subheader("Candidats à l'émergence")
    candidates = report["emergence_candidates"]
    if not candidates:
        st.info("Aucun phénomène ne dépasse encore les seuils de détection.")
    for candidate in candidates:
        st.markdown(
            f"**{candidate['kind']}** — confiance heuristique "
            f"{candidate['confidence']:.0%}"
        )
        st.write(candidate["summary"])
        st.json(candidate["evidence"])

    st.subheader("Règles comportementales actives")
    if report["behavior_rules"]:
        rule_rows = [
            {
                "id": rule["id"],
                "name": rule["name"],
                "priority": rule["priority"],
                "action": rule["action"],
                "source": rule["source"],
                "enabled": rule["enabled"],
            }
            for rule in report["behavior_rules"]
        ]
        st.dataframe(pd.DataFrame(rule_rows), hide_index=True, use_container_width=True)
    else:
        st.caption("Aucune règle dynamique ajoutée.")

    st.subheader("Mystères publics")
    if report["mysteries"]:
        st.dataframe(
            pd.DataFrame(report["mysteries"]), hide_index=True, use_container_width=True
        )
    else:
        st.caption("Aucun mystère actif.")

    st.subheader("Inbox Observateur")
    proposal_rows = repo.list_observer_proposals(limit=20)
    if not proposal_rows:
        st.caption("Aucune proposition Observateur.")
    for row in proposal_rows:
        proposal_data = __import__("json").loads(row["proposal_json"])
        with st.expander(
            f"#{row['id']} · {row['status']} · {proposal_data['type']} · "
            f"{proposal_data['confidence']:.0%}"
        ):
            st.write(proposal_data["summary"])
            st.json(proposal_data)
            if row["status"] == "pending" and world.mode.value == "sandbox":
                if st.button("Appliquer / examiner", key=f"proposal_{row['id']}"):
                    proposal = ObserverProposal.from_dict(proposal_data)
                    result = apply_proposal(world, proposal)
                    if result.get("applied"):
                        repo.save_world(world)
                        repo.update_observer_proposal(
                            row["id"], status="applied", result=result
                        )
                    else:
                        repo.update_observer_proposal(
                            row["id"], status="reviewed", result=result
                        )
                    st.rerun()

    st.subheader("Traits de la population")
    trait_df = pd.DataFrame.from_dict(report["traits"], orient="index").reset_index()
    trait_df = trait_df.rename(columns={"index": "trait"})
    st.dataframe(trait_df, hide_index=True, use_container_width=True)

with history_tab:
    st.subheader("Checkpoints")
    checkpoint_rows = [dict(row) for row in reversed(repo.checkpoints(limit=200))]
    if checkpoint_rows:
        checkpoints = pd.DataFrame(checkpoint_rows)
        st.line_chart(checkpoints, x="tick", y=["population", "food_count"])
        st.dataframe(checkpoints.tail(30), hide_index=True, use_container_width=True)

    st.subheader("Événements récents")
    events = pd.DataFrame([dict(row) for row in repo.recent_events(limit=150)])
    if not events.empty:
        st.dataframe(events, hide_index=True, use_container_width=True)
