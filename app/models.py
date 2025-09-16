
from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    role: str = Field(default="client")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id")
    rows_in: int
    rows_out: int
    duplicates_removed: int
    invalid_emails: int
    invalid_phones: int
    columns_csv: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
