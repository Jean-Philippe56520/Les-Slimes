import pytest

from les_slimes.divine.sovereign import (
    CreatorDecision,
    LawCandidate,
    SovereignCreatorCycle,
)


def candidate(**overrides) -> LawCandidate:
    data = {
        "actor_id": "chaos",
        "proposal_id": 7,
        "source_main_sha": "a" * 40,
        "main_is_current": True,
        "drive_artifact_id": "drive-law-7",
        "manifest_digest": "b" * 64,
        "patch_digest": "c" * 64,
        "affected_files": (
            "src/les_slimes/world/engine.py",
            "tests/test_engine.py",
        ),
        "artifact_verified": True,
        "patch_verified": True,
        "governance_eligible": True,
        "evidence_complete": True,
    }
    data.update(overrides)
    return LawCandidate(**data)


def test_acceptance_with_all_gates_authorizes_creator_implementation_only():
    review = SovereignCreatorCycle().review(
        candidate(),
        decision=CreatorDecision.ACCEPT,
        reason="Evidence reproduced and proposal artifact verified.",
    )
    assert review.implementation_authorized
    assert review.blockers == ()
    authorization = review.implementation_authorization
    assert authorization is not None
    assert authorization.proposal_id == 7
    assert authorization.candidate_actor_id == "chaos"
    assert authorization.source_main_sha == "a" * 40
    assert authorization.drive_artifact_id == "drive-law-7"
    assert authorization.patch_digest == "c" * 64
    assert authorization.authorized_by == "father"


@pytest.mark.parametrize(
    "decision",
    [
        CreatorDecision.REJECT,
        CreatorDecision.WAIT,
        CreatorDecision.REQUEST_AMENDMENT,
        CreatorDecision.REQUEST_EXPERIMENT,
    ],
)
def test_non_acceptance_never_authorizes_implementation(decision):
    review = SovereignCreatorCycle().review(
        candidate(), decision=decision, reason="No implementation in this cycle."
    )
    assert not review.implementation_authorized


@pytest.mark.parametrize(
    ("overrides", "expected_fragment"),
    [
        ({"actor_id": "observer"}, "restricted to Order and Chaos"),
        ({"proposal_id": 0}, "proposal_id"),
        ({"source_main_sha": "short"}, "source_main_sha"),
        ({"main_is_current": False}, "current main"),
        ({"drive_artifact_id": ""}, "drive_artifact_id"),
        ({"manifest_digest": "short"}, "manifest_digest"),
        ({"patch_digest": "short"}, "patch_digest"),
        ({"affected_files": ()}, "affected_files"),
        ({"affected_files": ("README.md",)}, "invalid Law target"),
        ({"artifact_verified": False}, "artifact has not been verified"),
        ({"patch_verified": False}, "patch digest has not been verified"),
        ({"governance_eligible": False}, "current governance"),
        ({"evidence_complete": False}, "evidence is incomplete"),
        (
            {"experiment_required": True, "experiment_passed": False},
            "isolated experiment",
        ),
        (
            {
                "combined_experiment_required": True,
                "combined_experiment_passed": False,
            },
            "combined experiment",
        ),
    ],
)
def test_acceptance_is_fail_closed_when_any_gate_is_missing(overrides, expected_fragment):
    review = SovereignCreatorCycle().review(
        candidate(**overrides),
        decision=CreatorDecision.ACCEPT,
        reason="Candidate considered for implementation.",
    )
    assert not review.implementation_authorized
    assert any(expected_fragment in blocker for blocker in review.blockers)


def test_creator_reason_is_mandatory():
    with pytest.raises(ValueError):
        SovereignCreatorCycle().review(
            candidate(), decision=CreatorDecision.WAIT, reason="   "
        )
