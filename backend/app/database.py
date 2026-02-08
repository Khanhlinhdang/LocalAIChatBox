from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from app.models import Base
import os
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://raguser:ragpassword@localhost:5432/ragdb"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _safe_add_column(conn, table: str, column: str, col_type: str, default=None):
    """Add a column to a table if it doesn't exist"""
    try:
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            f"WHERE table_name = '{table}' AND column_name = '{column}'"
        ))
        if result.fetchone() is None:
            default_clause = f" DEFAULT {default}" if default is not None else ""
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"))
            logger.info(f"Added column {table}.{column}")
    except Exception as e:
        logger.warning(f"Could not add column {table}.{column}: {e}")


def run_migrations():
    """Run schema migrations for Phase 4 enterprise features"""
    with engine.connect() as conn:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        # Create new tables first (create_all is safe for new tables)
        Base.metadata.create_all(bind=engine)

        # Add new columns to existing tables
        if "users" in existing_tables:
            _safe_add_column(conn, "users", "tenant_id", "INTEGER")
            _safe_add_column(conn, "users", "ldap_dn", "VARCHAR(500)")
            _safe_add_column(conn, "users", "auth_provider", "VARCHAR(20)", "'local'")

        if "documents" in existing_tables:
            _safe_add_column(conn, "documents", "tenant_id", "INTEGER")
            _safe_add_column(conn, "documents", "is_encrypted", "BOOLEAN", "false")

        if "folders" in existing_tables:
            _safe_add_column(conn, "folders", "tenant_id", "INTEGER")

        # Phase 5: Add research metadata columns
        if "research_tasks" in existing_tables:
            _safe_add_column(conn, "research_tasks", "result_metadata", "TEXT")

        conn.commit()
        logger.info("Database migration completed (Phase 5)")
        print("Database migration completed (Phase 5)")


def init_db():
    run_migrations()
    print("Database tables created/updated")


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
