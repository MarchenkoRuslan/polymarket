from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL, DATABASE_SSLMODE

_engine_kwargs: dict = {"pool_pre_ping": True}

if DATABASE_URL and DATABASE_URL.startswith("postgresql") and DATABASE_SSLMODE != "disable":
    _engine_kwargs["connect_args"] = {"sslmode": DATABASE_SSLMODE}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
