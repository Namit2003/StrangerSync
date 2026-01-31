from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL configuration (matches microservices)
DB_HOST = os.getenv("DATABASE_HOST", "localhost")
DB_PORT = os.getenv("DATABASE_PORT", "5432")
DB_NAME = os.getenv("DATABASE_NAME", "strangersync")
DB_USER = os.getenv("DATABASE_USER", "postgres")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "postgres")

# PostgreSQL connection string
DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Table 1: Track every time someone visits
class SessionLog(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_token = Column(String, index=True)
    ip_address = Column(String) 
    connected_at = Column(DateTime, default=datetime.utcnow)
    disconnected_at = Column(DateTime, nullable=True)

# Table 2: Track every match made
class MatchLog(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String, index=True)
    user_a = Column(String)
    user_b = Column(String)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

# Table 3: Admin query history
class AdminQuery(Base):
    __tablename__ = "admin_queries"
    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text)
    executed_at = Column(DateTime, default=datetime.utcnow)
    result_count = Column(Integer, nullable=True)

# Create the tables in the database
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")