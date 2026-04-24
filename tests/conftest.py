import os
import tempfile
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch, tmp_path):
    db = tmp_path / "test.db"
    monkeypatch.setenv("IPAY_DB_PATH", str(db))
    # Force reimport so settings + engine pick up the new path
    import importlib, sys
    for mod in list(sys.modules):
        if mod.startswith("infinitepay"):
            sys.modules.pop(mod)
    yield db
