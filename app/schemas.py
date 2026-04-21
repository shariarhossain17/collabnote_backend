from pydantic import BaseModel,EmailStr,Field


from typing import Optional

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