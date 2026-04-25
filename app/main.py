import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.security import (HTTPAuthorizationCredentials, HTTPBearer,
                              OAuth2PasswordRequestForm)
from sqlalchemy.orm import Session

from .auth import (ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token,
                   decode_access_token, hash_password, verify_password)
from .database import SessionLocal
from .elasticsearch import (ELASTICSEARCH_INDEX,
                            close_elasticsearch_connection,
                            connect_to_elasticsearch, get_elasticsearch)
from .kafka_producer import (get_topic_name, publish_log, start_kafka_producer,
                             stop_kafka_producer)
from .models import User
from .mongodb import close_mongodb_connection, connect_to_mongodb, get_mongodb
from .redis_client import (cache_delete, cache_delete_pattern, cache_get,
                           cache_set, close_redis_connection, connect_to_redis)
from .schemas import (CreateNote, EventSchema, NoteOut, SearchResult, Token,
                      TokenData, UpdateNote, UserCreate, UserOut)

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
    await connect_to_redis()
    await start_kafka_producer()
    print("Application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    await close_mongodb_connection()
    await close_elasticsearch_connection()
    await close_redis_connection()
    await stop_kafka_producer()
    print("Application shutdown complete")


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
async def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    
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

    #publish to kafka
    try:
        await publish_log({
            "event_type": "user_signup",
            "user_id": new_user.id,
            "resource_id": None,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "email": new_user.email,
                "username": new_user.username
            }
        })
    except Exception as e:
        print("Kafka publish failed:", e)


    return new_user


@app.post("/auth/login", response_model=Token)
async def login(
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


     # Kafka event publish
    try:
        await publish_log({
            "event_type": "user_login",
            "user_id": user.id,
            "resource_id": None,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "username": user.username
            }
        })
    except Exception as e:
        print("Kafka publish failed:", e)
    

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

        # Kafka event publish
         await publish_log({
             "event_type": "note_created",
                "user_id": current_user.id,
                "resource_id": note_id,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "title": note_data.title,
                    "tags": note_data.tags
                }
         })

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
    current_user: User = Depends(get_current_user),
    x_cache_control: Optional[str] = Header(None)
):
    
    start_time= time.time()


    bypass_cache=x_cache_control=="no-cache"


    if not bypass_cache:
        cached_note= await cache_get(f"note:{note_id}")

        if cached_note:
            elapsed =(time.time()-start_time)*1000
            print(f"Cache HIT for note:{note_id} ({elapsed:.2f}ms)")
            return NoteOut(**cached_note)




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

    cache_note = note.copy()
    await cache_set(f"note:{note_id}", cache_note)

    elapsed = (time.time() - start_time) * 1000
    print(f"Cache MISS for note:{note_id} ({elapsed:.2f}ms)")
    
    return note


@app.put("/notes/{note_id}", response_model=NoteOut)
async def update_note(
    note_id: str,
    note_data: UpdateNote,
    current_user: User = Depends(get_current_user)
):
    mongodb = get_mongodb()
    es=get_elasticsearch()
    
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

    print(result.modified_count,"from update")
    
    if result.modified_count == 0:
        error_response(status.HTTP_400_BAD_REQUEST, "Failed to update note")
    
    await cache_delete(f"note:{note_id}")
    
    updated_note = await mongodb.notes.find_one({"_id": object_id})
    
    updated_note["_id"] = str(updated_note["_id"])
    updated_note["user_id"] = str(updated_note["user_id"])
    updated_note["created_at"] = updated_note["created_at"].isoformat()


    await es.index(
        index=ELASTICSEARCH_INDEX,
        id=str(updated_note["_id"]),
        document={
            "title": updated_note["title"],
            "content": updated_note["content"],
            "tags": updated_note["tags"],
            "created_at": updated_note["created_at"]
        }
    )



    # Kafka event publish
    try:
        await publish_log({
            "event_type": "note_updated",
            "user_id": current_user.id,
            "resource_id": note_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "updated_fields": list(update_data.keys())
            }
        })
    except Exception as e:
        print("Kafka publish failed:", e)

    
    return updated_note


@app.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    current_user: User = Depends(get_current_user)
):

    mongodb = get_mongodb()
    es=get_elasticsearch()
    
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


    try:
        await es.delete(index=ELASTICSEARCH_INDEX,id=note_id)
        await cache_delete(f"note:{note_id}")

        # Kafka event publish
        try:
            await publish_log({
                "event_type": "note_deleted",
                "user_id": current_user.id,
                "resource_id": note_id,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "title": existing_note.get("title"),
                    "tags": existing_note.get("tags")
                }
            })
        except Exception as e:
            print("Kafka publish failed:", e)
    except Exception as e:
        print(f"Failed to delete from Elasticsearch: {e}")
    return None


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


@app.get("/search",response_model=list[SearchResult])
async def search_notes(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=10, le=100),
    current_user: User = Depends(get_current_user)
):
    es = get_elasticsearch()
    search_body = {
        "query": {
            "multi_match": {
                "query": q,
                "fields": ["title^3", "content"],
                "fuzziness": "AUTO"
            }
        },
        "highlight": {
            "fields": {
                "title": {},
                "content": {"fragment_size": 150}
            }
        },
        "size": limit
    }


    response = await es.search(
        index=ELASTICSEARCH_INDEX,
        body=search_body
    )

    results = []
    for hit in response["hits"]["hits"]:
        result = SearchResult(
            id=hit["_id"],
            title=hit["_source"]["title"],
            content=hit["_source"]["content"],
            tags=hit["_source"]["tags"],
            score=hit["_score"],
            highlight=hit.get("highlight")
        )
        results.append(result)

     # Kafka event publish
    try:
        await publish_log({
            "event_type": "note_searched",
            "user_id": current_user.id,
            "resource_id": None,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "query": q,
                "result_count": len(results)
            }
        })
    except Exception as e:
        print("Kafka publish failed:", e)


    return results
    



@app.get("/cache/stats")
async def cache_stats():
    from .redis_client import get_redis
    redis = get_redis()

    info = await redis.info("stats")

    total_commands = info.get("total_commands_processed", 0)
    keyspace_hits = info.get("keyspace_hits", 0)
    keyspace_misses = info.get("keyspace_misses", 0)

    total_requests = keyspace_hits + keyspace_misses
    hit_rate = (keyspace_hits / total_requests * 100) if total_requests > 0 else 0

    return {
        "keyspace_hits": keyspace_hits,
        "keyspace_misses": keyspace_misses,
        "hit_rate_percentage": round(hit_rate, 2),
        "total_commands": total_commands
    }


@app.delete("/cache/clear")
async def clear_cache():
    await cache_delete_pattern("note:*")
    return {"message": "Cache cleared successfully"}   