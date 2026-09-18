from __future__ import annotations

import hashlib
import json
import inspect

import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.divine import (
    ArchiveItem,
    DivineLawProposalPipeline,
    DivineSessionBindingService,
    LawProposalDraft,
)
from les_slimes.divine.access import (
    CHAOS_PROPOSALS_FOLDER_ID,
    ORDER_PROPOSALS_FOLDER_ID,
)
from les_slimes.world.engine import World


META_CHAOS = {
    "openai/session": "chaos-proposal-session",
    "openai/subject": "one-human",
}
META_ORDER = {
    "openai/session": "order-proposal-session",
    "openai/subject": "one-human",
}


def build_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=4401,
                width=20.0,
                height=15.0,
                initial_slimes=4,
                initial_food=5,
                max_food=20,
                food_spawn_probability=0.0,
            )
        )
    )
    sessions = DivineSessionBindingService(repo)
    sessions.bind(
        session_id=META_CHAOS["openai/session"],
        subject_id=META_CHAOS["openai/subject"],
        actor_id="chaos",
    )
    sessions.bind(
        session_id=META_ORDER["openai/session"],
        subject_id=META_ORDER["openai/subject"],
        actor_id="order",
    )
    return repo


class FakeGitProvider:
    def __init__(self):
        self.calls = []

    def read_file(self, repository_full_name, path, ref):
        self.calls.append(("read", repository_full_name, path, ref))
        return "content"

    def search_code(self, repository_full_name, query):
        self.calls.append(("search", repository_full_name, query))
        return []

    def get_ref_sha(self, repository_full_name, ref):
        self.calls.append(("sha", repository_full_name, ref))
        return "a" * 40


class FakeArchiveProvider:
    def __init__(self):
        self.calls = []
        self.contents = {}
        self.parents = {}
        self.counter = 0

    def search_descendants(self, root_id, query, *, limit):
        self.calls.append(("search", root_id, query, limit))
        return []

    def read_text(self, item_id):
        self.calls.append(("read", item_id))
        return self.contents[item_id]

    def create_text(self, parent_id, *, name, content):
        self.counter += 1
        item_id = f"item-{self.counter}"
        self.calls.append(("create", parent_id, name, content))
        self.contents[item_id] = content
        self.parents[item_id] = parent_id
        return ArchiveItem(
            id=item_id,
            name=name,
            mime_type="text/plain",
            scope_root_id=parent_id,
        )

    def update_text(self, item_id, *, content):
        self.calls.append(("update", item_id, content))
        self.contents[item_id] = content


def draft(**overrides):
    data = {
        "title": "Diversifier les stratégies",
        "observation": "Les comportements convergent.",
        "hypothesis": "Une variation bornée peut préserver plusieurs stratégies.",
        "expected_benefit": "Maintenir plusieurs trajectoires viables.",
        "risk": "Ajouter du bruit inutile.",
        "affected_files": (
            "src/les_slimes/world/engine.py",
            "tests/test_engine.py",
        ),
        "patch_text": "--- a/engine.py\n+++ b/engine.py\n@@ example\n",
        "tests_text": "--- a/tests.py\n+++ b/tests.py\n@@ test\n",
        "results_text": '{"control": 1, "treatment": 2}',
        "evidence": ("EXP-101",),
        "experiment_refs": ("EXP-101",),
    }
    data.update(overrides)
    return LawProposalDraft(**data)


def pipeline(tmp_path):
    repo = build_repo(tmp_path)
    git = FakeGitProvider()
    archive = FakeArchiveProvider()
    return repo, git, archive, DivineLawProposalPipeline(
        repo,
        git_provider=git,
        archive_provider=archive,
    )


@pytest.mark.parametrize(
    ("meta", "actor_id", "expected_parent"),
    [
        (META_CHAOS, "chaos", CHAOS_PROPOSALS_FOLDER_ID),
        (META_ORDER, "order", ORDER_PROPOSALS_FOLDER_ID),
    ],
)
def test_pipeline_derives_actor_and_workshop_from_bound_session(
    tmp_path, meta, actor_id, expected_parent
):
    repo, git, archive, service = pipeline(tmp_path)
    result = service.submit(meta, draft=draft())

    assert result.actor_id == actor_id
    assert result.source_main_sha == "a" * 40
    assert all(archive.parents[item_id] == expected_parent for item_id in result.artifact_ids)
    assert git.calls == [
        ("sha", "Jean-Philippe56520/Les-Slimes", "main")
    ]

    with repo._connect() as conn:
        proposal = conn.execute(
            "SELECT * FROM divine_proposals WHERE id = ?", (result.proposal_id,)
        ).fetchone()
        provenance = conn.execute(
            "SELECT * FROM divine_proposal_provenance WHERE proposal_id = ?",
            (result.proposal_id,),
        ).fetchone()

    assert proposal["actor_id"] == actor_id
    payload = json.loads(proposal["payload_json"])
    assert payload["drive_artifact_id"] == result.manifest_item_id
    assert payload["patch_digest"] == result.patch_digest
    assert "session_hash" not in payload
    assert "subject_hash" not in payload
    assert provenance["session_hash"] != meta["openai/session"]
    assert provenance["subject_hash"] != meta["openai/subject"]


def test_manifest_binds_source_files_artifact_ids_and_content_digests(tmp_path):
    _repo, _git, archive, service = pipeline(tmp_path)
    source = draft()
    result = service.submit(META_CHAOS, draft=source)

    manifest_text = archive.contents[result.manifest_item_id]
    manifest = json.loads(manifest_text)

    assert hashlib.sha256(manifest_text.encode("utf-8")).hexdigest() == result.manifest_digest
    assert manifest["actor_id"] == "chaos"
    assert manifest["source_main_sha"] == "a" * 40
    assert manifest["affected_files"] == list(source.affected_files)
    patch_id = manifest["artifacts"]["patch"]["id"]
    assert hashlib.sha256(archive.contents[patch_id].encode("utf-8")).hexdigest() == result.patch_digest
    assert manifest["artifacts"]["patch"]["sha256"] == result.patch_digest
    assert manifest["evidence"] == ["EXP-101"]
    assert manifest["experiment_refs"] == ["EXP-101"]


def test_protected_target_is_rejected_before_git_or_drive_access(tmp_path):
    _repo, git, archive, service = pipeline(tmp_path)

    with pytest.raises(PermissionError):
        service.submit(
            META_CHAOS,
            draft=draft(affected_files=("src/les_slimes/divine/access.py",)),
        )

    assert git.calls == []
    assert archive.calls == []


def test_unbound_session_is_rejected_before_external_providers(tmp_path):
    _repo, git, archive, service = pipeline(tmp_path)

    with pytest.raises(PermissionError, match="UNBOUND"):
        service.submit(
            {
                "openai/session": "unknown",
                "openai/subject": "one-human",
            },
            draft=draft(),
        )

    assert git.calls == []
    assert archive.calls == []


def test_invalid_main_sha_stops_before_drive_writes(tmp_path):
    _repo, git, archive, service = pipeline(tmp_path)
    git.get_ref_sha = lambda repository_full_name, ref: "not-a-sha"

    with pytest.raises(ValueError, match="invalid main SHA"):
        service.submit(META_ORDER, draft=draft())

    assert archive.calls == []


def test_submission_api_has_no_actor_id_parameter():
    assert "actor_id" not in inspect.signature(DivineLawProposalPipeline.submit).parameters
