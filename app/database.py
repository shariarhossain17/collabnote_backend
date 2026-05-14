import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker,DeclarativeBase


load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
if os.getenv("TESTING") and not DATABASE_URL:
    DATABASE_URL = "sqlite:///:memory:"

class Base(DeclarativeBase):
    pass


engine=create_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

SessionLocal=sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True
)
