import os

from datetime import datetime,timedelta
from typing import Optional

from jose import JWTError,jwt

from passlib.context import CryptContext

from dotenv import load_env


load_env()

SECRET_KEY=os.getenv("SECRET_KEY")
ALGORITHM=os.getenv("ALGORITHM","HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))



#password hashing context


pwd_context=CryptContext(schemes=["bycrypt"],deprecated="auto")



def hash_password(password:str)->str:
    return pwd_context.hash(password)

def verify_password(plain_password:str,hash_password:str)->bool:
    return pwd_context.verify(plain_password,hash_password)



def create_access_token(data:dict,expire_delta:Optional[timedelta]=None)-> str:
    to_encode =data.copy()


    if expire_delta:
        expire=datetime.utcnow()+expire_delta
    
    else:
        expire=datetime.utcnow()+timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp":expire})


    #Encode Jwt

    encoded_jwt = jwt.encode(to_encode,SECRET_KEY,algorithm=ALGORITHM)

    return encoded_jwt


def decode_access_token(token:str)->Optional[str]:


    try:
        payload=jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM])
        email:str=payload.get("sub")
        return email
    except JWTError:
        return None