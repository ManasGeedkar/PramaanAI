from typing import Generator
from sqlmodel import SQLModel, Session, create_engine
from app.config import DATABASE_URL

from sqlalchemy import event

# SQLite configuration: check_same_thread=False for multithreaded FastAPI requests, timeout=30.0
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30.0},
    echo=False
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


from sqlalchemy import text

def init_db():
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        for col, col_type in [("quality_json", "TEXT"), ("ela_status", "TEXT")]:
            try:
                conn.execute(text(f"ALTER TABLE document ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass

def get_session() -> Generator[Session, None, None]:

    with Session(engine) as session:
        yield session
