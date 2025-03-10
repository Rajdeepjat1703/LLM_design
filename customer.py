from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import httpx
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorClient
import json 

router = APIRouter(prefix="/customers", tags=["Customers"])
NODEJS_API_BASE = "http://localhost:5000/api/v1"  # Update with actual Node.js API URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# MongoDB Connection
MONGO_URI = "mongodb://localhost:27017"  # Update with actual MongoDB URI
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client.get_database("vypar")  # Update with actual database name

# Pydantic Schemas
class CustomerCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gstNumber: Optional[str] = None