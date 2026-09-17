import pytest

from les_slimes.divine.access import (
    AUTHORIZED_REPOSITORY,
    LES_SLIMES_DRIVE_MANIFEST_ID,
    LES_SLIMES_DRIVE_ROOT_ID,
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


def test_each_god_can_write_only_its_own_divine_branch():
    DivineAccessPolicy("order").assert_git_write_branch("god/order/stability-law")
    DivineAccessPolicy("chaos").assert_git_write_branch("god/chaos/variation-law")

    forbidden = (
        ("order", "main"),
        ("chaos", "main"),
        ("order", "god/chaos/foreign-law"),
        ("chaos", "god/order/foreign-law"),
        ("order", "father/override"),
        ("chaos", "feature/unscoped"),
    )
    for actor_id, branch in forbidden:
        with pytest.raises(PermissionError):
            DivineAccessPolicy(actor_id).assert_git_write_branch(branch)


def test_repo_paths_cannot_escape_workspace():
    policy = DivineAccessPolicy("chaos")
    assert policy.assert_repo_path("src/les_slimes/world/engine.py") == (
        "src/les_slimes/world/engine.py"
    )

    for path in ("", "/etc/passwd", "../secret", "src/../../secret", "C:\\secret"):
        with pytest.raises(PermissionError):
            policy.assert_repo_path(path)


def test_drive_access_requires_les_slimes_ancestry_and_manifest():
    policy = DivineAccessPolicy("order")
    policy.assert_drive_manifest(LES_SLIMES_DRIVE_MANIFEST_ID)
    policy.assert_drive_lineage((LES_SLIMES_DRIVE_ROOT_ID, "child", "grandchild"))

    with pytest.raises(PermissionError):
        policy.assert_drive_manifest("foreign-manifest")
    with pytest.raises(PermissionError):
        policy.assert_drive_lineage(("My Drive", "foreign-folder"))


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
