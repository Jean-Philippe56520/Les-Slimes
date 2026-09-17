from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "statement",
    [
        "import les_slimes.runtime",
        "import les_slimes.governance.models",
        "from les_slimes.runtime import CanonicalWorldWorker",
        "from les_slimes.governance.service import GovernanceAdminService",
        "import les_slimes.runtime; from les_slimes.governance.service import GovernanceAdminService",
        "from les_slimes.governance.service import GovernanceAdminService; import les_slimes.runtime",
    ],
)
def test_governance_runtime_imports_are_order_independent(statement):
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
