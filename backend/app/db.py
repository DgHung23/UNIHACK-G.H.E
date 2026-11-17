from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

_is_sqlite = config.DATABASE_URL.startswith("sqlite")
engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    future=True,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _rec):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


APPEND_ONLY_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger_events
       BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;""",
    """CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger_events
       BEGIN SELECT RAISE(ABORT, 'ledger_events is append-only'); END;""",
]


def create_all() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
    if _is_sqlite:
        with engine.begin() as conn:
            for t in APPEND_ONLY_TRIGGERS:
                conn.execute(text(t))


def drop_all() -> None:
    from . import models  # noqa: F401

    Base.metadata.drop_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
