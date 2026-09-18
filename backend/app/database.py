from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Database connection URL matching your docker-compose credentials
SQLALCHEMY_DATABASE_URL = "postgresql+psycopg://ecobuild_user:ecobuild_password@localhost:5432/ecobuild_db"

# Create the SQLAlchemy engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a SessionLocal class for database transactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our ORM database models
Base = declarative_base()

# Dependency to get database sessions in our FastAPI endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()