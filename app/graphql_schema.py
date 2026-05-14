import strawberry
from typing import List, Optional, Any
from datetime import datetime
from bson import ObjectId
from sqlalchemy.orm import Session

from app.mongodb import get_mongodb
from app.models import User as UserModel
from app.auth import decode_access_token
from app.elasticsearch import get_elasticsearch
from app.kafka_producer import publish_log

JSON = strawberry.scalar(
    dict[str, Any],
    name="JSON",
    serialize=lambda v: v,
    parse_value=lambda v: v,
)


@strawberry.type
class User:
    id: strawberry.ID
    username: str
    email: str
    created_at: str

    @strawberry.field
    async def notes(self) -> List["Note"]:
        db = get_mongodb()
        notes_cursor = db.notes.find({"user_id": int(self.id)})
        notes = await notes_cursor.to_list(length=100)

        return [
            Note(
                id=str(note["_id"]),
                user_id=str(note["user_id"]),
                title=note["title"],
                content=note["content"],
                tags=note.get("tags", []),
                created_at=note["created_at"].isoformat()
            )
            for note in notes
        ]

    @strawberry.field
    async def activity_logs(self) -> List["ActivityLog"]:
        db = get_mongodb()
        logs_cursor = db.activity_logs.find({"user_id": int(self.id)})
        logs = await logs_cursor.to_list(length=100)

        return [
            ActivityLog(
                id=str(log["_id"]),
                event_type=log["event_type"],
                user_id=str(log["user_id"]),
                resource_id=log.get("resource_id"),
                timestamp=log["timestamp"],
                metadata=log.get("metadata", {})
            )
            for log in logs
        ]


@strawberry.type
class Note:
    id: strawberry.ID
    user_id: str
    title: str
    content: str
    tags: List[str]
    created_at: str

    @strawberry.field
    async def author(self, info) -> User:
        db: Session = info.context["db"]
        user = db.query(UserModel).filter(UserModel.id == int(self.user_id)).first()
        if not user:
            raise Exception("Author not found")
        return User(
            id=strawberry.ID(str(user.id)),
            username=user.username,
            email=user.email,
            created_at=user.created_at.isoformat()
        )


@strawberry.type
class ActivityLog:
    id: strawberry.ID
    event_type: str
    user_id: str
    resource_id: Optional[str]
    timestamp: str
    metadata: JSON


@strawberry.type
class Query:
    @strawberry.field
    async def me(self, info) -> User:
        token = info.context.get("token")
        if not token:
            raise Exception("Not authenticated")
        email = decode_access_token(token)
        if not email:
            raise Exception("Invalid token")
        db: Session = info.context["db"]
        user = db.query(UserModel).filter(UserModel.email == email).first()
        if not user:
            raise Exception("User not found")
        return User(
            id=strawberry.ID(str(user.id)),
            username=user.username,
            email=user.email,
            created_at=user.created_at.isoformat()
        )

    @strawberry.field
    async def user(self, info, id: strawberry.ID) -> User:
        db: Session = info.context["db"]
        user = db.query(UserModel).filter(UserModel.id == int(id)).first()
        if not user:
            raise Exception("User not found")
        return User(
            id=strawberry.ID(str(user.id)),
            username=user.username,
            email=user.email,
            created_at=user.created_at.isoformat()
        )

    @strawberry.field
    async def users(self, info) -> List[User]:
        db: Session = info.context["db"]
        users = db.query(UserModel).all()
        return [
            User(
                id=strawberry.ID(str(u.id)),
                username=u.username,
                email=u.email,
                created_at=u.created_at.isoformat()
            )
            for u in users
        ]

    @strawberry.field
    async def note(self, info, id: strawberry.ID) -> Note:
        db = get_mongodb()
        try:
            obj_id = ObjectId(id)
        except (ValueError, TypeError):
            raise Exception("Invalid note ID")
        note = await db.notes.find_one({"_id": obj_id})
        if not note:
            raise Exception("Note not found")
        return Note(
            id=str(note["_id"]),
            user_id=str(note["user_id"]),
            title=note["title"],
            content=note["content"],
            tags=note.get("tags", []),
            created_at=note["created_at"].isoformat()
        )

    @strawberry.field
    async def notes(self, info) -> List[Note]:
        token = info.context.get("token")
        if not token:
            raise Exception("Not authenticated")
        email = decode_access_token(token)
        if not email:
            raise Exception("Invalid token")
        db: Session = info.context["db"]
        user = db.query(UserModel).filter(UserModel.email == email).first()
        if not user:
            raise Exception("User not found")
        mongo_db = get_mongodb()
        notes_cursor = mongo_db.notes.find({"user_id": user.id})
        notes = await notes_cursor.to_list(length=100)
        return [
            Note(
                id=str(note["_id"]),
                user_id=str(note["user_id"]),
                title=note["title"],
                content=note["content"],
                tags=note.get("tags", []),
                created_at=note["created_at"].isoformat()
            )
            for note in notes
        ]


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_note(
        self, info, title: str, content: str, tags: List[str]
    ) -> Note:
        token = info.context.get("token")
        if not token:
            raise Exception("Not authenticated")
        email = decode_access_token(token)
        if not email:
            raise Exception("Invalid token")
        db: Session = info.context["db"]
        user = db.query(UserModel).filter(UserModel.email == email).first()
        if not user:
            raise Exception("User not found")

        mongo_db = get_mongodb()
        es = get_elasticsearch()

        new_note = {
            "user_id": user.id,
            "title": title,
            "content": content,
            "tags": tags,
            "created_at": datetime.utcnow()
        }

        result = await mongo_db.notes.insert_one(new_note)
        note_id = str(result.inserted_id)

        await es.index(
            index="notes",
            id=note_id,
            document={
                "title": title,
                "content": content,
                "tags": tags,
                "created_at": new_note["created_at"].isoformat()
            }
        )

        await publish_log({
            "event_type": "note_created",
            "user_id": user.id,
            "resource_id": note_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "title": title,
                "tags": tags
            }
        })

        return Note(
            id=note_id,
            user_id=str(user.id),
            title=title,
            content=content,
            tags=tags,
            created_at=new_note["created_at"].isoformat()
        )

    @strawberry.mutation
    async def update_user(
        self,
        info,
        id: strawberry.ID,
        username: Optional[str] = None,
        email: Optional[str] = None,
    ) -> User:
        db: Session = info.context["db"]
        user = db.query(UserModel).filter(UserModel.id == int(id)).first()
        if not user:
            raise Exception("User not found")

        old_username = user.username
        old_email = user.email

        if username:
            user.username = username
        if email:
            user.email = email

        db.commit()
        db.refresh(user)

        # Log activity
        await publish_log({
            "event_type": "user_updated",
            "user_id": user.id,
            "resource_id": str(user.id),
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "old_username": old_username,
                "new_username": user.username,
                "old_email": old_email,
                "new_email": user.email
            }
        })

        return User(
            id=strawberry.ID(str(user.id)),
            username=user.username,
            email=user.email,
            created_at=user.created_at.isoformat()
        )


schema = strawberry.Schema(query=Query, mutation=Mutation)