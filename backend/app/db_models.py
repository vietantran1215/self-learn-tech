"""SQLAlchemy mappings for the existing SQLite schema (no data rewrite required)."""
from sqlalchemy import Float, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class NotebookRecord(Base):
    __tablename__ = 'notebooks'
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(Text)


class DocumentRecord(Base):
    __tablename__ = 'documents'
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    notebook: Mapped[str] = mapped_column(ForeignKey('notebooks.id'))
    name: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChunkRecord(Base):
    __tablename__ = 'chunks'
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    document: Mapped[str] = mapped_column(ForeignKey('documents.id'))
    page: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    modality: Mapped[str] = mapped_column(Text)
    vector: Mapped[list[float]] = mapped_column(JSON)


class OutboxRecord(Base):
    __tablename__ = 'outbox'
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    document: Mapped[str] = mapped_column(ForeignKey('documents.id'))
    sent: Mapped[int] = mapped_column(Integer, default=0, server_default='0')


class IngestionEvent(Base):
    __tablename__ = 'events'
    __table_args__ = {'sqlite_autoincrement': True}
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notebook: Mapped[str] = mapped_column(ForeignKey('notebooks.id'))
    kind: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON)
    created: Mapped[float] = mapped_column(Float)


class ArtifactRecord(Base):
    __tablename__ = 'artifacts'
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    notebook: Mapped[str] = mapped_column(ForeignKey('notebooks.id'))
    path: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
