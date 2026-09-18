from __future__ import annotations

import pytest

from les_slimes.divine import (
    ArchiveItem,
    CreatorArchiveGateway,
    DivineArchiveGateway,
    DivineWorldGateway,
)
from les_slimes.divine.access import (
    CHAOS_PROPOSALS_FOLDER_ID,
    CREATOR_REVIEW_FOLDER_ID,
    DIVINE_WORKSHOPS_ROOT_ID,
    LES_SLIMES_DRIVE_MANIFEST_ID,
    LES_SLIMES_DRIVE_ROOT_ID,
    ORDER_PROPOSALS_FOLDER_ID,
)


class FakeArchiveProvider:
    def __init__(self):
        self.calls: list[tuple] = []
        self.search_results: list[ArchiveItem] = []

    def search_descendants(self, root_id, query, *, limit):
        self.calls.append(("search", root_id, query, limit))
        return list(self.search_results)

    def read_text(self, item_id):
        self.calls.append(("read", item_id))
        return f"content:{item_id}"

    def create_text(self, parent_id, *, name, content):
        self.calls.append(("create", parent_id, name, content))
        return ArchiveItem(
            id="created-1",
            name=name,
            mime_type="text/plain",
            scope_root_id=parent_id,
        )

    def update_text(self, item_id, *, content):
        self.calls.append(("update", item_id, content))


class FakeApiProvider:
    def __init__(self):
        self.calls: list[tuple] = []

    def request(self, method, path, *, body=None, query=None):
        self.calls.append((method, path, body, query))
        return {"method": method, "path": path, "body": body, "query": query}


def test_archive_search_is_read_only_and_scoped_to_les_slimes_root():
    provider = FakeArchiveProvider()
    provider.search_results = [
        ArchiveItem(
            id="report-1",
            name="daily-report.md",
            mime_type="text/markdown",
            scope_root_id=LES_SLIMES_DRIVE_ROOT_ID,
        )
    ]
    gateway = DivineArchiveGateway("chaos", provider)
    results = gateway.search("daily", limit=12)
    assert results[0].id == "report-1"
    assert provider.calls[0] == ("search", LES_SLIMES_DRIVE_ROOT_ID, "daily", 12)
    assert gateway.read("report-1") == "content:report-1"


def test_god_writes_only_inside_own_proposal_workshop():
    provider = FakeArchiveProvider()
    chaos = DivineArchiveGateway("chaos", provider)
    created = chaos.create_proposal_text(name="law-1.md", content="proposal")
    chaos.update_proposal_text(created.id, content="amended")
    assert ("create", CHAOS_PROPOSALS_FOLDER_ID, "law-1.md", "proposal") in provider.calls
    assert ("update", created.id, "amended") in provider.calls

    order_provider = FakeArchiveProvider()
    order = DivineArchiveGateway("order", order_provider)
    order.create_proposal_text(name="law-2.md", content="proposal")
    assert ("create", ORDER_PROPOSALS_FOLDER_ID, "law-2.md", "proposal") in order_provider.calls


def test_general_archive_search_does_not_grant_write_capability():
    provider = FakeArchiveProvider()
    provider.search_results = [
        ArchiveItem(
            id="other-report",
            name="report.md",
            mime_type="text/plain",
            scope_root_id=LES_SLIMES_DRIVE_ROOT_ID,
        )
    ]
    gateway = DivineArchiveGateway("chaos", provider)
    gateway.search("report")
    with pytest.raises(PermissionError, match="own proposal workshop"):
        gateway.update_proposal_text("other-report", content="tamper")


def test_proposal_search_is_scoped_to_actor_workshop_and_grants_update():
    provider = FakeArchiveProvider()
    provider.search_results = [
        ArchiveItem(
            id="own-proposal",
            name="proposal.md",
            mime_type="text/plain",
            scope_root_id=CHAOS_PROPOSALS_FOLDER_ID,
        )
    ]
    gateway = DivineArchiveGateway("chaos", provider)
    results = gateway.search_proposals("proposal")
    gateway.update_proposal_text(results[0].id, content="amended")
    assert provider.calls[0] == ("search", CHAOS_PROPOSALS_FOLDER_ID, "proposal", 50)


def test_arbitrary_drive_id_is_rejected_before_provider_access():
    provider = FakeArchiveProvider()
    gateway = DivineArchiveGateway("order", provider)
    with pytest.raises(PermissionError, match="capability"):
        gateway.read("foreign-private-file")
    assert provider.calls == []


def test_creator_reads_workshops_and_writes_only_review_folder():
    provider = FakeArchiveProvider()
    provider.search_results = [
        ArchiveItem(
            id="proposal-x",
            name="proposal-x.md",
            mime_type="text/plain",
            scope_root_id=DIVINE_WORKSHOPS_ROOT_ID,
        )
    ]
    creator = CreatorArchiveGateway(provider)
    found = creator.search_proposals("proposal-x")
    assert creator.read(found[0].id) == "content:proposal-x"
    review = creator.create_review_text(name="review.md", content="accepted")
    creator.update_review_text(review.id, content="implemented")
    assert ("create", CREATOR_REVIEW_FOLDER_ID, "review.md", "accepted") in provider.calls


def test_manifest_is_seeded_but_foreign_search_result_is_rejected():
    provider = FakeArchiveProvider()
    gateway = DivineArchiveGateway("chaos", provider)
    assert gateway.read_manifest() == f"content:{LES_SLIMES_DRIVE_MANIFEST_ID}"
    provider.search_results = [
        ArchiveItem(
            id="foreign",
            name="foreign",
            mime_type="text/plain",
            scope_root_id="another-root",
        )
    ]
    with pytest.raises(PermissionError, match="outside LES_SLIMES"):
        gateway.search("foreign")


def test_world_gateway_never_sends_actor_identity_in_payload():
    provider = FakeApiProvider()
    gateway = DivineWorldGateway("chaos", provider)
    gateway.health()
    gateway.governance()
    gateway.add_journal(entry_type="observation", content="Measured observation")
    gateway.add_proposal(proposal_type="hypothesis", title="Hypothesis")
    gateway.enqueue_command(
        command_type="emit_signal",
        payload={"signal": "S1", "x": 1.0, "y": 2.0},
        idempotency_key="chaos-cycle-1",
    )
    for _method, _path, body, _query in provider.calls:
        assert body is None or "actor_id" not in body


def test_world_gateway_rejects_admin_and_spoofed_identity_before_provider():
    provider = FakeApiProvider()
    gateway = DivineWorldGateway("order", provider)
    with pytest.raises(PermissionError):
        gateway._request("GET", "/admin/actors")
    with pytest.raises(PermissionError, match="actor_id"):
        gateway._request(
            "POST",
            "/proposals",
            body={"actor_id": "father", "proposal_type": "x", "title": "x"},
        )
    assert provider.calls == []


def test_world_gateway_has_no_generic_web_surface():
    gateway = DivineWorldGateway("chaos", FakeApiProvider())
    assert not hasattr(gateway, "web")
    assert not hasattr(gateway, "browse")
    assert not hasattr(gateway, "request_url")
