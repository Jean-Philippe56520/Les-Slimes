import pytest

from les_slimes.divine.access import (
    AUTHORIZED_REPOSITORY,
    CHAOS_PROPOSALS_FOLDER_ID,
    LES_SLIMES_DRIVE_MANIFEST_ID,
    LES_SLIMES_DRIVE_ROOT_ID,
    ORDER_PROPOSALS_FOLDER_ID,
    DivineAccessPolicy,
    DivineSurface,
)


def test_policy_is_only_for_order_and_chaos():
    for actor_id in ("order", "chaos"):
        assert DivineAccessPolicy(actor_id).actor_id == actor_id
    with pytest.raises(ValueError):
        DivineAccessPolicy("father")


def test_repository_is_hard_pinned():
    policy = DivineAccessPolicy("chaos")
    policy.assert_repository(AUTHORIZED_REPOSITORY)
    for other_repo in (
        "Jean-Philippe56520/Other",
        "openai/openai",
        "Jean-Philippe56520/Les-Slimes-copy",
    ):
        with pytest.raises(PermissionError):
            policy.assert_repository(other_repo)


def test_web_and_unknown_surfaces_are_not_available():
    policy = DivineAccessPolicy("order")
    for surface in DivineSurface:
        assert policy.assert_surface(surface) == surface
    for forbidden in ("web", "browser", "other_api", "email"):
        with pytest.raises(PermissionError):
            policy.assert_surface(forbidden)


def test_git_policy_is_read_only_and_law_targets_are_only_proposal_scope():
    policy = DivineAccessPolicy("chaos")
    assert policy.assert_git_read_only() is None
    assert policy.assert_law_target_path("src/les_slimes/world/engine.py") == (
        "src/les_slimes/world/engine.py"
    )
    with pytest.raises(PermissionError):
        policy.assert_law_target_path("src/les_slimes/divine/access.py")
    with pytest.raises(PermissionError):
        policy.assert_law_target_path("README.md")


def test_repo_paths_cannot_escape_workspace():
    policy = DivineAccessPolicy("chaos")
    assert policy.assert_repo_path("src/les_slimes/world/engine.py") == (
        "src/les_slimes/world/engine.py"
    )
    for path in ("", "/etc/passwd", "../secret", "src/../../secret", "C:\\secret"):
        with pytest.raises(PermissionError):
            policy.assert_repo_path(path)


def test_drive_access_and_actor_owned_workshop():
    order = DivineAccessPolicy("order")
    chaos = DivineAccessPolicy("chaos")
    order.assert_drive_manifest(LES_SLIMES_DRIVE_MANIFEST_ID)
    order.assert_drive_lineage((LES_SLIMES_DRIVE_ROOT_ID, "child"))
    assert order.proposal_workspace_id == ORDER_PROPOSALS_FOLDER_ID
    assert chaos.proposal_workspace_id == CHAOS_PROPOSALS_FOLDER_ID
    order.assert_drive_write_parent(ORDER_PROPOSALS_FOLDER_ID)
    chaos.assert_drive_write_parent(CHAOS_PROPOSALS_FOLDER_ID)
    with pytest.raises(PermissionError):
        order.assert_drive_write_parent(CHAOS_PROPOSALS_FOLDER_ID)
    with pytest.raises(PermissionError):
        chaos.assert_drive_write_parent(ORDER_PROPOSALS_FOLDER_ID)


def test_api_allowlist_excludes_creator_administration():
    policy = DivineAccessPolicy("chaos")
    for path in ("/health", "/world", "/world/slimes", "/governance", "/journals"):
        policy.assert_api_request("GET", path)
    for path in ("/commands", "/journals", "/proposals"):
        policy.assert_api_request("POST", path)
    for method, path in (
        ("GET", "/admin/actors"),
        ("POST", "/admin/actors/order/budget"),
        ("DELETE", "/world"),
        ("POST", "/world"),
        ("GET", "/internal/secrets"),
    ):
        with pytest.raises(PermissionError):
            policy.assert_api_request(method, path)
