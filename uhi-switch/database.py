import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use SQLite for development/testing if DATABASE_URL is not set
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./uhi_switch.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    # check_same_thread is needed only for SQLite
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
