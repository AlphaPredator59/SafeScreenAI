"""Tests that the initial migration can initialize an empty database."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_creates_all_tables(tmp_path) -> None:
    """Alembic upgrades an empty database to the current head schema."""
    database_path = tmp_path / "migration_test.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        insp = inspect(engine)
        assert set(insp.get_table_names()) >= {
            "alembic_version",
            "videos",
            "moderation_results",
            "detections",
            "evidence",
            "transcript_segments",
        }
        mod_cols = {c["name"] for c in insp.get_columns("moderation_results")}
        assert "risk_score" in mod_cols
        assert "explanation" in mod_cols
    finally:
        engine.dispose()
