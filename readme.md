# CollabNote Backend

CollabNote is a **FastAPI** capstone API where users sign up, log in with JWT, and manage **notes** stored in **MongoDB** while **profiles** live in **PostgreSQL**. The same app adds **Elasticsearch** full‑text search, **Redis** caching for hot note reads, **Kafka** for activity events, and a **Strawberry GraphQL** layer at `/graphql`, suitable for running behind **Nginx** with Docker Compose.

This repository implements the **Poridhi FastAPI Basics — CollabNote** stack end‑to‑end: hybrid persistence, cache invalidation on writes, search with highlights, event publishing, and CI linting/tests.

## Prerequisites

- **Docker** and **Docker Compose** (v2 plugin recommended)
- **Python 3.11+** (for local runs and pytest without only‑Docker workflows)
- **4–6 GB RAM** recommended when running Postgres, MongoDB, Redis, Kafka, and Elasticsearch together

## Elasticsearch host setup (`vm.max_map_count`)

Elasticsearch needs a high virtual memory map count. On Linux (including a lab VM), run **once** (or add to `/etc/sysctl.conf`):

```bash
sudo sysctl -w vm.max_map_count=262144
```

This matches the capstone guidance and the **60s `start_period`** used in `docker-compose.yml` for Elasticsearch healthchecks.

## Quick start (Docker Compose)

1. Clone the repository and enter the project root.

2. Copy environment template and edit secrets:

   ```bash
   cp .env.example .env
   ```

3. Start infrastructure and API (see `docker-compose.yml` for exact services):

   ```bash
   docker compose up --build
   ```

   - **Nginx** on **port 80** proxies to two API replicas (`fastapi1`, `fastapi2`) when those services are used.
   - A single **`fastapi`** service is also defined with **port 8000** mapped for direct local access (e.g. `http://localhost:8000/docs`).

