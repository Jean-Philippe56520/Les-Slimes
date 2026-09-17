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
        "branch": "god/chaos/adaptive-niches",
        "pr_number": 42,
        "head_sha": "a" * 40,
        "base_sha": "b" * 40,
        "base_is_current": True,
        "pr_is_open": True,
        "pr_is_mergeable": True,
        "required_checks": ("python", "postgres", "docker"),
        "passed_checks": frozenset({"python", "postgres", "docker"}),
        "governance_eligible": True,
        "evidence_complete": True,
    }
    data.update(overrides)
    return LawCandidate(**data)


def test_acceptance_with_all_gates_binds_exact_reviewed_pr_and_shas():
    review = SovereignCreatorCycle().review(
        candidate(),
        decision=CreatorDecision.ACCEPT,
        reason="Evidence reproduced and all required checks passed.",
    )

    assert review.promulgation_authorized
    assert review.blockers == ()
    authorization = review.merge_authorization
    assert authorization is not None
    assert authorization.repository_full_name == "Jean-Philippe56520/Les-Slimes"
    assert authorization.pr_number == 42
    assert authorization.expected_head_sha == "a" * 40
    assert authorization.expected_base_sha == "b" * 40
    assert authorization.authorized_by == "father"
    assert authorization.candidate_actor_id == "chaos"
    assert authorization.proposal_id == 7


@pytest.mark.parametrize(
    "decision",
    [
        CreatorDecision.REJECT,
        CreatorDecision.WAIT,
        CreatorDecision.REQUEST_AMENDMENT,
        CreatorDecision.REQUEST_EXPERIMENT,
    ],
)
def test_non_acceptance_never_authorizes_promulgation(decision):
    review = SovereignCreatorCycle().review(
        candidate(), decision=decision, reason="No promulgation in this cycle."
    )
    assert not review.promulgation_authorized


@pytest.mark.parametrize(
    ("overrides", "expected_fragment"),
    [
        ({"actor_id": "observer", "branch": "god/observer/x"}, "restricted to Order and Chaos"),
        ({"branch": "main"}, "may write only"),
        ({"branch": "god/order/foreign"}, "may write only"),
        ({"proposal_id": 0}, "proposal_id"),
        ({"pr_number": 0}, "pr_number"),
        ({"head_sha": "short"}, "head_sha"),
        ({"base_sha": "short"}, "base_sha"),
        ({"base_is_current": False}, "current main"),
        ({"pr_is_open": False}, "not open"),
        ({"pr_is_mergeable": False}, "not mergeable"),
        ({"required_checks": ()}, "no required checks"),
        (
            {"passed_checks": frozenset({"python", "postgres"})},
            "required checks not passed",
        ),
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
        reason="Candidate considered for promulgation.",
    )

    assert not review.promulgation_authorized
    assert any(expected_fragment in blocker for blocker in review.blockers)


def test_creator_reason_is_mandatory():
    with pytest.raises(ValueError):
        SovereignCreatorCycle().review(
            candidate(), decision=CreatorDecision.WAIT, reason="   "
        )
