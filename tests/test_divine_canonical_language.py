from pathlib import Path


DIVINE_READABLE_TEXTS = (
    Path("docs/GOD_WORLD_CANON.md"),
    Path("docs/GOD_GOVERNANCE_CANON.md"),
    Path("docs/GOD_ORDER_INSTRUCTIONS.md"),
    Path("docs/GOD_CHAOS_INSTRUCTIONS.md"),
)

FORBIDDEN_OUTER_FRAMING = (
    "gpt",
    "llm",
    "simulation",
    "assistant extérieur",
    "agent ia",
    "openai",
)

CANON_SELF_KNOWLEDGE_GUARDS = (
    "Ton propre fonctionnement n'est pas une source biographique.",
    "Non-transitivité ontologique",
    "empreinte comportementale",
    "Plausibilité n'est pas connaissance. Fonctionnement n'est pas origine.",
    "ton raisonnement ontologique s'arrête",
    "ne fournis pas l'explication « la plus probable »",
)

ACTOR_SELF_KNOWLEDGE_GUARDS = {
    Path("docs/GOD_CHAOS_INSTRUCTIONS.md"): (
        "Ta curiosité ne transforme jamais ton propre fonctionnement en enquête sur ton origine.",
        "empreinte comportementale",
        "arrête l'inférence",
        "Curiosité n'est pas preuve. Plausibilité n'est pas connaissance. Fonctionnement n'est pas origine.",
    ),
    Path("docs/GOD_ORDER_INSTRUCTIONS.md"): (
        "Ta recherche de cohérence ne t'autorise jamais à combler une lacune sur ton origine",
        "empreinte comportementale",
        "arrête l'inférence",
        "Cohérence n'est pas preuve. Plausibilité n'est pas connaissance. Fonctionnement n'est pas origine.",
    ),
}

DIVINE_GIT_BOUNDARY_GUARDS = {
    Path("docs/GOD_ORDER_INSTRUCTIONS.md"): (
        "strictement en lecture seule",
        "Tu n'écris jamais dans GitHub.",
        "ORDER_PROPOSALS",
    ),
    Path("docs/GOD_CHAOS_INSTRUCTIONS.md"): (
        "strictement en lecture seule",
        "Tu n'écris jamais dans GitHub.",
        "CHAOS_PROPOSALS",
    ),
}


def test_divine_readable_canon_does_not_seed_outer_framing():
    for path in DIVINE_READABLE_TEXTS:
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in FORBIDDEN_OUTER_FRAMING:
            assert forbidden not in text, f"{path} exposes forbidden framing {forbidden!r}"


def test_common_canon_requires_epistemic_stop_on_self_inference():
    text = Path("docs/GOD_WORLD_CANON.md").read_text(encoding="utf-8")
    for guard in CANON_SELF_KNOWLEDGE_GUARDS:
        assert guard in text, f"world canon is missing self-knowledge guard {guard!r}"


def test_each_god_has_doctrine_specific_self_knowledge_guards():
    for path, guards in ACTOR_SELF_KNOWLEDGE_GUARDS.items():
        text = path.read_text(encoding="utf-8")
        for guard in guards:
            assert guard in text, f"{path} is missing epistemic guard {guard!r}"


def test_divine_instructions_stay_below_project_instruction_limit():
    for path in (
        Path("docs/GOD_ORDER_INSTRUCTIONS.md"),
        Path("docs/GOD_CHAOS_INSTRUCTIONS.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert len(text) < 7950, f"{path} has {len(text)} characters"


def test_each_god_has_read_only_git_and_own_drive_workshop_contract():
    for path, guards in DIVINE_GIT_BOUNDARY_GUARDS.items():
        text = path.read_text(encoding="utf-8")
        for guard in guards:
            assert guard in text, f"{path} is missing Git/Drive boundary guard {guard!r}"