4. **Kafka consumer** (writes `activity_logs` in MongoDB) is a **separate process** per capstone. With dependencies running, from the repo root:

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python -m consumer.consumer
   ```

   Use the same `KAFKA_*` and `MONGODB_*` values as in `.env`.

## REST API reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | No | Service banner with `instance_id`, `hostname`, `client_ip` |
| GET | `/ping` | No | Simple liveness string |
| GET | `/health` | No | Health JSON with `status`, `instance_id` |
| POST | `/auth/signup` | No | Register user (bcrypt hash → Postgres) |
| POST | `/auth/login` | No | OAuth2 form login → JWT |
| GET | `/profile` | Bearer | Current user profile from Postgres |
| POST | `/notes` | Bearer | Create note in MongoDB; index ES; Kafka event |
| GET | `/notes` | Bearer | List current user’s notes |
| GET | `/notes/{note_id}` | Bearer | Single note; Redis cache (`note:{id}`), optional `X-Cache-Control: no-cache` bypass |
| PUT | `/notes/{note_id}` | Bearer | Update note; re‑index ES; clear Redis key |
| DELETE | `/notes/{note_id}` | Bearer | Delete note; remove from ES; clear cache |
| GET | `/users/{user_id}/notes` | Bearer | Notes for `user_id` (hybrid: user in Postgres, notes in MongoDB) |
| GET | `/search` | Bearer | Elasticsearch `multi_match` (title boost, fuzziness), highlights |
| GET | `/cache/stats` | No | Redis hit/miss style stats |
| DELETE | `/cache/clear` | No | Clear `note:*` cache keys pattern |
| GET | `/activity` | Bearer | Last 20 activity rows for user from MongoDB |
| GET | `/activity/stats` | No | Aggregate stats over logs |

OpenAPI docs: **`/docs`** when the app is running.

## GraphQL

Schema: **`app/graphql_schema.py`**. HTTP: **`GET` / `POST`** **`/graphql`**.  
JWT লাগে যেখানে রিজলভার `info.context["token"]` চেক করে (`me`, `notes`, আর মিউটেশন `create_note`).

### নামগুলো কীভাবে ধরবেন (Strawberry → GraphQL)

`graphql_schema.py`‑এ টাইপ/ফিল্ড **Python `snake_case`**‑এ লেখা। Strawberry ডিফল্টে স্কিমায় **camelCase** দেখায় (GraphiQL **Docs** / introspection‑এ যা আসে সেটাই চালান)। সাধারণ ম্যাপিং:

| Python (ফাইলে) | GraphQL (কোয়েরিতে) |
|----------------|----------------------|
| `created_at` | `createdAt` |
| `activity_logs` | `activityLogs` |
| `user_id` | `userId` |
| `event_type` | `eventType` |
| `resource_id` | `resourceId` |
| রুট মিউটেশন `create_note` | `createNote` |
| রুট মিউটেশন `update_user` | `updateUser` |

একক শব্দ (`me`, `users`, `title`, `email`) দুই জায়গাতেই একই থাকে।

### কোয়েরি লেখার ধরন (GraphQL syntax)

1. **`query` অপারেশন:** `query OptionalName { rootField { nestedFields } }`
2. **আর্গুমেন্ট:** বন্ধনীতে — `user(id: "1")` বা ভেরিয়েবল দিয়ে নিচের মতো।
3. **ভেরিয়েবল:** অপারেশনের নামের পর `($varName: Type!)` তারপর ফিল্ডে `(id: $varName)`; GraphiQL‑এ নিচে **Query Variables** JSON দিন।
4. **নেস্ট:** প্রতিটি অবজেক্ট টাইপের জন্য `{}`‑এর ভিতরে শুধু যে ফিল্ড চান সেগুলো লিখুন।
5. **অথ:** `Authorization: Bearer <access_token>` হেডার (REST লগইন থেকে `access_token`)।

### টাইপ ও ফিল্ড (স্কিমা অনুযায়ী)

**`User`** — `id`, `username`, `email`, `createdAt`; নেস্ট: `notes` → `[Note!]!`, `activityLogs` → `[ActivityLog!]!`  
**`Note`** — `id`, `userId`, `title`, `content`, `tags`, `createdAt`; নেস্ট: `author` → `User!`  
**`ActivityLog`** — `id`, `eventType`, `userId`, `resourceId`, `timestamp`, `metadata` (স্কেলার `JSON`)

### রুট `Query` (শুধু এইগুলো)

| রুট ফিল্ড | আর্গুমেন্ট | JWT |
|-----------|------------|-----|
| `me` | — | দরকার |
| `user` | `id: ID!` | চেক নেই |
| `users` | — | চেক নেই |
| `note` | `id: ID!` | চেক নেই |
| `notes` | — | দরকার |

### রুট `Mutation`

| ফিল্ড | আর্গুমেন্ট | JWT |
|--------|------------|-----|
| `createNote` | `title: String!`, `content: String!`, `tags: [String!]!` | দরকার |
| `updateUser` | `id: ID!`, `username: String`, `email: String` | চেক নেই |

### উদাহরণ: `me` (ড্যাশবোর্ড স্টাইল, camelCase)

```graphql
query Dashboard {
  me {
    username
    email
    createdAt
    notes {
      id
      title
      tags
      createdAt
    }
    activityLogs {
      eventType
      timestamp
      metadata
    }
  }
}
```

### উদাহরণ: `user`, `users`, `note`, `notes`

```graphql
# Postgres ইউজার ID (সংখ্যা স্ট্রিং হিসেবে ID তে)
query OneUser($userId: ID!) {
  user(id: $userId) {
    id
    username
    email
    createdAt
  }
}

query AllUsers {
  users {
    id
    username
    email
    createdAt
  }
}

# Mongo ObjectId স্ট্রিং
query OneNote($noteId: ID!) {
  note(id: $noteId) {
    id
    userId
    title
    content
    tags
    createdAt
    author {
      username
      email
    }
  }
}

query MyNotes {
  notes {
    id
    title
    content
    tags
    createdAt
  }
}
```

**Variables উদাহরণ (GraphiQL):**

```json
{ "userId": "1", "noteId": "507f1f77bcf86cd799439011" }
```

### উদাহরণ: মিউটেশন

```graphql
mutation NewNote($title: String!, $content: String!, $tags: [String!]!) {
  createNote(title: $title, content: $content, tags: $tags) {
    id
    title
    createdAt
  }
}

