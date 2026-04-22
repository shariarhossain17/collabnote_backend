import os
from datetime import datetime, timedelta
from typing import Dict, Optional

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import (HTTPAuthorizationCredentials, HTTPBearer,
                              OAuth2PasswordRequestForm)
from sqlalchemy.orm import Session

from .auth import (ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token,
                   decode_access_token, hash_password, verify_password)
from .database import SessionLocal
from .elasticsearch import (ELASTICSEARCH_INDEX,
                            close_elasticsearch_connection,
                            connect_to_elasticsearch, get_elasticsearch)
from .models import User
from .mongodb import close_mongodb_connection, connect_to_mongodb, get_mongodb
from .schemas import (CreateNote, NoteOut, Token, TokenData, UpdateNote,
                      UserCreate, UserOut)

load_dotenv()

app=FastAPI(
    title=os.getenv("APP_NAME","Collabnote"),
    description="Collabnote backend",
    version="1.0.0"
)


security=HTTPBearer()

#mongodb

@app.on_event("startup")
async def startup_event():
    await connect_to_mongodb()
    await connect_to_elasticsearch()


@app.on_event("shutdown")
async def shutdown_event():
    await close_mongodb_connection()
    await close_elasticsearch_connection()

#postgres db

def get_db():
    db=SessionLocal()

    try:
        yield db
    
    finally :
        db.close()



#application start
def error_response(
    status_code: int,
    message: str,
    headers: Optional[Dict[str, str]] = None
):
    raise HTTPException(
        status_code=status_code,
        detail=message,
        headers=headers
    )
@app.get("/ping")
def ping():
    return {"status":"ok","message":"pong"}

def get_current_user(
        credentials:HTTPAuthorizationCredentials=Depends(security),
        db:Session=Depends(get_db)
)->User:
    token=credentials.credentials

    email=decode_access_token(token)

    if email is None:
        error_response(
            status.HTTP_401_UNAUTHORIZED,
            "Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},

        )
    

    user= db.query(User).filter(User.email==email).first()

    if user is None:
        error_response(
            status.HTTP_401_UNAUTHORIZED,
            "Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},

        )
    return user


