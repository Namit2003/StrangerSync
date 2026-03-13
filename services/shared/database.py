"""
Shared database models and connection logic for all microservices
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Support DATABASE_URL directly (Railway, Render, etc.) or individual vars for local dev
_raw_url = os.getenv("DATABASE_URL")
if _raw_url:
    DATABASE_URL = _raw_url.replace("postgres://", "postgresql+psycopg://", 1).replace("postgresql://", "postgresql+psycopg://", 1)
else:
    DB_HOST = os.getenv("DATABASE_HOST", "localhost")
    DB_PORT = os.getenv("DATABASE_PORT", "5432")
    DB_NAME = os.getenv("DATABASE_NAME", "strangersync")
    DB_USER = os.getenv("DATABASE_USER", "postgres")
    DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "postgres")
    DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Database Models
class SessionLog(Base):
    """User session logs"""
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_token = Column(String, index=True)
    ip_address = Column(String)
    connected_at = Column(DateTime, default=datetime.utcnow)
    disconnected_at = Column(DateTime, nullable=True)

class MatchLog(Base):
    """Match logs between users"""
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String, unique=True, index=True)
    user_a = Column(String)
    user_b = Column(String)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

class AdminQuery(Base):
    """Admin query history"""
    __tablename__ = "admin_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text)
    executed_at = Column(DateTime, default=datetime.utcnow)
    result_count = Column(Integer, nullable=True)

# Helper functions
def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")

def get_db_session():
    """Get a database session"""
    return SessionLocal()
