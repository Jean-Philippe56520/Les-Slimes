from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from les_slimes.analytics import build_world_report
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.governance import GovernanceAdminService
from les_slimes.observer import ObserverProposal, proposal_to_command
from les_slimes.runtime import RuntimeStorage
from les_slimes.world.engine import World


st.set_page_config(page_title="Les Slimes — Lab", layout="wide")
st.title("Les Slimes — Lab")
st.caption("Laboratoire secondaire : lecture, diagnostic et soumission de commandes canoniques")

with st.sidebar:
    db_path = st.text_input("Base SQLite", str(ROOT / "data" / "world.sqlite"))
    st.caption("Le Lab ne pilote pas l'horloge canonique et n'écrit jamais directement dans le monde.")

repo = SQLiteRepository(db_path)
if not repo.exists():
    st.warning("Aucun monde n'existe à cet emplacement. Initialisez-le avec `les-slimes init`.")
    st.stop()

storage = RuntimeStorage(repo)
governance_admin = GovernanceAdminService(repo)
world = repo.load_world()
metrics = world.metrics()
report = build_world_report(world)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Tick", f"{metrics.tick:,}")
c2.metric("Population", metrics.population)
c3.metric("Nourriture", metrics.food_count)
c4.metric("Naissances", metrics.births)
c5.metric("Décès", metrics.deaths)
c6.metric("Génération", metrics.max_generation)

world_tab, inspect_tab, culture_tab, runtime_tab, history_tab = st.tabs(
    ["Monde", "Inspecteur", "Culture & société", "Runtime", "Historique"]
)

with world_tab:
    st.subheader("Monde 2D")
    points = [
        {"x": s.x, "y": s.y, "kind": "Slime", "size": max(5.0, s.energy / 4.0), "id": s.id}
        for s in world.slimes.values()
    ]
    points.extend(
        {"x": food.x, "y": food.y, "kind": "Nourriture", "size": 5.0, "id": f"FOOD-{food.id}"}
        for food in world.foods.values()
    )
    points.extend(
        {"x": mystery.x, "y": mystery.y, "kind": "Mystère", "size": max(8.0, mystery.radius * 5.0), "id": mystery.id}
        for mystery in world.mysteries.values()
        if mystery.active
    )
    if points:
        st.scatter_chart(pd.DataFrame(points), x="x", y="y", color="kind", size="size", use_container_width=True)

    st.subheader("Soumettre une intervention du Père")
    with st.form("father_controls"):
        col_x, col_y = st.columns(2)
        x = col_x.slider("X", 0.0, float(world.config.width), float(world.config.width / 2))
        y = col_y.slider("Y", 0.0, float(world.config.height), float(world.config.height / 2))
        food_count = st.number_input("Nourritures", 1, 20, 3)
        signal = st.selectbox("Signal", World.SIGNALS)
        radius = st.slider("Rayon du signal", 1.0, float(max(world.config.width, world.config.height)), float(world.config.signal_radius))
        left, right = st.columns(2)
        add_food = left.form_submit_button("Mettre en queue : nourriture", use_container_width=True)
        emit_signal = right.form_submit_button("Mettre en queue : signal", use_container_width=True)

    if add_food:
        command = storage.enqueue_command(
            actor_id="father",
            command_type="deposit_food",
            payload={"x": x, "y": y, "count": int(food_count)},
            idempotency_key=f"lab:food:{uuid.uuid4().hex}",
            created_at_utc=datetime.now(UTC),
        )
        st.success(f"Commande {command.id} mise en queue.")
    if emit_signal:
        command = storage.enqueue_command(
            actor_id="father",
            command_type="emit_signal",
            payload={"signal": signal, "x": x, "y": y, "radius": radius},
            idempotency_key=f"lab:signal:{uuid.uuid4().hex}",
            created_at_utc=datetime.now(UTC),
        )
        st.success(f"Commande {command.id} mise en queue.")

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
            st.json({
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
            })
        with b:
            st.write("**Génome**")
            st.dataframe(pd.DataFrame([{"trait": k, "valeur": v} for k, v in slime.genome.to_dict().items()]), hide_index=True, use_container_width=True)
        with c:
            st.write("**Signaux appris**")
            rows = [{"signal": k, "association_nourriture": v} for k, v in sorted(slime.signal_food_associations.items())]
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            else:
                st.caption("Aucun signal appris.")

