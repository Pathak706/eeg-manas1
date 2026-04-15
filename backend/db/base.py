from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import settings


# SQLite needs check_same_thread; PostgreSQL doesn't
_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    # Import models so Base knows about them before creating tables
    from models import patient, study, analysis  # noqa: F401

    # Check if we need to migrate (old schema had seizure_probability, new has depression_severity_score)
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if inspector.has_table("analysis_results"):
        columns = {c["name"] for c in inspector.get_columns("analysis_results")}
        if "overall_seizure_probability" in columns and "depression_severity_score" not in columns:
            # Old schema detected — drop analysis tables and recreate
            analysis.EpochResult.__table__.drop(engine, checkfirst=True)
            analysis.AnalysisResult.__table__.drop(engine, checkfirst=True)

    Base.metadata.create_all(bind=engine)
