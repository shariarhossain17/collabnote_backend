
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime,UniqueConstraint,Boolean
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    pass_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow())
    is_active = Column(Boolean, default=True)


    __table_args__= (
        UniqueConstraint("email",name="uq_user_email"),
        UniqueConstraint("username",name="uq_user_name"),
    )

    def __repr__(self):
        return f"<USer(id={self.id},email={self.email}),username={self.username})>"