import os
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    config_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(20))  # running, success, failed
    trigger: Mapped[str] = mapped_column(String(20))  # scheduled, manual
    started_at: Mapped[datetime] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    log_file: Mapped[str | None] = mapped_column(String(500), nullable=True)

    step_results: Mapped[list["StepResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class StepResult(Base):
    __tablename__ = "step_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("job_runs.id"), index=True)
    step_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))  # running, success, failed, skipped
    exit_code: Mapped[int | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    output_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["JobRun"] = relationship(back_populates="step_results")


_engine = None
_session_factory = None


def get_engine(db_path: str = "data/cronbox.db"):
    global _engine
    if _engine is None:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        _engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    return _engine


def get_session_factory(db_path: str = "data/cronbox.db") -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = get_engine(db_path)
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


async def get_session(db_path: str = "data/cronbox.db") -> AsyncSession:
    factory = get_session_factory(db_path)
    return factory()


async def init_db(db_path: str = "data/cronbox.db"):
    engine = get_engine(db_path)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
