import os


from dotenv import load_dotenv

from fastapi import FastAPI,Depends,HTTPException,status

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm


from .database import SessionLocal

load_dotenv()

app=FastAPI(
    title=os.getenv("APP_NAME","Collabnote"),
    description="Collabnote backend",
    version="1.0.0"
)


security=HTTPBearer()


def get_db():
    db=SessionLocal()

    try:
        yield db
    
    finally :
        db.close()

@app.get("/ping")
def ping():
    return {"status":"ok","message":"pong"}