with culture_tab:
    st.subheader("Signaux et comportements émergents")
    signal_df = pd.DataFrame.from_dict(report["signals"], orient="index").reset_index().rename(columns={"index": "signal"})
    st.dataframe(signal_df, hide_index=True, use_container_width=True)

    social = report["social"]
    a, b = st.columns(2)
    a.metric("Clusters sociaux", social["cluster_count"])
    b.metric("Plus grand cluster", social["largest_cluster_size"])

    st.subheader("Candidats à l'émergence")
    if not report["emergence_candidates"]:
        st.info("Aucun phénomène ne dépasse encore les seuils de détection.")
    for candidate in report["emergence_candidates"]:
        st.markdown(f"**{candidate['kind']}** — confiance heuristique {candidate['confidence']:.0%}")
        st.write(candidate["summary"])

    st.subheader("Inbox Observateur")
    proposal_rows = repo.list_observer_proposals(limit=20)
    if not proposal_rows:
        st.caption("Aucune proposition Observateur.")
    for row in proposal_rows:
        proposal_data = json.loads(row["proposal_json"])
        with st.expander(f"#{row['id']} · {row['status']} · {proposal_data['type']}"):
            st.write(proposal_data["summary"])
            st.json(proposal_data)
            if row["status"] == "pending" and st.button("Approuver comme Père", key=f"proposal_{row['id']}"):
                proposal = ObserverProposal.from_dict(proposal_data)
                converted = proposal_to_command(proposal)
                if converted is None:
                    result = {"queued": False, "reason": "Proposition analytique"}
                    repo.update_observer_proposal(row["id"], status="reviewed", result=result)
                else:
                    command_type, payload = converted
                    command = storage.enqueue_command(
                        actor_id="father",
                        command_type=command_type,
                        payload=payload,
                        idempotency_key=f"lab:proposal:{row['id']}:{uuid.uuid4().hex}",
                        created_at_utc=datetime.now(UTC),
                        source_proposal_id=int(row["id"]),
                    )
                    repo.update_observer_proposal(
                        row["id"],
                        status="queued",
                        result={"command_id": command.id, "approved_by": "father"},
                    )
                st.rerun()

with runtime_tab:
    st.subheader("Command Queue")
    command_rows = [dict(row) for row in storage.recent_commands(limit=100)]
    if command_rows:
        st.dataframe(pd.DataFrame(command_rows), hide_index=True, use_container_width=True)
    else:
        st.caption("Aucune commande.")

    st.subheader("Acteurs et permissions")
    actor_rows = [
        {"id": actor.id, "kind": actor.kind, "active": actor.active, "permissions": ", ".join(sorted(actor.permissions))}
        for actor in storage.list_actors()
    ]
    st.dataframe(pd.DataFrame(actor_rows), hide_index=True, use_container_width=True)

    st.subheader("Gouvernance divine")
    governance_rows = []
    for actor_id in ("father", "order", "chaos"):
        status = governance_admin.status(actor_id)
        governance_rows.append(
            {
                "acteur": actor_id,
                "actif": status["active"],
                "pouvoir": status["max_power_name"],
                "miracle": status["budgets"]["miracle"],
                "legislatif": status["budgets"]["legislative"],
                "faveur": status["budgets"]["favor"],
                "dette_transgression": status["budgets"]["transgression_debt"],
                "sanctions": ", ".join(item["sanction_type"] for item in status["active_sanctions"]),
            }
        )
    st.dataframe(pd.DataFrame(governance_rows), hide_index=True, use_container_width=True)
    st.caption(
        "Administration de la gouvernance : CLI Père uniquement jusqu'à l'API authentifiée. "
        f"Chaîne d'audit valide : {governance_admin.storage.validate_audit_chain()}"
    )

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