mutation PatchUser($id: ID!, $username: String, $email: String) {
  updateUser(id: $id, username: $username, email: $email) {
    id
    username
    email
    createdAt
  }
}
```

```json
{
  "title": "Hello",
  "content": "Body",
  "tags": ["api", "fastapi"]
}
```

```json
{ "id": "1", "username": "newname", "email": null }
```

> নিশ্চিত না হলে GraphiQL‑এ **Schema** / **Docs** খুলে ফিল্ডের ঠিক নাম কপি করুন; Strawberry ভার্সনে `auto_camel_case` বন্ধ থাকলে নাম `snake_case`‑ও হতে পারে।

All configuration is via environment variables. See **`.env.example`** for the full list and placeholders. **`DATABASE_URL`**, **`SECRET_KEY`**, **`MONGODB_URL`**, **`REDIS_URL`**, **`ELASTICSEARCH_URL`**, and **`KAFKA_BOOTSTRAP_SERVERS`** must be set correctly for your environment (hostnames differ between `localhost` and Docker service names).

## Tests & linting

```bash
pip install -r requirements-dev.txt
python -m flake8 app/ --count --max-line-length=88 --statistics
python -m pytest app/test_main.py -v --cov=app --cov-report=term
```

CI mirrors this in `.github/workflows/ci.yml` (flake8 + pytest + Docker build/push on `main`).

## Repository layout (high level)

| Path | Role |
|------|------|
| `app/main.py` | FastAPI app: REST + lifespan (Mongo, ES, Redis, Kafka) |
| `app/database.py` | SQLAlchemy engine / sessions (Postgres) |
| `app/mongodb.py` | Motor async Mongo client |
| `app/redis_client.py` | Async Redis helpers + TTL |
| `app/elasticsearch.py` | Async Elasticsearch client + index bootstrap |
| `app/kafka_producer.py` | `aiokafka` producer |
| `app/graphql_schema.py` | Strawberry schema |
| `app/auth.py` | JWT + passlib bcrypt |
| `app/models.py` / `app/schemas.py` | ORM + Pydantic models |
| `consumer/consumer.py` | Standalone Kafka → Mongo `activity_logs` consumer |
| `nginx/nginx.conf` | Upstream pool for two FastAPI containers |
| `docker-compose.yml` | Stack definition |
| `.github/workflows/ci.yml` | Lint, test, image build/push |

> **Phase 0:** submit **`requirements.md`** (or `requirements.pdf`) separately as required by the course; this README focuses on runnable setup and API documentation.

## Architecture decision log (ADL)

**1. Postgres for users, MongoDB for notes**  
**Context:** Capstone asks for a hybrid store: relational integrity for accounts vs flexible documents for notes and logs.  
**Decision:** Store `users` (email, username, password hash) in **PostgreSQL** via SQLAlchemy; store `notes` and `activity_logs` in **MongoDB** via Motor.  
**Rationale:** User fields are stable and query well relationally; notes and append‑only activity events fit a document model and share the same cluster as the consumer pipeline.

**2. Redis cache only on `GET /notes/{id}` with TTL**  
**Context:** Hot reads should be fast; stale reads after edits are unacceptable.  
**Decision:** Cache key `note:{note_id}` with TTL from **`CACHE_TTL`** (default **3600** s); invalidate the key on **PUT** and **DELETE**; **POST** does not pre‑warm cache.  
**Rationale:** Matches the spec’s invalidation table; bounded staleness; fewer keys than caching list endpoints.

**3. Kafka producer in API, consumer as separate process**  
**Context:** Activity logging must not block request latency unnecessarily and should be scalable independently.  
**Decision:** FastAPI publishes JSON events with `event_type`, `user_id`, `resource_id`, `timestamp`, `metadata`; a **separate** `consumer.consumer` process commits to **`activity_logs`**.  
**Rationale:** Process‑level decoupling and replay semantics (`auto_offset_reset=earliest`) align with the course architecture note.

---

**CollabNote** — FastAPI Basics Capstone | Backend layout aligned with this repository’s code.
