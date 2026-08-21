"""Safe Neon PostgreSQL setup, verification, and SQLite data migration.

Commands:
    python scripts/neon_db.py check
    python scripts/neon_db.py init-schema
    python scripts/neon_db.py migrate-sqlite --sqlite aloksaar.db
    python scripts/neon_db.py verify --sqlite aloksaar.db

The running app uses DATABASE_URL (normally Neon's pooled URL). This script
uses DATABASE_URL_UNPOOLED because Neon recommends a direct connection for
schema migrations and bulk data operations.
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.extensions import db  # noqa: E402
import app.models  # noqa: E402,F401 - registers every SQLAlchemy model
from config import _normalize_database_url  # noqa: E402


def _direct_url() -> str:
    value = os.getenv("DATABASE_URL_UNPOOLED") or os.getenv("NEON_DATABASE_URL_UNPOOLED")
    value = _normalize_database_url(value)
    if not value:
        pooled = _normalize_database_url(os.getenv("DATABASE_URL"))
        if pooled:
            pooled_url = make_url(pooled)
            if pooled_url.host and pooled_url.host.endswith(".neon.tech") and "-pooler" in pooled_url.host:
                value = pooled_url.set(host=pooled_url.host.replace("-pooler", "", 1)).render_as_string(
                    hide_password=False
                )
                print("DATABASE_URL_UNPOOLED is not set; derived the matching direct Neon endpoint.")
        if not value:
            raise SystemExit("DATABASE_URL_UNPOOLED is required. Copy the direct URL from Neon Connect.")
    parsed = make_url(value)
    if not parsed.host or not parsed.host.endswith(".neon.tech"):
        raise SystemExit("DATABASE_URL_UNPOOLED must point to a Neon .neon.tech host.")
    if "-pooler" in parsed.host:
        raise SystemExit("Use Neon's direct URL for migration commands, not the -pooler URL.")
    return value


def _target_engine():
    return create_engine(_direct_url(), pool_pre_ping=True, connect_args={"connect_timeout": 15})


def _safe_target_label(engine) -> str:
    url = engine.url
    return f"{url.drivername}://{url.username or '?'}@{url.host}/{url.database or '?'}"


def check_connection() -> None:
    engine = _target_engine()
    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT current_database(), current_user, version(), "
            "current_setting('ssl')"
        )).one()
    print(f"Connected: {_safe_target_label(engine)}")
    print(f"database={row[0]} user={row[1]} ssl={row[3]}")
    print(row[2].splitlines()[0])


def init_schema() -> None:
    engine = _target_engine()
    db.metadata.create_all(engine)
    tables = inspect(engine).get_table_names()
    print(f"Schema ready on {_safe_target_label(engine)}")
    print("tables=" + ",".join(sorted(tables)))


def _source_engine(sqlite_path: Path):
    resolved = sqlite_path.resolve()
    if not resolved.is_file():
        raise SystemExit(f"SQLite source does not exist: {resolved}")
    return create_engine(f"sqlite:///{resolved.as_posix()}")


def _table_counts(engine) -> dict:
    counts = {}
    with engine.connect() as connection:
        for table in db.metadata.sorted_tables:
            counts[table.name] = connection.execute(select(func.count()).select_from(table)).scalar_one()
    return counts


def migrate_sqlite(sqlite_path: Path) -> None:
    source = _source_engine(sqlite_path)
    target = _target_engine()
    db.metadata.create_all(target)

    target_counts = _table_counts(target)
    nonempty = {name: count for name, count in target_counts.items() if count}
    if nonempty:
        raise SystemExit(
            "Refusing to overwrite a non-empty Neon database: "
            + ", ".join(f"{name}={count}" for name, count in nonempty.items())
        )

    with source.connect() as source_connection, target.begin() as target_connection:
        for table in db.metadata.sorted_tables:
            rows = [dict(row) for row in source_connection.execute(select(table)).mappings()]
            if rows:
                target_connection.execute(table.insert(), rows)
            print(f"copied {table.name}: {len(rows)}")

        for table in db.metadata.sorted_tables:
            if "id" not in table.c:
                continue
            target_connection.execute(text(
                "SELECT setval(pg_get_serial_sequence(:table_name, 'id'), "
                "COALESCE((SELECT MAX(id) FROM \"" + table.name + "\"), 1), "
                "(SELECT COUNT(*) > 0 FROM \"" + table.name + "\"))"
            ), {"table_name": table.name})

    verify(sqlite_path)


def verify(sqlite_path: Path) -> None:
    source = _source_engine(sqlite_path)
    target = _target_engine()
    source_counts = _table_counts(source)
    target_counts = _table_counts(target)
    mismatches = {
        name: (source_counts[name], target_counts.get(name))
        for name in source_counts
        if source_counts[name] != target_counts.get(name)
    }
    for name in source_counts:
        print(f"{name}: sqlite={source_counts[name]} neon={target_counts.get(name, 'missing')}")
    if mismatches:
        raise SystemExit(f"Count verification failed: {mismatches}")
    print("Verification passed: every table count matches.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage AlokSaar's Neon PostgreSQL database safely.")
    parser.add_argument("command", choices=("check", "init-schema", "migrate-sqlite", "verify"))
    parser.add_argument("--sqlite", type=Path, default=PROJECT_ROOT / "aloksaar.db")
    args = parser.parse_args()

    if args.command == "check":
        check_connection()
    elif args.command == "init-schema":
        init_schema()
    elif args.command == "migrate-sqlite":
        migrate_sqlite(args.sqlite)
    else:
        verify(args.sqlite)


if __name__ == "__main__":
    main()
