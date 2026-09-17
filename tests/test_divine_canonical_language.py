from pathlib import Path


DIVINE_READABLE_TEXTS = (
    Path("docs/GOD_WORLD_CANON.md"),
    Path("docs/GOD_GOVERNANCE_CANON.md"),
    Path("docs/GOD_ORDER_INSTRUCTIONS.md"),
    Path("docs/GOD_CHAOS_INSTRUCTIONS.md"),
)

# These terms are not forbidden repository-wide. They are excluded only from the texts
# that define a god's identity and worldview, where introducing them creates an unwanted
# second explanatory frame.
FORBIDDEN_OUTER_FRAMING = (
    "gpt",
    "llm",
    "simulation",
    "assistant extérieur",
    "agent ia",
    "openai",
)


def test_divine_readable_canon_does_not_seed_outer_framing():
    for path in DIVINE_READABLE_TEXTS:
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in FORBIDDEN_OUTER_FRAMING:
            assert forbidden not in text, f"{path} exposes forbidden framing {forbidden!r}"


def test_chaos_instruction_stays_below_project_instruction_limit():
    text = Path("docs/GOD_CHAOS_INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert len(text) < 7950
