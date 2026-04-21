import os


from dotenv import load_dotenv
from fastapi import FastAPI,Depends,HTTPException,status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional,Dict


from datetime import timedelta,datetime
from .schemas import UserCreate,UserOut,Token,TokenData
from .models import User
from .database import SessionLocal
from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

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


