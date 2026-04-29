from __future__ import annotations
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID

load_dotenv()

Base = declarative_base()


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(String, nullable=True)
    session_id = Column(String, nullable=False)
    asked_at   = Column(DateTime, default=datetime.utcnow)
    question   = Column(Text, nullable=False)
    response   = Column(Text, nullable=False)

# Lazy globals — not created at import time
engine = None
SessionLocal = None


def _init_db():
    global engine, SessionLocal
    if engine is not None:
        return

    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("❌ DATABASE_URL is not set")

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)


def get_db():
    _init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()