@app.post("/auth/signup",response_model=UserOut,status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()

    if existing_user:
        if existing_user.email == user_data.email:
            error_response(status.HTTP_400_BAD_REQUEST, "Email already exists")
        if existing_user.username == user_data.username:
            error_response(status.HTTP_400_BAD_REQUEST, "Username already exists")

    hashed_password = hash_password(user_data.password)

    new_user = User(
        email=user_data.email,
        username=user_data.username,
        pass_hash=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@app.post("/auth/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Find user by username
    user = db.query(User).filter(User.username == form_data.username).first()

    # Check if user exists and password is correct
    if not user or not verify_password(form_data.password, user.pass_hash):
        error_response(status.HTTP_401_UNAUTHORIZED, "incorrect username or password", headers={"WWW-Authenticate": "Bearer"},)

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expire_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}



@app.get("/profile",response_model=UserOut)
def profile(current_user:User=Depends(get_current_user)):
    return current_user


#note route


@app.post("/notes",response_model=NoteOut,status_code=status.HTTP_201_CREATED)
async def create_note(
    note_data:CreateNote,
    current_user:User=Depends(get_current_user)
):
    mongodb=get_mongodb()
    es=get_elasticsearch()

    new_note={
        "user_id":current_user.id,
        "title":note_data.title,
        "content":note_data.content,
        "tags":note_data.tags,
        "created_at":datetime.utcnow()

    }


    result = await mongodb.notes.insert_one(new_note)

    if result.inserted_id:
         
         note_id = str(result.inserted_id)

         await es.index(
             index=ELASTICSEARCH_INDEX,
             id=note_id,
              document={
            "title": note_data.title,
            "content": note_data.content,
            "tags": note_data.tags,
            "created_at": new_note["created_at"].isoformat()
        }
         )
         return {
            "_id": str(result.inserted_id),
            "user_id": str(current_user.id),
            "title": new_note["title"],
            "content": new_note["content"],
            "tags": new_note["tags"],
            "created_at": new_note["created_at"].isoformat()
        }
    else:
        return error_response(status.HTTP_400_BAD_REQUEST, "note created failed")
        

@app.get("/notes", response_model=list[NoteOut])
async def get_notes(
    current_user: User = Depends(get_current_user),
    limit:int=10
):
    mongodb = get_mongodb()

    cursor = mongodb.notes.find({
        "user_id": current_user.id
    }).sort("created_at", -1)

    notes = await cursor.to_list(limit)  

    for note in notes:
        note["_id"] = str(note["_id"])
        note["user_id"] = str(note["user_id"])
        note["created_at"] = note["created_at"].isoformat()

    return notes


@app.get("/notes/{note_id}", response_model=NoteOut)
async def get_note(
    note_id: str,
    current_user: User = Depends(get_current_user)
):
    mongodb = get_mongodb()
    
    try:
        object_id = ObjectId(note_id)
    except:
        error_response(status.HTTP_400_BAD_REQUEST, "Invalid note ID format")
    
    note = await mongodb.notes.find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not note:
        error_response(status.HTTP_404_NOT_FOUND, "Note not found or you don't have access to it")
    
    note["_id"] = str(note["_id"])
    note["user_id"] = str(note["user_id"])
    note["created_at"] = note["created_at"].isoformat()
    
    return note


@app.put("/notes/{note_id}", response_model=NoteOut)
async def update_note(
    note_id: str,
    note_data: UpdateNote,
    current_user: User = Depends(get_current_user)
):
    mongodb = get_mongodb()
    
    try:
        object_id = ObjectId(note_id)
    except:
        error_response(status.HTTP_400_BAD_REQUEST, "Invalid note ID format")
    
    existing_note = await mongodb.notes.find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not existing_note:
        error_response(status.HTTP_404_NOT_FOUND, "Note not found or you don't have access to it")
    
   
    update_data = {}
    if note_data.title is not None:
        update_data["title"] = note_data.title
    if note_data.content is not None:
        update_data["content"] = note_data.content
    if note_data.tags is not None:
        update_data["tags"] = note_data.tags
    
    if not update_data:
        error_response(status.HTTP_400_BAD_REQUEST, "No fields to update")
    
    # Update the note
    result = await mongodb.notes.update_one(
        {"_id": object_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        error_response(status.HTTP_400_BAD_REQUEST, "Failed to update note")
    
    updated_note = await mongodb.notes.find_one({"_id": object_id})
    
    updated_note["_id"] = str(updated_note["_id"])
    updated_note["user_id"] = str(updated_note["user_id"])
    updated_note["created_at"] = updated_note["created_at"].isoformat()
    
    return updated_note


@app.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    current_user: User = Depends(get_current_user)
):

    mongodb = get_mongodb()
    
    try:
        object_id = ObjectId(note_id)
    except:
        error_response(status.HTTP_400_BAD_REQUEST, "Invalid note ID format")
    
    existing_note = await mongodb.notes.find_one({
        "_id": object_id,
        "user_id": current_user.id
    })
    
    if not existing_note:
        error_response(status.HTTP_404_NOT_FOUND, "Note not found or you don't have access to it")
    
    result = await mongodb.notes.delete_one({
        "_id": object_id
    })
    
    if result.deleted_count == 0:
        error_response(status.HTTP_400_BAD_REQUEST, "Failed to delete note")


@app.get("/users/{user_id}/notes", response_model=list[NoteOut])
async def get_user_notes(
    user_id: int,
    current_user: User = Depends(get_current_user),
    limit: int = 10
):
    mongodb = get_mongodb()
    
    cursor = mongodb.notes.find({
        "user_id": user_id
    }).sort("created_at", -1)

    notes = await cursor.to_list(limit)  

    for note in notes:
        note["_id"] = str(note["_id"])
        note["user_id"] = str(note["user_id"])
        note["created_at"] = note["created_at"].isoformat()

    return notes
    return notes
