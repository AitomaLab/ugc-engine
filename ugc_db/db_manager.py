import os
import datetime
from sqlalchemy import create_engine, Column, String, Integer, TIMESTAMP, JSON, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import uuid

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback to local SQLite for development
    DATABASE_URL = "sqlite:///./ugc_saas.db"

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Influencer(Base):
    __tablename__ = "influencers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True)
    gender = Column(String)
    accent = Column(String)
    tone = Column(String)
    visual_description = Column(String)
    reference_image_url = Column(String)
    elevenlabs_voice_id = Column(String)
    category = Column(String)

class AppClip(Base):
    __tablename__ = "app_clips"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    category = Column(String)
    video_url = Column(String)
    duration = Column(Float)

class VideoJob(Base):
    __tablename__ = "video_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), index=True)
    influencer_id = Column(UUID(as_uuid=True), ForeignKey("influencers.id"))
    app_clip_id = Column(UUID(as_uuid=True), ForeignKey("app_clips.id"), nullable=True)
    project_name = Column(String)
    status = Column(String, default="pending")
    progress_percent = Column(Integer, default=0)
    final_video_url = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
