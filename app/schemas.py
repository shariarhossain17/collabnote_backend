from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email:EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, description="Password Minimum 6 characters")


    class Config:
        json_schema_extra={
            "example":{
                "email": "shahriar@gmail.com",
                "username": "shahriar",
                "password": "pass123"
            }
        }



class UserOut(BaseModel):
    id:int
    email:EmailStr
    username:str
    role:str


    class Config:
        from_attribute=True
        json_schema_extra={
            "example":{
                "id":1,
                "email":"shahriar@gmail.com",
                "username":"shahriar"
            }
        }


class Token(BaseModel):
    access_token:str
    token_type:str="bearer"


    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }


class TokenData(BaseModel):
    email:Optional[str]=None




# notes

class CreateNote(BaseModel):
    title:str
    content:str
    tags:list[str]

    class Config:
        json_schema_extra={
            "example":{
                "title":"Notes",
                "content":"Hello i am note",
                "tags":["personal","public"]
            }
        }


class UpdateNote(BaseModel):
    title:Optional[str]=None
    content:Optional[str]=None
    tags:Optional[list[str]]=None

    class Config:
        json_schema_extra={
            "example":{
                "title":"Updated Notes",
                "content":"Updated content",
                "tags":["personal","public","updated"]
            }
        }



class NoteOut(BaseModel):
    id:str=Field(alias="_id",description="Mongodb document id")
    user_id:str
    title:str
    content:str
    tags:list[str]
    created_at:str

    class Config:
        populate_by_name = True
        json_schema_extra={
            "example":{
                "_id":"507f1f77bcf86cd799439011",
                "user_id":"1",
                "title":"Notes",
                "content":"Hello i am note",
                "tags":["personal","public"],
                "created_at":"2026-04-22T06:40:07.241083"
            }
        }



class SearchResult(BaseModel):
    id: str
    title: str
    content: str
    tags: List[str]
    score: float
    highlight: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "title": "FastAPI Tutorial",
                "content": "FastAPI is a modern web framework...",
                "tags": ["fastapi", "python"],
                "score": 8.5,
                "highlight": {
                    "title": ["<em>FastAPI</em> Tutorial"]
                }
            }
        }




from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class EventSchema(BaseModel):
    event_type: str
    user_id: int
    resource_id: Optional[str] = None
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "note_created",
                "user_id": 42,
                "resource_id": "507f1f77bcf86cd799439011",
                "timestamp": "2025-02-25T14:30:00Z",
                "metadata": {
                    "title": "My Note",
                    "tags": ["api"]
                }
            }
        }
