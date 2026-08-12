"""Sanity checks on the Alembic migration chain - not a full migration run
(the rest of the suite exercises the schema via Base.metadata.create_all
against a throwaway SQLite file, per tests/conftest.py), just confirms the
migration files themselves form one linear, unambiguous chain ending in a
single head, which is what `alembic upgrade head` in a real deployment
depends on."""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _script_directory() -> ScriptDirectory:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_migration_chain_has_a_single_head():
    script = _script_directory()
    heads = script.get_heads()
    assert len(heads) == 1


def test_budget_migration_follows_initial_schema():
    script = _script_directory()
    revisions = {rev.revision: rev for rev in script.walk_revisions()}
    assert "1c20bbe6ba9c" in revisions
    assert "8f3a1d9c2b40" in revisions
    assert revisions["8f3a1d9c2b40"].down_revision == "1c20bbe6ba9c"
