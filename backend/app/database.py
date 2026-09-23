import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Fallback to local Docker if no cloud environment variable is provided
DEFAULT_LOCAL_URL = "postgresql+psycopg://ecobuild_user:ecobuild_password@localhost:5432/ecobuild_db"
raw_db_url = os.getenv("SQLALCHEMY_DATABASE_URL", DEFAULT_LOCAL_URL)

# Ensure psycopg (v3) driver is used even if cloud provider supplies postgresql://
if raw_db_url.startswith("postgresql://"):
    SQLALCHEMY_DATABASE_URL = raw_db_url.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    SQLALCHEMY_DATABASE_URL = raw_db_url

# Create the SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()