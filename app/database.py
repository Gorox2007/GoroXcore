from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite database URL; relative path keeps DB in project root
DATABASE_URL = "sqlite:///./app.db"

# check_same_thread is required for SQLite with FastAPI in a single process
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
